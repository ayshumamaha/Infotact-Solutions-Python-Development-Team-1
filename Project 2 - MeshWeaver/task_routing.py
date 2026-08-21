"""
task_routing.py
----------------
Module: Task Routing.

Decides WHICH peer in the mesh should run a submitted task, by picking
the node currently reporting the lowest CPU load.

In the full MeshWeaver design, load numbers normally arrive continuously
via the Gossip Protocol module (each node broadcasts its CPU/RAM every
few seconds to its neighbours). Since Gossip Protocol isn't one of the
four modules built here, this module includes its own minimal on-demand
LOAD_QUERY / LOAD_REPORT exchange instead, so Task Routing is fully
self-contained and testable in isolation. In production this cache would
simply be kept warm by the Gossip module instead of queried on demand.

Builds on:
  - async_networking.Node        (Module 1: transport + handler registry)
  - remote_task_execution.RemoteExecutor  (Module 2: actually running the task)
"""

import asyncio
import logging

import psutil

from asyn import Node, Message
from remote import RemoteExecutor

logger = logging.getLogger("meshweaver.task_routing")

LOAD_QUERY = "LOAD_QUERY"
LOAD_REPORT = "LOAD_REPORT"


def current_load() -> dict:
    """Read this machine's real current CPU and RAM usage."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_percent": psutil.virtual_memory().percent,
    }


def enable_load_reporting(node: Node):
    """
    Register the LOAD_QUERY handler on any node so it can answer "what's
    your current load" questions from a router elsewhere in the mesh.
    Call this on EVERY node that should be routable to, not just on the
    node that does the routing.
    """
    async def _on_load_query(message: Message, addr):
        return Message(LOAD_REPORT, node.node_id, payload=current_load(), msg_id=message.msg_id)

    node.register_handler(LOAD_QUERY, _on_load_query)


class TaskRouter:
    """
    Attaches to a Node. Knows about a set of peers, can query their live
    load, and routes a task to whichever peer is least busy right now.
    """

    def __init__(self, node: Node, executor: RemoteExecutor):
        self.node = node
        self.executor = executor
        self.peers = set()  # set of (host, port) tuples

        # A router should also be able to answer load queries about itself.
        enable_load_reporting(self.node)

    # ---------- peer management ----------

    def add_peer(self, host: str, port: int):
        self.peers.add((host, port))

    def remove_peer(self, host: str, port: int):
        self.peers.discard((host, port))

    async def query_peer_load(self, host: str, port: int, timeout: float = 2.0) -> dict:
        """Ask one specific peer for its current load. Returns None if unreachable."""
        try:
            msg = Message(LOAD_QUERY, self.node.node_id)
            reply = await self.node.send_tcp(host, port, msg, timeout=timeout)
            if reply is None:
                return None
            return reply.payload
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, OSError) as e:
            logger.warning("Could not reach peer %s:%s for load query: %s", host, port, e)
            return None

    async def get_cluster_load(self) -> dict:
        """
        Query every known peer concurrently. Returns {(host, port): load_dict}
        for peers that responded. Dead/unreachable peers are simply omitted --
        this IS the fault tolerance behaviour: a peer that doesn't answer
        just isn't considered for routing.
        """
        if not self.peers:
            return {}

        results = await asyncio.gather(
            *[self.query_peer_load(host, port) for host, port in self.peers]
        )
        return {
            peer: load
            for peer, load in zip(self.peers, results)
            if load is not None
        }

    # ---------- routing decision ----------

    async def pick_best_peer(self):
        """
        Returns the (host, port) of the peer with the lowest current
        CPU load, or None if no peers are reachable.
        """
        cluster_load = await self.get_cluster_load()
        if not cluster_load:
            return None
        return min(cluster_load, key=lambda peer: cluster_load[peer]["cpu_percent"])

    # ---------- the actual routing + execution ----------

    async def route_task(self, func, *args, timeout: float = 10.0, **kwargs):
        """
        Picks the least-loaded known peer and runs func(*args, **kwargs)
        there via RemoteExecutor. Raises RuntimeError if no peer is
        reachable right now.
        """
        target = await self.pick_best_peer()
        if target is None:
            raise RuntimeError("No reachable peers to route this task to")

        host, port = target
        logger.info("Routing task to %s:%s (lowest reported CPU load)", host, port)
        return await self.executor.submit_task(host, port, func, *args, timeout=timeout, **kwargs)


if __name__ == "__main__":
    # Self-contained demo: three worker nodes with simulated load, plus one
    # coordinator node that routes a task to whichever worker is least busy.

    def add(a, b):
        return a + b

    async def _demo():
        coordinator = await Node("coordinator", port=9301).start()
        worker_1 = await Node("worker-1", port=9302).start()
        worker_2 = await Node("worker-2", port=9303).start()
        worker_3 = await Node("worker-3", port=9304).start()

        router = TaskRouter(coordinator, RemoteExecutor(coordinator))
        for w in (worker_1, worker_2, worker_3):
            RemoteExecutor(w)
            enable_load_reporting(w)  # so this worker can answer load queries

        for w in (worker_1, worker_2, worker_3):
            router.add_peer(w.host, w.port)

        print("Querying live CPU load of all 3 workers...")
        cluster_load = await router.get_cluster_load()
        for (host, port), load in cluster_load.items():
            print(f"  {host}:{port} -> CPU {load['cpu_percent']}%  RAM {load['ram_percent']}%")

        print("\nRouting add(3, 4) to the least-loaded worker...")
        result = await router.route_task(add, 3, 4)
        print(f"  -> Result: {result}")

        for n in (coordinator, worker_1, worker_2, worker_3):
            await n.stop()
        print("\nAll nodes shut down cleanly.")

    asyncio.run(_demo())


"""
gossip_protocol.py
-------------------
Module: Gossip Protocol.

Keeps every node's NodeManager eventually consistent without anyone having
to query anyone else on demand. Once per interval, a node:

  1. Picks a small random sample of the peers it currently knows about
     (not the whole mesh -- that's what makes gossip scale: O(fanout) work
     per round instead of O(n)).
  2. Sends each of them a GOSSIP message containing its own peer list plus
     its own current CPU/RAM load.
  3. The recipient merges that peer list into its own NodeManager (new
     peers get added, known peers get their load updated) and replies with
     its own view back, so information spreads in both directions per
     exchange.

This is the same "gossip about liveness and load" idea task_routing.py's
docstring mentions as the production replacement for its on-demand
LOAD_QUERY -- this module is that replacement, kept separate so
task_routing can still be exercised in isolation.

Builds on:
  - async_networking.Node
  - node_management.NodeManager
"""

import asyncio
import logging
import random

import psutil

from async_networking import Node, Message
from node_management import NodeManager

logger = logging.getLogger("meshweaver.gossip")

GOSSIP = "GOSSIP"


def _current_load() -> dict:
    return {"cpu_percent": psutil.cpu_percent(interval=0.1), "ram_percent": psutil.virtual_memory().percent}


def enable_gossip(node: Node, manager: NodeManager):
    """Register the GOSSIP handler so this node can receive and answer gossip from peers."""

    async def _on_gossip(message: Message, addr) -> Message:
        sender_id = message.sender_id
        sender_load = message.payload.get("load", {})
        manager.join(sender_id, addr[0], message.payload.get("port", addr[1]))
        manager.touch(sender_id)
        manager.update_load(sender_id, sender_load.get("cpu_percent"), sender_load.get("ram_percent"))

        for peer_id, host, port in message.payload.get("peers", []):
            manager.join(peer_id, host, port)

        return Message(
            GOSSIP,
            node.node_id,
            payload={"peers": manager.as_address_list(), "load": _current_load(), "port": node.port},
            msg_id=message.msg_id,
        )

    node.register_handler(GOSSIP, _on_gossip)


async def gossip_once(node: Node, manager: NodeManager, fanout: int = 2, timeout: float = 2.0) -> int:
    """Do a single gossip round: contact up to `fanout` random known peers. Returns how many replied."""
    candidates = manager.all_peers()
    if not candidates:
        return 0

    targets = random.sample(candidates, k=min(fanout, len(candidates)))
    replies = 0
    for peer in targets:
        msg = Message(
            GOSSIP, node.node_id,
            payload={"peers": manager.as_address_list(), "load": _current_load(), "port": node.port},
        )
        try:
            reply = await node.send_tcp(peer.host, peer.port, msg, timeout=timeout)
        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            logger.warning("Gossip to %s failed: %s", peer.node_id, e)
            manager.mark_status(peer.node_id, "suspect")
            continue

        if reply is None:
            continue
        replies += 1
        manager.touch(peer.node_id)
        for peer_id, host, port in reply.payload.get("peers", []):
            manager.join(peer_id, host, port)

    return replies


async def gossip_loop(node: Node, manager: NodeManager, interval: float = 5.0, fanout: int = 2, rounds: int = None):
    """
    Run gossip_once() forever (or `rounds` times, for demos/tests) on a
    fixed interval. Intended to be launched with asyncio.create_task() and
    cancelled on shutdown.
    """
    completed = 0
    while rounds is None or completed < rounds:
        await gossip_once(node, manager, fanout=fanout)
        completed += 1
        await asyncio.sleep(interval)


if __name__ == "__main__":
    async def _demo():
        node_a = await Node("node-A", port=9701).start()
        node_b = await Node("node-B", port=9702).start()
        node_c = await Node("node-C", port=9703).start()

        mgr_a = NodeManager(node_a.node_id, node_a.host, node_a.port)
        mgr_b = NodeManager(node_b.node_id, node_b.host, node_b.port)
        mgr_c = NodeManager(node_c.node_id, node_c.host, node_c.port)

        for node, mgr in ((node_a, mgr_a), (node_b, mgr_b), (node_c, mgr_c)):
            enable_gossip(node, mgr)

        # Seed partial knowledge: A knows B, B knows C. Neither A nor C
        # knows about the other yet -- gossip should fix that.
        mgr_a.join(node_b.node_id, node_b.host, node_b.port)
        mgr_b.join(node_a.node_id, node_a.host, node_a.port)
        mgr_b.join(node_c.node_id, node_c.host, node_c.port)
        mgr_c.join(node_b.node_id, node_b.host, node_b.port)

        print(f"Before gossip: A knows {[p.node_id for p in mgr_a.all_peers()]}, "
              f"C knows {[p.node_id for p in mgr_c.all_peers()]}")

        print("\nRunning 3 gossip rounds on each node...")
        for _ in range(3):
            await gossip_once(node_a, mgr_a, fanout=1)
            await gossip_once(node_b, mgr_b, fanout=2)
            await gossip_once(node_c, mgr_c, fanout=1)

        print(f"\nAfter gossip: A knows {[p.node_id for p in mgr_a.all_peers()]}, "
              f"C knows {[p.node_id for p in mgr_c.all_peers()]}")
        print("(A and C never talked directly -- they learned about each other through B)")

        for n in (node_a, node_b, node_c):
            await n.stop()
        print("\nNodes shut down cleanly.")

    asyncio.run(_demo())

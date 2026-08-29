
"""
heartbeat_fault_tolerance.py
------------------------------
Module: Heartbeat Monitoring & Fault Tolerance.

Reuses async_networking's existing PING/PONG (Module 1 already built it
for RTT measurement) as a liveness check, and layers a missed-heartbeat
counter on top so the mesh can tell "slow" apart from "gone":

  - Every `interval` seconds, ping each known peer.
  - A reply resets that peer's miss counter and marks it ALIVE.
  - A missed ping increments the counter and marks the peer SUSPECT.
  - After `max_misses` consecutive misses, the peer is marked DEAD and an
    optional callback fires (task_routing / gossip naturally stop
    considering DEAD peers once node_management reflects that status).

Builds on:
  - async_networking.Node.ping()
  - node_management.NodeManager
"""

import asyncio
import logging

from async_networking import Node
from node_management import NodeManager, ALIVE, SUSPECT, DEAD

logger = logging.getLogger("meshweaver.heartbeat")


class HeartbeatMonitor:
    """Periodically pings every peer in a NodeManager and updates their status."""

    def __init__(self, node: Node, manager: NodeManager, interval: float = 5.0,
                 timeout: float = 1.0, max_misses: int = 3, on_dead=None):
        self.node = node
        self.manager = manager
        self.interval = interval
        self.timeout = timeout
        self.max_misses = max_misses
        self.on_dead = on_dead  # optional callback(node_id)
        self._misses: dict[str, int] = {}
        self._task = None

    async def check_once(self):
        """Ping every currently-known non-dead peer once."""
        for peer in self.manager.all_peers():
            try:
                await self.node.ping(peer.host, peer.port, timeout=self.timeout)
            except asyncio.TimeoutError:
                self._record_miss(peer.node_id)
            else:
                self._misses[peer.node_id] = 0
                self.manager.mark_status(peer.node_id, ALIVE)
                self.manager.touch(peer.node_id)

    def _record_miss(self, node_id: str):
        misses = self._misses.get(node_id, 0) + 1
        self._misses[node_id] = misses

        if misses >= self.max_misses:
            self.manager.mark_status(node_id, DEAD)
            logger.warning("Peer %s missed %d heartbeats -- marked DEAD", node_id, misses)
            if self.on_dead:
                self.on_dead(node_id)
        else:
            self.manager.mark_status(node_id, SUSPECT)
            logger.info("Peer %s missed a heartbeat (%d/%d)", node_id, misses, self.max_misses)

    async def run(self, rounds: int = None):
        """Run check_once() forever (or `rounds` times, for demos/tests) on a fixed interval."""
        completed = 0
        while rounds is None or completed < rounds:
            await self.check_once()
            completed += 1
            if rounds is None or completed < rounds:
                await asyncio.sleep(self.interval)

    def start(self):
        """Launch run() as a background asyncio task. Call stop() to cancel it."""
        self._task = asyncio.ensure_future(self.run())
        return self._task

    def stop(self):
        if self._task:
            self._task.cancel()


if __name__ == "__main__":
    async def _demo():
        node_a = await Node("node-A", port=9801).start()
        node_b = await Node("node-B", port=9802).start()

        mgr_a = NodeManager(node_a.node_id, node_a.host, node_a.port)
        mgr_a.join(node_b.node_id, node_b.host, node_b.port)

        dead_peers = []
        monitor = HeartbeatMonitor(node_a, mgr_a, interval=0.5, timeout=0.5, max_misses=2,
                                    on_dead=lambda nid: dead_peers.append(nid))

        print("Round 1: node-B is up, should stay ALIVE...")
        await monitor.check_once()
        print(f"  node-B status: {mgr_a.get(node_b.node_id).status}")

        print("\nStopping node-B, then checking twice (max_misses=2)...")
        await node_b.stop()
        await monitor.check_once()
        print(f"  node-B status after 1 miss: {mgr_a.get(node_b.node_id).status}")
        await monitor.check_once()
        print(f"  node-B status after 2 misses: {mgr_a.get(node_b.node_id).status}")
        print(f"  on_dead callback fired for: {dead_peers}")

        await node_a.stop()
        print("\nNode-A shut down cleanly.")

    asyncio.run(_demo())

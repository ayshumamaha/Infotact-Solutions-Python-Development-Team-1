"""
node_management.py
-------------------
Module: Node Management.

A NodeManager is the mesh's "who's who" -- a shared registry that the other
modules read from and write to instead of passing raw (host, port) tuples
around everywhere:

  - kademlia_node_discovery writes new entries when a peer announces itself.
  - gossip_protocol merges remote peer views into it.
  - heartbeat_fault_tolerance flips entries to DEAD when a peer stops
    answering, and back to ALIVE if it responds again.
  - task_routing / rich_cli_dashboard read from it to know who's around.

This module intentionally has no networking code of its own -- it is pure
bookkeeping, which keeps it trivial to unit test and safe for every other
module to depend on without circular imports.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("meshweaver.node_management")

ALIVE = "alive"
SUSPECT = "suspect"
DEAD = "dead"


@dataclass
class PeerInfo:
    node_id: str
    host: str
    port: int
    status: str = ALIVE
    cpu_percent: float = None
    ram_percent: float = None
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    @property
    def address(self):
        return (self.host, self.port)


class NodeManager:
    """In-memory registry of every peer this node currently knows about."""

    def __init__(self, self_id: str, self_host: str, self_port: int):
        self.self_id = self_id
        self.self_host = self_host
        self.self_port = self_port
        self._peers: dict[str, PeerInfo] = {}

    # ---------- membership ----------

    def join(self, node_id: str, host: str, port: int) -> PeerInfo:
        """Register a peer, or refresh it if already known."""
        if node_id == self.self_id:
            return None
        existing = self._peers.get(node_id)
        if existing:
            existing.host, existing.port = host, port
            existing.last_seen = time.time()
            if existing.status != ALIVE:
                logger.info("Peer %s is back (was %s)", node_id, existing.status)
            existing.status = ALIVE
            return existing

        info = PeerInfo(node_id=node_id, host=host, port=port)
        self._peers[node_id] = info
        logger.info("Peer joined: %s at %s:%s", node_id, host, port)
        return info

    def leave(self, node_id: str):
        if self._peers.pop(node_id, None):
            logger.info("Peer left: %s", node_id)

    def mark_status(self, node_id: str, status: str):
        peer = self._peers.get(node_id)
        if peer and peer.status != status:
            logger.info("Peer %s status: %s -> %s", node_id, peer.status, status)
            peer.status = status

    def touch(self, node_id: str):
        """Record that we just heard from this peer."""
        peer = self._peers.get(node_id)
        if peer:
            peer.last_seen = time.time()
            peer.status = ALIVE

    def update_load(self, node_id: str, cpu_percent: float, ram_percent: float):
        peer = self._peers.get(node_id)
        if peer:
            peer.cpu_percent = cpu_percent
            peer.ram_percent = ram_percent

    # ---------- queries ----------

    def get(self, node_id: str) -> PeerInfo:
        return self._peers.get(node_id)

    def all_peers(self, include_dead: bool = False) -> list[PeerInfo]:
        return [p for p in self._peers.values() if include_dead or p.status != DEAD]

    def alive_addresses(self) -> set[tuple[str, int]]:
        return {p.address for p in self._peers.values() if p.status == ALIVE}

    def as_address_list(self) -> list[tuple[str, str, int]]:
        """(node_id, host, port) for every known peer -- the shape gossip/discovery ship over the wire."""
        return [(p.node_id, p.host, p.port) for p in self._peers.values()]

    def __len__(self):
        return len(self._peers)


if __name__ == "__main__":
    manager = NodeManager("coordinator", "127.0.0.1", 9000)
    manager.join("worker-1", "127.0.0.1", 9001)
    manager.join("worker-2", "127.0.0.1", 9002)
    manager.update_load("worker-1", cpu_percent=12.5, ram_percent=40.0)
    manager.mark_status("worker-2", SUSPECT)

    print(f"Known peers: {len(manager)}")
    for peer in manager.all_peers():
        print(f"  {peer.node_id} @ {peer.host}:{peer.port} [{peer.status}] cpu={peer.cpu_percent}")

    manager.leave("worker-2")
    print(f"After leave: {[p.node_id for p in manager.all_peers()]}")


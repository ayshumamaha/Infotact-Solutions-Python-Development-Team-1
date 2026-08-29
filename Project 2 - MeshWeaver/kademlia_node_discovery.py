
"""
kademlia_node_discovery.py
---------------------------
Module: Node Discovery.

A full Kademlia DHT (XOR-metric routing tables, k-buckets, iterative
FIND_NODE lookups) is a project on its own. What this mesh actually needs
is much simpler: a new node has to learn who else is already in the mesh.
So this module implements the piece of Kademlia's design that solves that
problem -- bootstrap-based discovery -- without the full DHT machinery:

  1. A new node ANNOUNCEs itself to one already-known "bootstrap" peer.
  2. The bootstrap peer registers the newcomer in its NodeManager and
     replies with its own current peer list (PEER_LIST).
  3. The newcomer merges that list into its own NodeManager, so after one
     round-trip it already knows about every peer the bootstrap node knew
     about.

Ongoing membership changes after that point are handled by
gossip_protocol.py, and dead-peer detection by heartbeat_fault_tolerance.py
-- this module's only job is getting a brand-new node "into" the mesh.

Builds on:
  - async_networking.Node   (transport)
  - node_management.NodeManager  (where discovered peers are recorded)
"""

import logging

from async_networking import Node, Message
from node_management import NodeManager

logger = logging.getLogger("meshweaver.discovery")

ANNOUNCE = "ANNOUNCE"
PEER_LIST = "PEER_LIST"


def enable_discovery(node: Node, manager: NodeManager):
    """
    Register the ANNOUNCE handler on `node` so other nodes can discover it
    (and be discovered by it in return). Call this on every node in the mesh,
    not just bootstrap nodes -- any node can be someone else's entry point.
    """

    async def _on_announce(message: Message, addr) -> Message:
        peer_id = message.sender_id
        peer_host, peer_port = message.payload["host"], message.payload["port"]
        manager.join(peer_id, peer_host, peer_port)

        return Message(
            PEER_LIST,
            node.node_id,
            payload={"peers": manager.as_address_list()},
            msg_id=message.msg_id,
        )

    node.register_handler(ANNOUNCE, _on_announce)


async def announce_to(node: Node, manager: NodeManager, bootstrap_host: str, bootstrap_port: int, timeout: float = 5.0) -> int:
    """
    Announce `node` to a bootstrap peer and merge whatever peer list comes
    back into `manager`. Returns the number of newly-learned peers.
    """
    msg = Message(ANNOUNCE, node.node_id, payload={"host": node.host, "port": node.port})
    reply = await node.send_tcp(bootstrap_host, bootstrap_port, msg, timeout=timeout)
    if reply is None:
        logger.warning("Bootstrap peer %s:%s did not respond to ANNOUNCE", bootstrap_host, bootstrap_port)
        return 0

    before = len(manager)
    for peer_id, host, port in reply.payload.get("peers", []):
        manager.join(peer_id, host, port)
    # The bootstrap peer itself is also a peer worth knowing about.
    manager.join(reply.sender_id, bootstrap_host, bootstrap_port)

    learned = len(manager) - before
    logger.info("Discovered %d new peer(s) via bootstrap %s:%s", learned, bootstrap_host, bootstrap_port)
    return learned


if __name__ == "__main__":
    import asyncio

    async def _demo():
        # node-A starts first and acts as the bootstrap for everyone else.
        node_a = await Node("node-A", port=9601).start()
        mgr_a = NodeManager(node_a.node_id, node_a.host, node_a.port)
        enable_discovery(node_a, mgr_a)

        node_b = await Node("node-B", port=9602).start()
        mgr_b = NodeManager(node_b.node_id, node_b.host, node_b.port)
        enable_discovery(node_b, mgr_b)

        node_c = await Node("node-C", port=9603).start()
        mgr_c = NodeManager(node_c.node_id, node_c.host, node_c.port)
        enable_discovery(node_c, mgr_c)

        print("node-B announces to node-A (the only peer it knows about)...")
        await announce_to(node_b, mgr_b, node_a.host, node_a.port)
        print(f"  node-B now knows: {[p.node_id for p in mgr_b.all_peers()]}")

        print("\nnode-C announces to node-A too...")
        await announce_to(node_c, mgr_c, node_a.host, node_a.port)
        print(f"  node-C now knows: {[p.node_id for p in mgr_c.all_peers()]}")
        print(f"  node-A now knows: {[p.node_id for p in mgr_a.all_peers()]}  (both B and C found it)")

        for n in (node_a, node_b, node_c):
            await n.stop()
        print("\nNodes shut down cleanly.")

    asyncio.run(_demo())

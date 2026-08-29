import asyncio

from tls_ssl_security import SecureNode, SecureExecutor, generate_signing_keypair
from node_management import NodeManager
from kademlia_node_discovery import enable_discovery, announce_to
from gossip_protocol import enable_gossip, gossip_once
from task_routing import enable_load_reporting, TaskRouter
from remote_task_execution import RemoteExecutor
from heartbeat_fault_tolerance import HeartbeatMonitor
from rich_cli_dashboard import render_snapshot
from textual_ui import MeshWeaverApp


async def main():

    print("=" * 60)
    print("        MeshWeaver Distributed Mesh Computing Framework")
    print("=" * 60)

    # STEP 1 : Async Networking + TLS/SSL Secure Communication
    # Bring up the mesh nodes. SecureNode wraps async_networking.Node so
    # every TCP exchange below -- routing, gossip, discovery, heartbeats --
    # is already TLS-encrypted, without those modules needing to know it.

    print("\nSTEP 1 : Starting Nodes (TLS-secured transport)")

    coordinator = await SecureNode("coordinator").start()
    workers = [await SecureNode(f"worker-{i}").start() for i in range(1, 4)]

    print(f"  coordinator listening on {coordinator.host}:{coordinator.port}")
    for w in workers:
        print(f"  {w.node_id} listening on {w.host}:{w.port}")

    # STEP 2 : Node Management
    # Each node gets its own registry of who else it knows about.

    print("\nSTEP 2 : Initializing Node Management")

    managers = {n.node_id: NodeManager(n.node_id, n.host, n.port) for n in [coordinator, *workers]}

    for n in [coordinator, *workers]:
        enable_discovery(n, managers[n.node_id])
        enable_gossip(n, managers[n.node_id])

    print(f"  Node Manager ready for: {list(managers.keys())}")

    # STEP 3 : Node Discovery
    # Workers only know the coordinator's address to start. One ANNOUNCE
    # round-trip each is enough for them to learn about the coordinator
    # (and, once gossip runs, about each other).

    print("\nSTEP 3 : Node Discovery (workers announcing to coordinator)")

    for w in workers:
        await announce_to(w, managers[w.node_id], coordinator.host, coordinator.port)
        print(f"  {w.node_id} discovered: {[p.node_id for p in managers[w.node_id].all_peers()]}")

    print(f"  coordinator now knows: {[p.node_id for p in managers[coordinator.node_id].all_peers()]}")

    # STEP 4 : Gossip Protocol
    # A couple of gossip rounds so workers learn about each other too,
    # not just about the coordinator.

    print("\nSTEP 4 : Gossip Protocol (propagating peer knowledge)")

    for _ in range(2):
        for n in [coordinator, *workers]:
            await gossip_once(n, managers[n.node_id], fanout=2)

    for w in workers:
        print(f"  {w.node_id} now knows: {[p.node_id for p in managers[w.node_id].all_peers()]}")

    # STEP 5 : Task Routing + Remote Task Execution
    # Workers report live CPU/RAM load; the coordinator routes a task to
    # whichever worker is least busy right now and runs it there.

    print("\nSTEP 5 : Task Routing (routing to the least-loaded worker)")

    for w in workers:
        enable_load_reporting(w)
        RemoteExecutor(w)

    coordinator_executor = RemoteExecutor(coordinator)
    router = TaskRouter(coordinator, coordinator_executor)
    for w in workers:
        router.add_peer(w.host, w.port)

    cluster_load = await router.get_cluster_load()
    for (host, port), load in cluster_load.items():
        peer_id = next(p.node_id for p in managers[coordinator.node_id].all_peers() if p.address == (host, port))
        managers[coordinator.node_id].update_load(peer_id, load["cpu_percent"], load["ram_percent"])
        print(f"  {peer_id} @ {host}:{port} -> CPU {load['cpu_percent']}%  RAM {load['ram_percent']}%")

    def add(a, b):
        return a + b

    result = await router.route_task(add, 21, 21)
    print(f"  Routed add(21, 21) -> result: {result}")

    # STEP 6 : Heartbeat Monitoring & Fault Tolerance
    # Detect a dead peer: stop worker-1, then show the coordinator's
    # heartbeat monitor flag it as DEAD after repeated missed pings.

    print("\nSTEP 6 : Heartbeat Monitoring & Fault Tolerance")

    dead_peers = []
    monitor = HeartbeatMonitor(
        coordinator, managers[coordinator.node_id],
        interval=0.3, timeout=0.5, max_misses=2,
        on_dead=lambda nid: dead_peers.append(nid),
    )

    await monitor.check_once()
    print(f"  All workers alive: "
          f"{[p.node_id for p in managers[coordinator.node_id].all_peers() if p.status == 'alive']}")

    print(f"  Stopping {workers[0].node_id} to simulate a node failure...")
    await workers[0].stop()
    await monitor.check_once()
    await monitor.check_once()
    print(f"  Detected dead: {dead_peers}")

    # STEP 7 : Request Signing (TLS/SSL Security, part 2)
    # Beyond transport encryption, prove WHO sent a task: a signed submission
    # from an untrusted signer should be rejected even over the same
    # encrypted channel used in Step 5.

    print("\nSTEP 7 : Request Signing (coordinator -> worker-2, signed & verified)")

    coord_priv, coord_pub = generate_signing_keypair()
    w2 = workers[1]
    w2_priv, w2_pub = generate_signing_keypair()

    coord_secure_exec = SecureExecutor(coordinator, coord_priv)
    w2_secure_exec = SecureExecutor(w2, w2_priv, trusted_keys={coordinator.node_id: coord_pub})

    signed_result = await coord_secure_exec.submit_task(w2.host, w2.port, add, 10, 15)
    print(f"  Signed task accepted (trusted signer) -> result: {signed_result}")

    untrusted_priv, _ = generate_signing_keypair()
    impostor_exec = SecureExecutor(coordinator, untrusted_priv)
    try:
        await impostor_exec.submit_task(w2.host, w2.port, add, 1, 1)
        print("  Unexpected: untrusted signer was accepted")
    except PermissionError as e:
        print(f"  Untrusted signer correctly rejected: {e}")

    # STEP 8 : Rich CLI Dashboard (snapshot)

    print("\nSTEP 8 : Mesh Status Dashboard\n")

    render_snapshot(managers[coordinator.node_id])

    print("\n===================================")
    print("Backend Pipeline Executed Successfully")
    print("===================================")

    # STEP 9 : Interactive Textual UI
    # Live dashboard over the same coordinator/manager/router/monitor the
    # pipeline just built. 'r' runs a gossip+heartbeat round on demand,
    # 't' routes a fresh demo task, 'q' quits back to main.py for shutdown.

    print("\n🚀 Launching Interactive Textual UI Dashboard...")

    app = MeshWeaverApp(coordinator, managers[coordinator.node_id], router, monitor)
    await app.run_async()

    # STEP 10 : Clean shutdown (after the UI is closed)

    print("\nSTEP 10 : Shutting Down")

    monitor.stop()
    for n in [coordinator, *workers[1:]]:
        await n.stop()

    print("\nMeshWeaver Pipeline Shut Down Cleanly")


if __name__ == "__main__":
    asyncio.run(main())

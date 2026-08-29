"""
textual_ui.py
--------------
Module: Interactive Terminal UI.

The interactive counterpart to rich_cli_dashboard.py's static snapshot --
same idea as PyChronicle's textual_ui.py, but showing MeshWeaver's live
mesh state instead of a debugging timeline: a sidebar listing every
module in the pipeline, summary cards, a live node table, and activity
panels for routing/security/discovery events.

Because the mesh is asyncio-based (nodes, gossip, heartbeats all run on
the event loop), this app is driven with `await app.run_async()` from
inside main.py's own event loop rather than the blocking `app.run()`
PyChronicle uses -- that keeps the mesh's background asyncio objects
(the SecureNode transports, the HeartbeatMonitor) alive and usable while
the UI is open.

Bindings:
  r  -- manual refresh: run one gossip round + one heartbeat check now
  t  -- submit a demo task through the TaskRouter
  q  -- quit (returns control back to main.py, which then shuts the mesh down)
"""

from __future__ import annotations

import random

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, DataTable
from textual.binding import Binding

from node_management import NodeManager, ALIVE, SUSPECT, DEAD
from gossip_protocol import gossip_once


class ModuleBox(Static):
    """Sidebar item representing a MeshWeaver module."""
    pass


class InfoCard(Static):
    """Top banner widget displaying a summary metric."""
    pass


class Panel(Static):
    """Dashboard widget displaying detailed live state."""
    pass


class MeshWeaverApp(App):

    TITLE = "MeshWeaver Distributed Mesh Computing Framework"
    SUB_TITLE = "Live Node Status, Routing & Security Dashboard"

    CSS = """

    Screen{
        background:#0d1117;
    }

    Header{
        background:#161b22;
        color:white;
    }

    Footer{
        background:#161b22;
        color:white;
    }

    #main{
        layout:horizontal;
        height:100%;
    }

    #sidebar{
        width:30;
        background:#111827;
        border:round cyan;
        padding: 0 1;
    }

    #content{
        width:1fr;
        padding:1;
    }

    ModuleBox{
        margin:0 0 1 0;
        padding:0 1;
        border:round green;
        background:#1b1f27;
        color:white;
    }

    InfoCard{
        width:1fr;
        height:7;
        margin:1;
        padding:1;
        border:round cyan;
        background:#1b1f27;
        color:white;
    }

    Panel{
        width:1fr;
        height:12;
        margin:1;
        padding:1;
        border:round cyan;
        background:#161b22;
        color:white;
    }

    #node_table{
        height:12;
        margin:1;
        border:round cyan;
        background:#161b22;
    }

    """

    BINDINGS = [
        Binding("r", "refresh_now", "Gossip + Heartbeat (R)", key_display="R"),
        Binding("t", "submit_task", "Submit Demo Task (T)", key_display="T"),
        Binding("q", "quit", "Quit", key_display="Q"),
    ]

    def __init__(self, coordinator, manager: NodeManager, router, monitor, refresh_interval: float = 3.0):
        super().__init__()
        self.coordinator = coordinator
        self.manager = manager
        self.router = router
        self.monitor = monitor
        self.refresh_interval = refresh_interval
        self.tasks_routed = 0
        self.last_result = "--"
        self.activity_log: list[str] = []

    # ---------- logging ----------

    def log_event(self, message: str):
        self.activity_log.insert(0, message)
        self.activity_log = self.activity_log[:10]

    # ---------- layout ----------

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):

            with Vertical(id="sidebar"):
                yield Static("🕸️  MODULES ARCHITECTURE\n")
                yield ModuleBox("✅ 1. Async Networking")
                yield ModuleBox("✅ 2. Node Management")
                yield ModuleBox("✅ 3. Task Serialization")
                yield ModuleBox("✅ 4. Remote Task Execution")
                yield ModuleBox("✅ 5. Node Discovery")
                yield ModuleBox("✅ 6. Gossip Protocol")
                yield ModuleBox("✅ 7. Task Routing")
                yield ModuleBox("✅ 8. Heartbeat & Fault Tolerance")
                yield ModuleBox("✅ 9. TLS/SSL Security")
                yield ModuleBox("✅ 10. Rich CLI Dashboard")
                yield ModuleBox("✅ 11. Textual UI")

            with Vertical(id="content"):

                with Horizontal():
                    yield InfoCard(f"🖥️ COORDINATOR\n\n{self.coordinator.node_id}", id="card_self")
                    yield InfoCard("👥 KNOWN PEERS\n\n0", id="card_peers")
                    yield InfoCard("💓 ALIVE / SUSPECT / DEAD\n\n0 / 0 / 0", id="card_health")
                    yield InfoCard("📨 TASKS ROUTED\n\n0", id="card_tasks")

                yield DataTable(id="node_table")

                with Horizontal():
                    yield Panel("📡 DISCOVERY & GOSSIP\n\nWaiting...", id="panel_gossip")
                    yield Panel("🧭 TASK ROUTING\n\nWaiting...", id="panel_routing")

                with Horizontal():
                    yield Panel("🔐 TLS / SIGNING\n\nWaiting...", id="panel_security")
                    yield Panel("📝 ACTIVITY LOG\n\n(empty)", id="panel_log")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#node_table", DataTable)
        table.add_columns("Node ID", "Address", "Status", "CPU %", "RAM %")
        self.update_dashboard()
        self.set_interval(self.refresh_interval, self.periodic_refresh)

    # ---------- refresh ----------

    def update_dashboard(self) -> None:
        peers = self.manager.all_peers(include_dead=True)
        alive = sum(1 for p in peers if p.status == ALIVE)
        suspect = sum(1 for p in peers if p.status == SUSPECT)
        dead = sum(1 for p in peers if p.status == DEAD)

        self.query_one("#card_peers", InfoCard).update(f"👥 KNOWN PEERS\n\n{len(peers)}")
        self.query_one("#card_health", InfoCard).update(
            f"💓 ALIVE / SUSPECT / DEAD\n\n{alive} / {suspect} / {dead}"
        )
        self.query_one("#card_tasks", InfoCard).update(f"📨 TASKS ROUTED\n\n{self.tasks_routed}")

        table = self.query_one("#node_table", DataTable)
        table.clear()
        for p in peers:
            cpu = f"{p.cpu_percent:.1f}" if p.cpu_percent is not None else "--"
            ram = f"{p.ram_percent:.1f}" if p.ram_percent is not None else "--"
            table.add_row(p.node_id, f"{p.host}:{p.port}", p.status, cpu, ram, key=p.node_id)

        gossip_text = "📡 DISCOVERY & GOSSIP\n\n" + "\n".join(
            e for e in self.activity_log if e.startswith(("[gossip]", "[discovery]"))
        )[:600]
        self.query_one("#panel_gossip", Panel).update(gossip_text.strip() or "📡 DISCOVERY & GOSSIP\n\nNo events yet")

        routing_text = "🧭 TASK ROUTING\n\n" + "\n".join(
            e for e in self.activity_log if e.startswith("[routing]")
        )[:600]
        self.query_one("#panel_routing", Panel).update(routing_text.strip() or "🧭 TASK ROUTING\n\nNo tasks routed yet")

        security_text = "🔐 TLS / SIGNING\n\n" + "\n".join(
            e for e in self.activity_log if e.startswith("[security]")
        )[:600]
        self.query_one("#panel_security", Panel).update(security_text.strip() or "🔐 TLS / SIGNING\n\nAll TCP traffic is TLS-encrypted")

        log_text = "\n".join(self.activity_log[:8]) or "(empty)"
        self.query_one("#panel_log", Panel).update(f"📝 ACTIVITY LOG\n\n{log_text}")

    async def periodic_refresh(self) -> None:
        """Runs automatically every `refresh_interval` seconds: one gossip round + one heartbeat check."""
        try:
            replied = await gossip_once(self.coordinator, self.manager, fanout=2)
            self.log_event(f"[gossip] round complete, {replied} peer(s) replied")
        except Exception as e:
            self.log_event(f"[gossip] round failed: {e}")

        if self.monitor:
            await self.monitor.check_once()

        self.update_dashboard()

    # ---------- actions ----------

    async def action_refresh_now(self) -> None:
        await self.periodic_refresh()
        self.notify("Ran gossip round + heartbeat check")

    async def action_submit_task(self) -> None:
        a, b = random.randint(1, 50), random.randint(1, 50)

        def add(x, y):
            return x + y

        try:
            result = await self.router.route_task(add, a, b)
            self.tasks_routed += 1
            self.last_result = str(result)
            self.log_event(f"[routing] add({a}, {b}) -> {result}")
            self.notify(f"Task routed: add({a}, {b}) = {result}")
        except RuntimeError as e:
            self.log_event(f"[routing] failed: {e}")
            self.notify(f"Routing failed: {e}", severity="warning")

        self.update_dashboard()


if __name__ == "__main__":
    # Standalone preview with a fake/empty manager -- for real use this app
    # is launched from main.py with live nodes attached (see STEP 9 there).
    import asyncio

    class _DummyRouter:
        async def route_task(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    class _DummyNode:
        node_id = "coordinator"

    async def _preview():
        mgr = NodeManager("coordinator", "127.0.0.1", 9000)
        mgr.join("worker-1", "127.0.0.1", 9001)
        mgr.update_load("worker-1", cpu_percent=15.0, ram_percent=40.0)
        mgr.join("worker-2", "127.0.0.1", 9002)
        mgr.mark_status("worker-2", SUSPECT)

        app = MeshWeaverApp(_DummyNode(), mgr, _DummyRouter(), monitor=None)
        await app.run_async()

    asyncio.run(_preview())

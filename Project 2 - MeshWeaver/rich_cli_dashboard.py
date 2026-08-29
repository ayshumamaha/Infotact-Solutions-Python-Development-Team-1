
"""
rich_cli_dashboard.py
-----------------------
Module: Rich CLI Dashboard.

Renders the mesh's current state (from a NodeManager) as a formatted
terminal table using the `rich` library -- this is the module main.py's
demo pipeline ends on, the same way PyChronicle's pipeline ends by
launching its Textual UI.

Two entry points:
  - render_snapshot(manager): print one table and return (used at the end
    of a short-lived demo/CLI run).
  - live_dashboard(manager, refresh_fn, interval): an auto-refreshing table
    for long-running processes, calling `refresh_fn` (e.g. a gossip round)
    before each redraw.
"""

import asyncio

from rich.console import Console
from rich.live import Live
from rich.table import Table

from node_management import NodeManager, ALIVE, SUSPECT, DEAD

_STATUS_STYLE = {ALIVE: "green", SUSPECT: "yellow", DEAD: "red"}


def _build_table(manager: NodeManager) -> Table:
    table = Table(title=f"MeshWeaver -- peers known to {manager.self_id}")
    table.add_column("Node ID", style="cyan")
    table.add_column("Address")
    table.add_column("Status")
    table.add_column("CPU %", justify="right")
    table.add_column("RAM %", justify="right")

    for peer in manager.all_peers(include_dead=True):
        style = _STATUS_STYLE.get(peer.status, "white")
        table.add_row(
            peer.node_id,
            f"{peer.host}:{peer.port}",
            f"[{style}]{peer.status}[/{style}]",
            f"{peer.cpu_percent:.1f}" if peer.cpu_percent is not None else "--",
            f"{peer.ram_percent:.1f}" if peer.ram_percent is not None else "--",
        )

    if len(manager) == 0:
        table.add_row("(no peers known yet)", "", "", "", "")
    return table


def render_snapshot(manager: NodeManager, console: Console = None):
    """Print a single table snapshot of the mesh and return."""
    console = console or Console()
    console.print(_build_table(manager))


async def live_dashboard(manager: NodeManager, refresh_fn=None, interval: float = 2.0, rounds: int = 5):
    """
    Auto-refreshing dashboard for `rounds` refreshes (unbounded if rounds is
    None -- intended for a real long-running node). Calls `await refresh_fn()`
    before each redraw if provided, so e.g. a gossip round runs right before
    the table updates.
    """
    console = Console()
    with Live(_build_table(manager), console=console, refresh_per_second=4) as live:
        completed = 0
        while rounds is None or completed < rounds:
            if refresh_fn:
                await refresh_fn()
            live.update(_build_table(manager))
            completed += 1
            await asyncio.sleep(interval)


if __name__ == "__main__":
    manager = NodeManager("coordinator", "127.0.0.1", 9000)
    manager.join("worker-1", "127.0.0.1", 9001)
    manager.join("worker-2", "127.0.0.1", 9002)
    manager.join("worker-3", "127.0.0.1", 9003)
    manager.update_load("worker-1", cpu_percent=12.5, ram_percent=38.0)
    manager.update_load("worker-2", cpu_percent=71.2, ram_percent=55.4)
    manager.mark_status("worker-3", DEAD)

    render_snapshot(manager)

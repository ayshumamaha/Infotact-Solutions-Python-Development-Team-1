from __future__ import annotations

import argparse
import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .node_management import Node, NodeRegistry
from .fault_tolerance import HeartbeatMonitor


console = Console()


def build_table(registry: NodeRegistry) -> Table:
    table = Table(title="MeshWeaver Node Dashboard")
    table.add_column("Node ID")
    table.add_column("Address")
    table.add_column("Status")
    table.add_column("Role")
    table.add_column("Heartbeat Age", justify="right")

    for node in registry.all_nodes():
        role = str(node.metadata.get("role", "unknown"))
        table.add_row(
            node.node_id,
            f"{node.host}:{node.port}",
            node.status.value.upper(),
            role,
            f"{node.age():.1f}s",
        )

    return table


def build_dashboard(registry: NodeRegistry) -> Panel:
    nodes = registry.all_nodes()
    online = len(registry.online_nodes())

    summary = (
        f"[bold]MeshWeaver[/bold]  |  "
        f"Total Nodes: {len(nodes)}  |  "
        f"Online: {online}"
    )

    return Panel(
        build_table(registry),
        title=summary,
        border_style="blue",
    )


def run_demo(refresh: float = 1.0) -> None:
    registry = NodeRegistry()

    registry.register(
        Node(
            "worker-1",
            "127.0.0.1",
            5001,
            {"role": "worker", "cpu": 4},
        )
    )
    registry.register(
        Node(
            "worker-2",
            "127.0.0.1",
            5002,
            {"role": "worker", "cpu": 8},
        )
    )
    registry.register(
        Node(
            "controller",
            "127.0.0.1",
            5000,
            {"role": "controller"},
        )
    )

    monitor = HeartbeatMonitor(
        registry,
        interval=1.0,
        timeout=5.0,
    )
    monitor.start()

    try:
        with Live(
            build_dashboard(registry),
            console=console,
            refresh_per_second=4,
            screen=True,
        ) as live:
            while True:
                # Simulate an active controller and worker.
                registry.heartbeat("controller")
                registry.heartbeat("worker-1")

                # worker-2 intentionally stops heartbeating after startup,
                # allowing the fault-tolerance status to be observed.
                live.update(build_dashboard(registry))
                time.sleep(max(0.1, refresh))
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="MeshWeaver Rich CLI Dashboard"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the live dashboard demonstration",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Dashboard refresh interval in seconds",
    )

    args = parser.parse_args(argv)

    if args.demo:
        run_demo(args.refresh)
        return

    registry = NodeRegistry()
    registry.register(
        Node(
            "local-node",
            metadata={"role": "controller"},
        )
    )

    console.print(build_dashboard(registry))


if __name__ == "__main__":
    main()

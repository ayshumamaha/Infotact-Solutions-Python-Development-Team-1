from __future__ import annotations

import threading
from time import time
from typing import Callable, Optional

from .node_management import Node, NodeRegistry, NodeStatus


class HeartbeatMonitor:
    """
    Background heartbeat monitor.

    Node state:
      ONLINE    -> heartbeat is recent
      SUSPECTED -> heartbeat is older than timeout / 2
      OFFLINE   -> heartbeat is older than timeout
    """

    def __init__(
        self,
        registry: NodeRegistry,
        interval: float = 2.0,
        timeout: float = 6.0,
        on_status_change: Optional[
            Callable[[Node, NodeStatus], None]
        ] = None,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be greater than 0")

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        self.registry = registry
        self.interval = interval
        self.timeout = timeout
        self.on_status_change = on_status_change

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def check_once(self) -> None:
        """Check all registered nodes once."""
        now = time()

        for node in self.registry.all_nodes():
            age = max(
                0.0,
                now - node.last_heartbeat,
            )

            if age > self.timeout:
                new_status = NodeStatus.OFFLINE
            elif age > self.timeout / 2:
                new_status = NodeStatus.SUSPECTED
            else:
                new_status = NodeStatus.ONLINE

            if node.status != new_status:
                self.registry.mark_status(
                    node.node_id,
                    new_status,
                )

                if self.on_status_change:
                    self.on_status_change(
                        node,
                        new_status,
                    )

    def start(self) -> None:
        """Start the background heartbeat monitor."""
        if self.running:
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="meshweaver-heartbeat-monitor",
            daemon=True,
        )

        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval):
            self.check_once()

    def stop(self) -> None:
        """Stop the background monitor."""
        self._stop_event.set()

        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            self._thread.join(
                timeout=self.interval + 1
            )

        self._thread = None

    def __enter__(self) -> "HeartbeatMonitor":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop()


class FaultTolerantNodeRegistry(NodeRegistry):
    """NodeRegistry with a convenient heartbeat monitor factory."""

    def start_monitor(
        self,
        interval: float = 2.0,
        timeout: float = 6.0,
        on_status_change: Optional[
            Callable[[Node, NodeStatus], None]
        ] = None,
    ) -> HeartbeatMonitor:
        monitor = HeartbeatMonitor(
            registry=self,
            interval=interval,
            timeout=timeout,
            on_status_change=on_status_change,
        )

        monitor.start()
        return monitor

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import RLock
from time import time
from typing import Any, Dict, List, Optional


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPECTED = "suspected"


@dataclass
class Node:
    node_id: str
    host: str = "127.0.0.1"
    port: int = 5000
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.ONLINE
    last_heartbeat: float = field(default_factory=time)

    def touch(self) -> None:
        self.last_heartbeat = time()
        self.status = NodeStatus.ONLINE

    def age(self) -> float:
        return max(0.0, time() - self.last_heartbeat)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        data = dict(data)
        data["status"] = NodeStatus(data.get("status", NodeStatus.ONLINE))
        return cls(**data)


class NodeRegistry:
    """Thread-safe in-memory registry for MeshWeaver nodes."""

    def __init__(self) -> None:
        self._nodes: Dict[str, Node] = {}
        self._lock = RLock()

    def register(self, node: Node) -> Node:
        with self._lock:
            existing = self._nodes.get(node.node_id)
            if existing:
                existing.host = node.host
                existing.port = node.port
                existing.metadata.update(node.metadata)
                existing.touch()
                return existing
            self._nodes[node.node_id] = node
            return node

    def unregister(self, node_id: str) -> bool:
        with self._lock:
            return self._nodes.pop(node_id, None) is not None

    def get(self, node_id: str) -> Optional[Node]:
        with self._lock:
            return self._nodes.get(node_id)

    def heartbeat(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.touch()
            return True

    def mark_status(self, node_id: str, status: NodeStatus) -> bool:
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.status = status
            return True

    def all_nodes(self) -> List[Node]:
        with self._lock:
            return list(self._nodes.values())

    def online_nodes(self) -> List[Node]:
        return [n for n in self.all_nodes() if n.status == NodeStatus.ONLINE]

    def remove_stale(self, timeout: float) -> List[Node]:
        removed = []
        with self._lock:
            for node_id, node in list(self._nodes.items()):
                if node.age() > timeout:
                    removed.append(self._nodes.pop(node_id))
        return removed

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        return {n.node_id: n.to_dict() for n in self.all_nodes()}

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Callable, Dict

import cloudpickle


class TaskSerializationError(Exception):
    """Raised when task serialization or deserialization fails."""


class TaskSerializer:
    """Serialize Python callables and arguments for MeshWeaver transport."""

    VERSION = 1

    @classmethod
    def serialize(
        cls,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> bytes:
        if not callable(func):
            raise TaskSerializationError("func must be callable")

        try:
            payload = {
                "version": cls.VERSION,
                "task_id": cls.task_id(func, args, kwargs),
                "function": base64.b64encode(
                    cloudpickle.dumps(func)
                ).decode("ascii"),
                "args": base64.b64encode(
                    cloudpickle.dumps(args)
                ).decode("ascii"),
                "kwargs": base64.b64encode(
                    cloudpickle.dumps(kwargs)
                ).decode("ascii"),
            }

            return json.dumps(
                payload,
                separators=(",", ":"),
            ).encode("utf-8")

        except Exception as exc:
            raise TaskSerializationError(
                f"Unable to serialize task: {exc}"
            ) from exc

    @classmethod
    def deserialize(cls, payload: bytes) -> Dict[str, Any]:
        try:
            data = json.loads(payload.decode("utf-8"))

            if data.get("version") != cls.VERSION:
                raise TaskSerializationError(
                    "Unsupported task payload version"
                )

            func = cloudpickle.loads(
                base64.b64decode(data["function"])
            )
            args = cloudpickle.loads(
                base64.b64decode(data["args"])
            )
            kwargs = cloudpickle.loads(
                base64.b64decode(data["kwargs"])
            )

            if not callable(func):
                raise TaskSerializationError(
                    "Deserialized object is not callable"
                )

            return {
                "task_id": data["task_id"],
                "function": func,
                "args": args,
                "kwargs": kwargs,
            }

        except TaskSerializationError:
            raise
        except Exception as exc:
            raise TaskSerializationError(
                f"Unable to deserialize task: {exc}"
            ) from exc

    @classmethod
    def task_id(
        cls,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
    ) -> str:
        serialized = cloudpickle.dumps(
            (func, args, kwargs)
        )
        return hashlib.sha256(serialized).hexdigest()[:16]

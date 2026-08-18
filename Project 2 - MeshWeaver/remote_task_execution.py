"""
remote_task_execution.py
-------------------------
Module: Remote Task Execution (works with Task Serialization / cloudpickle).

Builds directly on top of async_networking.Node. Responsibilities:
  - Serialize a Python function + its arguments with cloudpickle, so even
    lambdas / local functions / closures can be sent over the wire
    (plain pickle cannot do this reliably).
  - Ship the serialized task to a remote peer over TCP (reliable delivery,
    since losing a task mid-flight is worse than losing a UDP heartbeat).
  - On the receiving side: deserialize, execute, and catch ANY exception
    so one bad task can never crash the node that runs it.
  - Send the result (or the error) back to whichever node submitted it.

Security note: executing arbitrary pickled code from the network is a real
RCE risk. In this project that risk is closed by the TLS/SSL + signature
module later, which restricts execution to signed requests from trusted
mesh peers only. This module intentionally does not try to solve that here.
"""

import asyncio
import logging
import traceback

import cloudpickle

from asyn import Node, Message

logger = logging.getLogger("meshweaver.remote_task_execution")

TASK_SUBMIT = "TASK_SUBMIT"
TASK_RESULT = "TASK_RESULT"


class TaskExecutionError(Exception):
    """Raised locally when a remote task failed on the executing node."""

    def __init__(self, remote_traceback: str):
        self.remote_traceback = remote_traceback
        super().__init__(f"Remote task failed:\n{remote_traceback}")


def serialize_task(func, *args, **kwargs) -> bytes:
    """Package a function + its args/kwargs into transmittable bytes."""
    return cloudpickle.dumps({"func": func, "args": args, "kwargs": kwargs})


def deserialize_task(data: bytes):
    """Reverse of serialize_task. Returns (func, args, kwargs)."""
    obj = cloudpickle.loads(data)
    return obj["func"], obj["args"], obj["kwargs"]


class RemoteExecutor:
    """
    Wraps a Node with task submission + execution behaviour.
    One RemoteExecutor per node — attach it after Node.start().
    """

    def __init__(self, node: Node):
        self.node = node
        self.node.register_handler(TASK_SUBMIT, self._on_task_submit)

    # ---------- submitting side ----------

    async def submit_task(self, host: str, port: int, func, *args, timeout: float = 10.0, **kwargs):
        """
        Send `func(*args, **kwargs)` to a remote node, execute it there,
        and return the result. Raises TaskExecutionError if the remote
        side raised an exception while running the task.
        """
        payload_bytes = serialize_task(func, *args, **kwargs)
        # payload is bytes; Message.payload is a JSON-friendly dict, so we
        # hex-encode the pickle bytes to keep the wire format uniform with
        # the rest of the async_networking messages.
        message = Message(TASK_SUBMIT, self.node.node_id, payload={"task": payload_bytes.hex()})

        reply = await self.node.send_tcp(host, port, message, timeout=timeout)
        if reply is None:
            raise TimeoutError("No response received from remote node")

        status = reply.payload.get("status")
        result_hex = reply.payload.get("result")
        result_bytes = bytes.fromhex(result_hex) if result_hex else None

        if status == "ok":
            return cloudpickle.loads(result_bytes)
        else:
            raise TaskExecutionError(reply.payload.get("error", "unknown error"))

    # ---------- executing side ----------

    async def _on_task_submit(self, message: Message, addr) -> Message:
        """
        Handler invoked automatically (via Node's dispatch) when a
        TASK_SUBMIT message arrives. Deserializes, runs, and replies.
        """
        try:
            task_bytes = bytes.fromhex(message.payload["task"])
            func, args, kwargs = deserialize_task(task_bytes)

            # Support both normal sync functions and coroutine functions.
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            result_bytes = cloudpickle.dumps(result)
            return Message(
                TASK_RESULT,
                self.node.node_id,
                payload={"status": "ok", "result": result_bytes.hex()},
                msg_id=message.msg_id,
            )
        except Exception:
            tb = traceback.format_exc()
            logger.warning("Task execution failed: %s", tb)
            return Message(
                TASK_RESULT,
                self.node.node_id,
                payload={"status": "error", "error": tb},
                msg_id=message.msg_id,
            )


if __name__ == "__main__":
    # Self-contained demo: two nodes, one submits a real math function to
    # the other, the other executes it and returns the actual result.
    def add(a, b):
        return a + b

    def divide_by_zero():
        return 1 / 0  # deliberately triggers the error path

    async def _demo():
        node_a = await Node("node-A", port=9101).start()
        node_b = await Node("node-B", port=9102).start()
        executor_a = RemoteExecutor(node_a)
        RemoteExecutor(node_b)  # node_b just needs the handler registered

        print("Submitting add(7, 5) from node-A to node-B...")
        result = await executor_a.submit_task(node_b.host, node_b.port, add, 7, 5)
        print(f"  -> Result: {result}")

        print("Submitting a task that raises ZeroDivisionError...")
        try:
            await executor_a.submit_task(node_b.host, node_b.port, divide_by_zero)
        except TaskExecutionError as e:
            print(f"  -> Correctly caught remote failure: {e.remote_traceback.splitlines()[-1]}")

        await node_a.stop()
        await node_b.stop()
        print("Nodes shut down cleanly.")

    asyncio.run(_demo())


import json
import os


class StateCapture:
    """Persists execution trace events to a JSON file on disk.
    (Will later be swapped/backed by sqlite_storage.py.)"""

    def __init__(self, storage_path: str = "trace_output.json"):
        self.storage_path = storage_path

    def save(self, events: list):
        with open(self.storage_path, "w") as f:
            json.dump(events, f, indent=2, default=str)

    def load(self) -> list:
        if not os.path.exists(self.storage_path):
            return []
        with open(self.storage_path, "r") as f:
            return json.load(f)


if __name__ == "__main__":
    from execution_tracer import ExecutionTracer

    __tracer__ = ExecutionTracer()

    x = 5
    __tracer__.record(1, "x", x)
    y = x + 2
    __tracer__.record(2, "y", y)

    capture = StateCapture("trace_output.json")
    capture.save(__tracer__.get_events())

    print("Saved events:")
    for event in capture.load():
        print(event)
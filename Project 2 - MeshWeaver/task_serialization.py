
"""
task_serialization.py
----------------------
Module: Task Serialization.

Pulled out into its own module because both remote_task_execution.py and
tls_ssl_security.py need the exact same packaging logic, and the README's
project layout lists it as its own file.

Uses cloudpickle instead of stdlib pickle because cloudpickle can serialize
lambdas, closures, and functions defined interactively/locally -- plain
pickle only handles functions importable by qualified name from a module,
which is too restrictive for a task-submission API.
"""

import cloudpickle


def serialize_task(func, *args, **kwargs) -> bytes:
    """Package a function + its args/kwargs into transmittable bytes."""
    return cloudpickle.dumps({"func": func, "args": args, "kwargs": kwargs})


def deserialize_task(data: bytes):
    """Reverse of serialize_task. Returns (func, args, kwargs)."""
    obj = cloudpickle.loads(data)
    return obj["func"], obj["args"], obj["kwargs"]


def serialize_result(value) -> bytes:
    """Package a return value (or any picklable object) for the wire."""
    return cloudpickle.dumps(value)


def deserialize_result(data: bytes):
    """Reverse of serialize_result."""
    return cloudpickle.loads(data)


if __name__ == "__main__":
    def add(a, b):
        return a + b

    packed = serialize_task(add, 2, 3)
    func, args, kwargs = deserialize_task(packed)
    print(f"Round-tripped task: {func.__name__}(*{args}, **{kwargs}) = {func(*args, **kwargs)}")

    packed_result = serialize_result({"status": "ok", "value": 5})
    print(f"Round-tripped result: {deserialize_result(packed_result)}")

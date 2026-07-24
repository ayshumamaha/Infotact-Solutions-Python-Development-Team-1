class ExecutionTracer:
    """Collects variable assignment events during a program's execution."""

    def __init__(self):
        self.events = []

    def record(self, lineno: int, var_name: str, value):
        self.events.append({
            "lineno": lineno,
            "var": var_name,
            "value": value,
        })

    def get_events(self):
        return self.events

    def clear(self):
        self.events = []


if __name__ == "__main__":
    __tracer__ = ExecutionTracer()

    x = 5
    __tracer__.record(1, "x", x)
    y = x + 2
    __tracer__.record(2, "y", y)

    for event in __tracer__.get_events():
        print(f"Line {event['lineno']}: {event['var']} = {event['value']}")
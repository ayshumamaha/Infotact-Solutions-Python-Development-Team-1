
class WatchManager:
    def __init__(self):
        self.watch_list = set()

    def add_variable(self, var_name: str):
        """Add a variable to the watch list."""
        self.watch_list.add(var_name)

    def remove_variable(self, var_name: str):
        """Remove a variable from the watch list."""
        self.watch_list.discard(var_name)

    def get_watched_values(self, state: dict):
        """
        Return only watched variables from a state snapshot.
        State format: {
            'line': int,
            'delta': {'x': 10, 'y': 20}
        }
        """
        delta = state.get("delta", {})
        watched = {}

        for var in self.watch_list:
            if var in delta:
                watched[var] = delta[var]

        return watched

    def show_watch_list(self):
        return list(self.watch_list)


# Test
if __name__ == "__main__":
    wm = WatchManager()
    wm.add_variable("z")
    wm.add_variable("i")

    sample_state = {
        "line": 6,
        "delta": {"z": 33, "i": 2, "x": 10}
    }

    print("Watch List:", wm.show_watch_list())
    print("Watched Values:", wm.get_watched_values(sample_state))
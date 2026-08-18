
def compress_state(previous_state, current_state):
    """
    Returns only the variables whose values changed. # type: ignore
    """

    delta = {}

    for key, value in current_state.items():
        if key not in previous_state or previous_state[key] != value:
            delta[key] = value

    return delta


if __name__ == "__main__":

    state1 = {
        "a": 10,
        "b": 20,
        "c": 30
    }

    state2 = {
        "a": 10,
        "b": 25,
        "c": 30,
        "d": 40
    }

    print("Previous State:")
    print(state1)

    print("\nCurrent State:")
    print(state2)

    compressed = compress_state(state1, state2)

    print("\nDelta Compression Output:")
    print(compressed)

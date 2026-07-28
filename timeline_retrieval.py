import json
from sqlite_storage import SQLiteStorage


class TimelineRetrieval:

    def __init__(self):

        self.storage = SQLiteStorage()

        self.timeline = self.load()

        self.index = 0

    def load(self):

        rows = self.storage.fetch_all()

        states = []

        for row in rows:

            states.append(json.loads(row[3]))

        return states

    def current_state(self):

        if not self.timeline:
            return None

        return self.timeline[self.index]

    def next_state(self):

        if self.index < len(self.timeline)-1:
            self.index += 1

        return self.current_state()

    def previous_state(self):

        if self.index > 0:
            self.index -= 1

        return self.current_state()

    def show_summary(self):

        print("Total States :", len(self.timeline))

        for i, state in enumerate(self.timeline):

            print(i, state)
# sqlite_storage.py

import sqlite3
import json
from pathlib import Path
from datetime import datetime


class SQLiteStorage:

    def __init__(self, db_name="pychronicle.db"):
        self.db_path = Path(db_name)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            started_at TEXT,
            finished_at TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            event_type TEXT,
            function_name TEXT,
            file_name TEXT,
            line_number INTEGER,
            timestamp TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS states(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            variable_name TEXT,
            variable_type TEXT,
            variable_value TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS watch_variables(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            variable_name TEXT,
            variable_value TEXT,
            timestamp TEXT
        )
        """)

        self.conn.commit()

    # -------------------------------
    # Save execution state
    # -------------------------------

    def save_state(self, line, delta):

        cursor = self.conn.cursor()

        cursor.execute("""
        INSERT INTO events
        (
            session_id,
            event_type,
            function_name,
            file_name,
            line_number,
            timestamp
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            1,
            "LINE",
            "",
            "",
            line,
            datetime.now().isoformat()
        ))

        event_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO states
        (
            event_id,
            variable_name,
            variable_type,
            variable_value
        )
        VALUES(?,?,?,?)
        """,
        (
            event_id,
            "STATE",
            "JSON",
            json.dumps({
                "line": line,
                "delta": delta
            })
        ))

        self.conn.commit()

    # -------------------------------
    # Fetch timeline
    # -------------------------------

    def fetch_all(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        SELECT
            states.id,
            events.line_number,
            events.timestamp,
            states.variable_value
        FROM states
        JOIN events
        ON states.event_id = events.id
        ORDER BY states.id
        """)

        return cursor.fetchall()

    # -------------------------------

    def close(self):
        self.conn.close()


if __name__ == "__main__":

    db = SQLiteStorage()

    db.save_state(
        1,
        {
            "x": 10,
            "y": 20
        }
    )

    print(db.fetch_all())

    db.close()

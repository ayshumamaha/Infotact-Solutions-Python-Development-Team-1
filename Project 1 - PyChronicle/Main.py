# main.py
# PyChronicle Integration 

import os
import sys

from ast_parser import scan_file
from AST_Rewriter import rewrite_code
from execution_tracer import ExecutionTracer
from state_capture import StateCapture
from Delta_com import compress_state
from watch_variables import WatchManager
from sqlite_storage import SQLiteStorage
from timeline_retrieval import TimelineRetrieval
from textual_ui import PyChronicleApp


def main():

    print("=" * 60)
    print("        PyChronicle Time Travel Debugger")
    print("=" * 60)

    target_file = os.path.join(
        os.path.dirname(__file__),
        "target_script.py")

    if not os.path.exists(target_file):
        print("Target Script Not Found!")
        return

    
    # STEP 1 : AST Parser
    
    print("\nSTEP 1 : Parsing Source Code")

    assignments = scan_file(target_file)

    for line, variable in assignments:
        print(f"Line {line} --> {variable}")

    
    # STEP 2 : AST Rewriter
    
    print("\nSTEP 2 : Rewriting Code")

    with open(target_file, "r") as file:
        source = file.read()

    rewritten = rewrite_code(source)

    rewritten_file = "rewritten_target.py"

    with open(rewritten_file, "w") as file:
        file.write(rewritten)

    print("Rewritten file saved.")


    # STEP 3 : Execution Tracer
   
    print("\nSTEP 3 : Execution Tracing")

    tracer = ExecutionTracer()

    previous_state = {}
    current_state = {}

    for line, variable in assignments:

        value = f"value_of_{variable}"

        current_state[variable] = value

        tracer.record(
            line,
            variable,
            value
        )

    events = tracer.get_events()

    print("\nRecorded Events")

    for event in events:
        print(event)

    
    # STEP 4 : Delta Compression
    

    print("\nSTEP 4 : Delta Compression")

    delta = compress_state(
        previous_state,
        current_state
    )

    print(delta)

    
    # STEP 5 : JSON State Capture
    

    print("\nSTEP 5 : Saving JSON")

    capture = StateCapture()

    capture.save(events)

    print("trace_output.json created.")

    
    # STEP 6 : SQLite Storage
   

    print("\nSTEP 6 : Saving SQLite")

    storage = SQLiteStorage()

    storage.save_state(
        line=1,
        delta=delta
    )

    print("Saved into SQLite Database.")

    
    # STEP 7 : Watch Variables
    

    print("\nSTEP 7 : Watch Variables")

    watcher = WatchManager()

    for _, variable in assignments:
        watcher.add_variable(variable)

    watched = watcher.get_watched_values(
        {
            "line": 1,
            "delta": delta
        }
    )

    print("Watch List")

    print(watcher.show_watch_list())

    print("\nWatched Values")

    print(watched)

    
    # STEP 8 : Timeline Retrieval
    

    print("\nSTEP 8 : Timeline")

    timeline = TimelineRetrieval()

    timeline.show_summary()

    current = timeline.current_state()

    print("\nCurrent State")

    print(current)

    print("\nNext State")

    print(timeline.next_state())

    print("\nPrevious State")

    print(timeline.previous_state())

    storage.close()

    print("\n===================================")
    print("Backend Pipeline Executed Successfully")
    print("===================================")

    
    # STEP 9 : Textual UI Dashboard Launch
    

    print("\n🚀 Launching Interactive Textual UI Dashboard...")
    
    app = PyChronicleApp(target_file=target_file, db_file="pychronicle.db")
    app.run()


if __name__ == "__main__":
    main()

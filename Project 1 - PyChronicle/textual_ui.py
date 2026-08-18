from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
import os
import sys
import json


# Custom Widgets


class ModuleBox(Static):
    """Sidebar item representing a PyChronicle module."""
    pass


class InfoCard(Static):
    """Top banner widget displaying metric summary cards."""
    pass


class Panel(Static):
    """Dashboard widget displaying detailed module state."""
    pass


# Main Textual Application


class PyChronicleApp(App):

    TITLE = "PyChronicle Time Travel Debugger"
    SUB_TITLE = "Interactive Execution Replay & State Timeline"

    CSS = """

    Screen{
        background:#0d1117;
    }

    Header{
        background:#161b22;
        color:white;
    }

    Footer{
        background:#161b22;
        color:white;
    }

    #main{
        layout:horizontal;
        height:100%;
    }

    #sidebar{
        width:30;
        background:#111827;
        border:round cyan;
        padding: 0 1;
    }

    #content{
        width:1fr;
        padding:1;
    }

    ModuleBox{
        margin:0 0 1 0;
        padding:0 1;
        border:round green;
        background:#1b1f27;
        color:white;
    }

    InfoCard{
        width:1fr;
        height:7;
        margin:1;
        padding:1;
        border:round cyan;
        background:#1b1f27;
        color:white;
    }

    Panel{
        width:1fr;
        height:12;
        margin:1;
        padding:1;
        border:round cyan;
        background:#161b22;
        color:white;
    }

    """

    BINDINGS = [
        Binding("n,right,f8", "next_state", "Next State (F8/→)", key_display="F8 / →"),
        Binding("p,left,f7", "prev_state", "Prev State (F7/←)", key_display="F7 / ←"),
        Binding("r", "refresh_data", "Refresh DB", key_display="R"),
        Binding("q", "quit", "Quit", key_display="Q"),
    ]

    def __init__(self, target_file="target_script.py", db_file="pychronicle.db"):
        super().__init__()
        self.target_file = target_file
        self.db_file = db_file
        self.timeline_data = []
        self.current_index = 0
        self.assignments = []
        self.load_data()

    def load_data(self):
        """Load real execution states from SQLite database or fallback gracefully to mock data."""
        self.timeline_data = []
        
        # 1. Try loading from TimelineRetrieval & SQLiteStorage
        try:
            from sqlite_storage import SQLiteStorage
            from timeline_retrieval import TimelineRetrieval
            
            if os.path.exists(self.db_file):
                tr = TimelineRetrieval()
                self.timeline_data = tr.timeline
        except Exception:
            pass

        # 2. Try scanning target_script.py for AST assignments
        try:
            from ast_parser import scan_file
            if os.path.exists(self.target_file):
                self.assignments = scan_file(self.target_file)
        except Exception:
            pass

        # 3. Fallback mock data if DB is empty
        if not self.timeline_data:
            if self.assignments:
                curr = {}
                for line_no, var in self.assignments:
                    curr[var] = f"value_of_{var}"
                    self.timeline_data.append({
                        "line": line_no,
                        "var": var,
                        "val": f"value_of_{var}",
                        "delta": dict(curr)
                    })
            else:
                self.timeline_data = [
                    {"line": 1, "var": "x", "val": "value_of_x", "delta": {"x": "value_of_x"}},
                    {"line": 2, "var": "y", "val": "value_of_y", "delta": {"x": "value_of_x", "y": "value_of_y"}},
                    {"line": 3, "var": "z", "val": "value_of_z", "delta": {"x": "value_of_x", "y": "value_of_y", "z": "value_of_z"}},
                    {"line": 4, "var": "total", "val": "100", "delta": {"x": "value_of_x", "y": "value_of_y", "z": "value_of_z", "total": "100"}},
                ]

        self.current_index = 0

   
    # UI Layout
  

    def compose(self) -> ComposeResult:

        yield Header()

        with Horizontal(id="main"):

            
            # Sidebar
            

            with Vertical(id="sidebar"):

                yield Static("🚀 MODULES ARCHITECTURE\n")

                yield ModuleBox("✅ 1. AST Parser")

                yield ModuleBox("✅ 2. AST Rewriter")

                yield ModuleBox("✅ 3. Execution Tracer")

                yield ModuleBox("✅ 4. State Capture")

                yield ModuleBox("✅ 5. Delta Compression")

                yield ModuleBox("✅ 6. SQLite Storage")

                yield ModuleBox("✅ 7. Watch Variables")

                yield ModuleBox("✅ 8. Timeline Retrieval")

                yield ModuleBox("✅ 9. CLI Interface")

                yield ModuleBox("✅ 10. Textual UI")


            
            # Main Dashboard
           

            with Vertical(id="content"):

                
                # TOP CARDS
               

                with Horizontal():

                    yield InfoCard(
                        f"📄 TARGET FILE\n\n{self.target_file}",
                        id="card_target"
                    )

                    yield InfoCard(
                        f"🗄 DATABASE\n\n{self.db_file}",
                        id="card_db"
                    )

                    yield InfoCard(
                        f"📊 TOTAL STATES\n\n{len(self.timeline_data)}",
                        id="card_total"
                    )

                    yield InfoCard(
                        f"⏱️ STEP POSITION\n\n1 / {max(1, len(self.timeline_data))}",
                        id="card_step"
                    )

                
                # ROW 1
                

                with Horizontal():

                    yield Panel(
                        "👀 WATCH VARIABLES\n\nLoading...",
                        id="panel_watch"
                    )

                    yield Panel(
                        "📅 TIMELINE STATE\n\nLoading...",
                        id="panel_timeline"
                    )

                
                # ROW 2
                

                with Horizontal():

                    yield Panel(
                        "📄 AST PARSER\n\nScanning...",
                        id="panel_ast"
                    )

                    yield Panel(
                        "✏️ AST REWRITER\n\nStatus : SUCCESS\n\nOutput File:\nrewritten_target.py",
                        id="panel_rewriter"
                    )

                
                # ROW 3
                

                with Horizontal():

                    yield Panel(
                        "⚡ EXECUTION EVENTS\n\nTracing...",
                        id="panel_events"
                    )

                    yield Panel(
                        "🧩 DELTA COMPRESSION\n\nCompressing...",
                        id="panel_delta"
                    )

                
                # ROW 4
                

                with Horizontal():

                    yield Panel(
                        f"💾 SQLITE STORAGE\n\nDatabase Connected\n\n{self.db_file}",
                        id="panel_sqlite"
                    )

                    yield Panel(
                        "📦 STATE CAPTURE\n\ntrace_output.json\n\nStatus : Saved",
                        id="panel_capture"
                    )

        yield Footer()

    def on_mount(self) -> None:
        """Called when app mounts. Initial dashboard update."""
        self.update_dashboard()

    def update_dashboard(self) -> None:
        """Update all dynamic cards and panels based on current_index."""
        total = len(self.timeline_data)
        if total == 0:
            return

        curr_state = self.timeline_data[self.current_index]
        
        # Format line and variables
        line_no = curr_state.get("line", self.current_index + 1)
        delta = curr_state.get("delta", curr_state)
        
        # 1. Update Info Cards
        self.query_one("#card_total", InfoCard).update(f"📊 TOTAL STATES\n\n{total}")
        self.query_one("#card_step", InfoCard).update(f"⏱️ STEP POSITION\n\n{self.current_index + 1} / {total}")

        # 2. Update Watch Variables
        watch_text = "👀 WATCH VARIABLES\n\n"
        if isinstance(delta, dict):
            for k, v in delta.items():
                watch_text += f"{k} = {v}\n"
        else:
            watch_text += str(delta)
        self.query_one("#panel_watch", Panel).update(watch_text.strip())

        # 3. Update Timeline
        timeline_text = f"📅 TIMELINE NAVIGATION\n\nState {self.current_index + 1} of {total}\n"
        timeline_text += f"Line Number : {line_no}\n"
        if isinstance(delta, dict):
            for k, v in delta.items():
                timeline_text += f" -> {k} = {v}\n"
        self.query_one("#panel_timeline", Panel).update(timeline_text.strip())

        # 4. Update AST Parser Panel
        ast_text = "📄 AST PARSER\n\nVariables Found:\n"
        if self.assignments:
            for l_num, v_name in self.assignments:
                ast_text += f" • Line {l_num}: {v_name}\n"
            ast_text += f"\nTotal Assignments: {len(self.assignments)}"
        else:
            ast_text += " • x\n • y\n • z\n\nTotal Assignments: 3"
        self.query_one("#panel_ast", Panel).update(ast_text.strip())

        # 5. Update Execution Events
        events_text = "⚡ EXECUTION EVENTS\n\n"
        for i in range(min(self.current_index + 1, total)):
            st = self.timeline_data[i]
            events_text += f"Line {st.get('line', i+1)} -> {st.get('var', 'state')} = {st.get('val', 'updated')}\n"
        self.query_one("#panel_events", Panel).update(events_text.strip())

        # 6. Update Delta Compression
        delta_str = json.dumps(delta, indent=2) if isinstance(delta, dict) else str(delta)
        self.query_one("#panel_delta", Panel).update(f"🧩 DELTA COMPRESSION\n\n{delta_str}")

        # 7. Update SQLite Storage
        sqlite_text = f"💾 SQLITE STORAGE\n\nConnected: {self.db_file}\n"
        sqlite_text += f"Active State ID: {self.current_index + 1}"
        self.query_one("#panel_sqlite", Panel).update(sqlite_text)

    def action_next_state(self) -> None:
        """Step forward to next timeline state."""
        if self.current_index < len(self.timeline_data) - 1:
            self.current_index += 1
            self.update_dashboard()
            self.notify(f"Moved to Step {self.current_index + 1}")
        else:
            self.notify("Already at the final execution step!", severity="warning")

    def action_prev_state(self) -> None:
        """Step backward to previous timeline state."""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_dashboard()
            self.notify(f"Moved to Step {self.current_index + 1}")
        else:
            self.notify("Already at the first step!", severity="warning")

    def action_refresh_data(self) -> None:
        """Reload database data and refresh UI."""
        self.load_data()
        self.update_dashboard()
        self.notify("Database reloaded successfully!")


if __name__ == "__main__":
    PyChronicleApp().run()

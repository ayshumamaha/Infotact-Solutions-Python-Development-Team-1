import typer
from Main import main
from timeline_retrieval import TimelineRetrieval
from textual_ui import PyChronicleApp

app = typer.Typer(help="PyChronicle CLI")


@app.command()
def run():
    """Run PyChronicle execution pipeline"""
    main()


@app.command()
def timeline():
    """Show execution timeline in terminal text"""
    tr = TimelineRetrieval()
    tr.show_summary()


@app.command()
def ui():
    """Launch interactive Textual Terminal UI dashboard"""
    PyChronicleApp().run()


if __name__ == "__main__":
    app()
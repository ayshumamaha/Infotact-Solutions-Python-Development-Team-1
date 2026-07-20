# Infotact-Solutions-Python-Development-Team-1
# PyChronicle – A Time-Travel Debugger for Python

## Overview

PyChronicle is a Python-based time-travel debugging framework that enables developers to inspect program execution history by recording execution states and allowing navigation through previously executed code. The project combines Abstract Syntax Tree (AST) rewriting, execution tracing, state capture, delta compression, and persistent storage to provide a lightweight debugging solution.

This project was developed as part of a Python Development Internship.

---

## Features

- Abstract Syntax Tree (AST) Parsing
- Hook Injection using AST Rewriting
- Execution Tracing
- Program State Capture
- SQLite-based State Storage
- Delta Compression for Efficient Storage
- Timeline Retrieval
- Watch Variable Monitoring
- Text-based User Interface
- Command Line Interface (CLI)
- Modular Architecture

---

## Project Structure

```
PyChronicle/
│
├── ast_parser.py
├── ast_rewriter.py
├── execution_tracer.py
├── state_capture.py
├── sqlite_storage.py
├── delta_compression.py
├── timeline_retrieval.py
├── watch_variables.py
├── textual_ui.py
├── cli.py
├── main.py
├── requirements.txt
└── README.md
```

---

## Technologies Used

- Python 3.11+
- AST Module
- SQLite3
- Click / Typer
- Textual
- Logging
- Git
- GitHub

---

## Installation

Clone the repository:

```bash
git clone https://github.com/username/PyChronicle.git
```

Move into the project directory:

```bash
cd PyChronicle
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

---

## Workflow

```
Python Source Code
        │
        ▼
AST Parser
        │
        ▼
AST Rewriter
        │
        ▼
Execution Tracer
        │
        ▼
State Capture
        │
        ▼
Delta Compression
        │
        ▼
SQLite Storage
        │
        ▼
Timeline Retrieval
        │
        ▼
Textual UI / CLI
```

---

## Future Enhancements

- Graphical User Interface
- Breakpoint Management
- Reverse Debugging
- Multi-file Project Support
- Performance Optimization
- Export Debug Sessions

---

## Contributors

- M. Ayshwarya
- Yash Waroshe
- Sunny Kumar
- Koushik Kumar Supakar

---

## License

This project was developed for educational and internship purposes.

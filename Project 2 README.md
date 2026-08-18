# Infotact-Solutions-Python-Development-Team-1
# MeshWeaver – A Distributed Mesh Computing Framework

## Overview

MeshWeaver is a Python-based distributed computing framework designed to execute computational tasks across interconnected nodes in a peer-to-peer environment. The project demonstrates distributed task execution, node discovery, secure communication, task routing, and fault tolerance using a modular architecture.

This project was developed as part of a Python Development Internship.

---

## Features

- Asynchronous Networking
- Node Management
- Remote Task Execution
- Task Serialization
- Kademlia-based Node Discovery
- Gossip Protocol
- Task Routing
- Heartbeat Monitoring
- Fault Tolerance
- TLS/SSL Secure Communication
- Rich CLI Dashboard

---

## Project Structure

```
MeshWeaver/
│
├── async_networking.py
├── node_management.py
├── task_serialization.py
├── remote_task_execution.py
├── kademlia_node_discovery.py
├── gossip_protocol.py
├── task_routing.py
├── heartbeat_fault_tolerance.py
├── tls_ssl_security.py
├── rich_cli_dashboard.py
├── main.py
├── requirements.txt
└── README.md
```

---

## Technologies Used

- Python 3.11+
- asyncio
- socket
- ssl
- cloudpickle
- Rich
- Logging
- Git
- GitHub

---

## Installation

Clone the repository:

```bash
git clone https://github.com/username/MeshWeaver.git
```

Move into the project directory:

```bash
cd MeshWeaver
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
Client Task
      │
      ▼
Task Serialization
      │
      ▼
Node Discovery
      │
      ▼
Task Routing
      │
      ▼
Remote Execution
      │
      ▼
Result Collection
      │
      ▼
CLI Dashboard
```

---

## Future Enhancements

- Dynamic Load Balancing
- Web-based Monitoring Dashboard
- Distributed File Storage
- Containerized Deployment
- Cloud Integration
- Advanced Scheduling Algorithms

---

## Contributors

- M. Ayshwarya
- Yash Waroshe
- Sunny Kumar
- Koushik Kumar Supakar

---

## License

This project was developed for educational and internship purposes.

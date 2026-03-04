# SRE LangGraph MCP Agent

An AI-powered **Site Reliability Engineering (SRE) investigation agent** that analyzes logs, metrics, and operational runbooks using **LangGraph, MCP servers, and LLM reasoning**.

This system simulates a real production environment where logs and metrics are continuously generated and the agent autonomously investigates system issues.

---

# Architecture Overview

The system follows a **multi-component architecture**.

```
User
 │
 ▼
Streamlit Frontend
(frontend_mcp.py)
 │
 ▼
FastAPI Backend
(fastapibackend.py)
 │
 ▼
LangGraph Agent
(langgraph_mcp_backend1.py)
 │
 ▼
MCP Client
 │
 ├── Logs MCP Server
 ├── Metrics MCP Server
 └── RAG MCP Server
```

---

# Project Structure

```
.
├── app
│   └── mcp_servers
│       ├── logs_server.py
│       ├── metrics_server.py
│       └── rag_server.py
│
├── data
│   └── telemetry / logs / metrics files
│
├── fastapibackend.py
├── frontend_mcp.py
├── langgraph_mcp_backend1.py
├── log_generator.py
├── metrics_generator.py
├── requirements.txt
└── .gitignore
```

---

# Features

* AI-powered incident investigation
* Streaming LLM responses
* Log analysis tools
* Error spike detection
* Metrics analysis
* Runbook-based remediation suggestions
* Thread-based chat sessions
* Real-time telemetry simulation

---

# Tech Stack

### Backend

* FastAPI
* LangGraph
* LangChain
* MCP (Model Context Protocol)
* SQLite (chat state storage)

### Frontend

* Streamlit

### LLM

* Groq API (`openai/gpt-oss-120b`)

### Other Libraries

* aiosqlite
* pydantic
* python threading

---

# System Workflow

1. User sends a query via the Streamlit UI.
2. The request is sent to the FastAPI backend.
3. FastAPI forwards the request to the LangGraph agent.
4. The agent determines which tools should be used.
5. MCP servers execute the requested tools.
6. Tool results are returned to the agent.
7. The LLM interprets the results.
8. The final response is streamed back to the user.

---

# Example Queries

```
Show logs for payment-api
Detect error spike in order-api
Check service health for user-api
What errors occurred in the last 10 minutes?
Suggest remediation for database connection timeout
```

---

# Installation

Clone the repository:

```
git clone https://github.com/Saichand4510/SRE-agent.git
cd SRE-agent
```

Create a virtual environment:

```
python -m venv agent
```

Activate the environment.

### Windows

```
agent\Scripts\activate
```

### Linux / Mac

```
source agent/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_api_key
```

---

# Running the Backend

Start the FastAPI server:

```
uvicorn fastapibackend:app --reload
```

When the backend starts it automatically:

* initializes the LangGraph agent
* starts the log generator thread
* starts the metrics generator thread
* launches MCP servers

---

# Running the Frontend

Start the Streamlit UI:

```
streamlit run frontend_mcp.py
```

Then open the browser URL shown in the terminal.

---

# Streaming Architecture

The system streams responses using **FastAPI StreamingResponse**.

```
User Query
   │
   ▼
LangGraph Agent
   │
   ▼
Tool Execution Events
   │
   ▼
LLM Token Streaming
   │
   ▼
Streamlit UI Updates
```

This allows the user to see responses **in real-time**.

---

# System Design Explanation

This project implements an **AI-powered SRE investigation agent** capable of analyzing operational telemetry.

The system separates responsibilities across multiple layers to ensure modularity and scalability.

---

## API Layer (FastAPI)

FastAPI acts as the **entry point** of the system.

Responsibilities:

* manage chat threads
* stream responses
* coordinate LangGraph execution
* start telemetry generators

FastAPI uses **asynchronous request handling** to support multiple users.

---

## Agent Layer (LangGraph)

LangGraph acts as the **reasoning engine**.

The agent:

* interprets user queries
* selects appropriate tools
* performs multi-step investigations
* combines tool outputs into a final explanation

Investigation flow:

```
User Query
   │
   ▼
LLM Reasoning
   │
   ▼
Tool Selection
   │
   ▼
Tool Execution
   │
   ▼
Result Analysis
   │
   ▼
Final Response
```

---

## MCP Tool Layer

The agent interacts with system tools via **Model Context Protocol (MCP)**.

Each MCP server provides specialized capabilities.

### Logs MCP Server

Provides log investigation features:

* log retrieval
* error pattern detection
* spike detection
* time window filtering

---

### Metrics MCP Server

Provides performance insights:

* latency analysis
* CPU usage
* memory usage
* service health checks

---

### RAG MCP Server

Provides remediation suggestions based on operational runbooks.

This allows the system to recommend:

* root causes
* mitigation strategies
* operational procedures

---

# Telemetry Simulation

To simulate a real production environment, background generators produce system signals.

### Log Generator

Continuously produces logs such as:

* INFO events
* WARN events
* ERROR spikes

---

### Metrics Generator

Continuously generates metrics:

* latency
* error rate
* CPU usage
* memory usage

---

# Concurrency Model

The system combines multiple concurrency techniques.

### Async API Server

FastAPI handles multiple requests concurrently using an **async event loop**.

---

### Background Threads

Two threads simulate telemetry:

* log generator thread
* metrics generator thread

---

### MCP Child Processes

Each MCP server runs as a **separate process** launched by the MCP client.

This provides:

* isolation
* parallel tool execution
* modular architecture

---

# Deployment

This project can be deployed on:

* Render
* Railway
* AWS
* Google Cloud

Recommended configuration:

```
WEB_CONCURRENCY=1
```

---

# Author

**Saichand Linga**

---

# Notes

This project demonstrates:

* AI agent architecture
* observability tooling
* distributed tool orchestration
* streaming AI interfaces
* production-style system design

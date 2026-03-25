# SRE LangGraph MCP Agent

An AI-powered **Site Reliability Engineering (SRE) investigation agent**
that analyzes logs, metrics, and operational runbooks using **LangGraph,
MCP servers, and LLM reasoning**.

This system simulates a real production environment where logs and
metrics are continuously generated and the agent autonomously
investigates system issues.

------------------------------------------------------------------------

# Architecture Overview

The system follows a **multi-component production-grade architecture**.


```
User
 │
 ▼
React frontend
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
│   └──  logs / metrics files
│
├── fastapibackend.py
├── Dockerfile
├── langgraph_mcp_backend1.py
├── log_generator.py
├── metrics_generator.py
├── requirements.txt
└── .gitignore
```

---

------------------------------------------------------------------------


# Features

-   AI-powered incident investigation
-   Streaming LLM responses
-   Log analysis tools
-   Error spike detection
-   Metrics analysis
-   Runbook-based remediation suggestions
-   JWT Authentication (Access + Refresh Tokens)
-   PostgreSQL storage
-   Structured logging and error handling
-   Rate limiting per user (API protection)
-   Dockerized deployment (Render)

------------------------------------------------------------------------

# Tech Stack

Backend: FastAPI, LangGraph, LangChain, MCP, PostgreSQL\
Frontend: React\
LLM: Groq (gpt-oss-120b)

------------------------------------------------------------------------

# System Workflow

1.  User sends a query via React UI\
2.  JWT authentication\
3.  Rate limiter validation\
4.  FastAPI processes request\
5.  LangGraph performs reasoning\
6.  MCP tools execute\
7.  LLM generates response\
8.  Response is streamed back

------------------------------------------------------------------------

# Authentication Flow

User Login → Access + Refresh Token → Authenticated Requests → Token
Refresh

------------------------------------------------------------------------

# Rate Limiting

Per-user rate limiting ensures fair usage, prevents abuse, and controls
LLM cost.

------------------------------------------------------------------------

# System Design Explanation

This project implements an **AI-powered SRE investigation agent**
capable of analyzing operational telemetry.

------------------------------------------------------------------------

## API Layer (FastAPI)

-   authentication & authorization\
-   rate limiting\
-   request handling\
-   streaming responses\
-   LangGraph coordination

------------------------------------------------------------------------

## Agent Layer (LangGraph)

-   reasoning engine\
-   tool selection\
-   multi-step investigation\
-   response synthesis

------------------------------------------------------------------------

## MCP Tool Layer

### Logs MCP Server

-   log retrieval\
-   error detection\
-   spike detection

### Metrics MCP Server

-   latency\
-   CPU usage\
-   memory usage

### RAG MCP Server

-   remediation suggestions\
-   runbook-based insights

------------------------------------------------------------------------

# Telemetry Simulation

### Log Generator

-   INFO / WARN / ERROR logs

### Metrics Generator

-   latency\
-   error rate\
-   CPU\
-   memory

------------------------------------------------------------------------

# Concurrency Model

-   async FastAPI event loop\
-   background threads\
-   MCP processes for isolation

------------------------------------------------------------------------

# Installation

git clone https://github.com/Saichand4510/SRE-agent.git cd SRE-agent
python -m venv agent

### Activate

Windows: agent`\Scripts`{=tex}`\activate`{=tex}

Linux / Mac: source agent/bin/activate

### Install

pip install -r requirements.txt

------------------------------------------------------------------------

# Environment Variables

GROQ_API_KEY=your_api_key DATABASE_URL=your_postgresql_url
JWT_SECRET=your_secret_key

------------------------------------------------------------------------

# Running the Backend

uvicorn fastapibackend:app --reload

------------------------------------------------------------------------

# Running the Frontend

npm install npm start

------------------------------------------------------------------------

# Deployment

Deployed on **Render using Docker**.

-   containerized application\
-   environment variable management\
-   scalable deployment

------------------------------------------------------------------------

# Future Enhancements

## Redis Caching

-   cache responses\
-   reduce database load\
-   improve latency

## LLM Efficiency

-   reduce token usage\
-   optimize prompts\
-   support self-hosted models (vLLM)

------------------------------------------------------------------------

# Author

Saichand Linga

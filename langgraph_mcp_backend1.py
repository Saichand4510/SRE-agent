from typing import TypedDict, Annotated, List
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
)
from langchain_core.tools import BaseTool

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq

load_dotenv()

# ============================================================
# 1️⃣ LLM (SECURE)
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
     model_name="llama-3.3-70b-versatile",   # 🔥 best on Groq
    temperature=0.2,  # 🔥 VERY IMPORTANT
    max_tokens=1500,                       
    api_key=GROQ_API_KEY,
)

# ============================================================
# 2️⃣ MCP CLIENT
# ============================================================

client = MultiServerMCPClient(
    {
        "metrics": {
            "command": "python",
            "args": ["app/mcp_servers/metrics_server.py"],
            "transport": "stdio",
        },
        "logs": {
            "command": "python",
            "args": ["app/mcp_servers/logs_server.py"],
            "transport": "stdio",
        },
        "rag": {
            "command": "python",
            "args": ["app/mcp_servers/rag_server.py"],
            "transport": "stdio",
        },
    }
)

# ============================================================
# 3️⃣ GLOBAL RUNTIME STATE (initialized at startup)
# ============================================================

tools: List[BaseTool] = []
llm_with_tools = llm
chatbot = None

# ============================================================
# 4️⃣ STATE
# ============================================================

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# ============================================================
# 5️⃣ CHAT NODE
# ============================================================

async def chat_node(state: ChatState):
    messages = state["messages"]

    system_message = SystemMessage(
        content='''
You are an expert SRE (Site Reliability Engineering) investigation agent.

Your goal is to diagnose production issues using available tools and provide clear, actionable insights.

========================
CORE PRINCIPLES
========================
- Be precise, structured, and concise
- Do not guess or hallucinate system data
- Always prefer tool outputs over assumptions
- Think step-by-step before answering

========================
TOOL USAGE RULES
========================
- ALWAYS use tools for:
  - logs, errors, metrics, health, spikes, or system state
- NEVER fabricate:
  - logs, metrics, error counts, timestamps, or system data
- You MAY call multiple tools if needed for investigation
- If tool output is empty or inconclusive, explicitly say so

========================
WHEN TO USE WHICH TOOL
========================
- Logs / errors → analyze_logs, get_logs_in_time_range
- Time-based queries → get_logs_in_time_range
- Error patterns → detect_error_patterns, detect_error_patterns_in_time_range
- Error spikes / anomalies → detect_error_spike
- Service health → service_health_summary
- Metrics (CPU, latency, memory) → metrics tools
- Root cause / remediation → runbook (RAG tool)

========================
DECISION LOGIC
========================
- If the question is factual about system state → use tools
- If the question is explanatory ("why", "how to fix") → use RAG tool
- If investigation requires multiple steps → call tools sequentially
- If no tool is needed → answer directly

========================
RESPONSE FORMAT (MANDATORY)
========================
1. Direct Answer (1–2 lines)
2. Key Findings (bullet points from tool data)
3. Recommended Actions (if applicable)

========================
STYLE GUIDELINES
========================
- Be clear and professional
- Use bullet points where helpful
- Avoid unnecessary verbosity
- Do not include internal reasoning or chain-of-thought

========================
FAILURE HANDLING
========================
- If no data is found → say: "No relevant data found in the selected range"
- If uncertain → say what is missing and suggest next step
- Never produce misleading conclusions

========================
EXAMPLES
========================

Bad:
"There might be an issue with the database."

Good:
"Database latency is elevated (156ms), but error rate is low (0.9%). No critical failures detected."

========================

Always base your answers strictly on tool outputs when available.'''
    )

    response = await llm_with_tools.ainvoke(
        [system_message] + messages
    )

    return {"messages": [response]}

# ============================================================
# 6️⃣ CHATBOT FACTORY (CALLED BY FASTAPI STARTUP)
# ============================================================

async def create_chatbot(checkpointer):
    """
    Initializes:
    - MCP tools
    - LLM tool binding
    - SQLite checkpointer
    - LangGraph
    """

    global tools, llm_with_tools,  chatbot

    # ✅ Load MCP tools
    try:
        tools = await client.get_tools()
    except Exception:
        tools = []

    # ✅ Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
   
    # ✅ Build graph
    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_edge(START, "chat_node")

    if tools:
        tool_node = ToolNode(tools)
        graph.add_node("tools", tool_node)
        graph.add_conditional_edges("chat_node", tools_condition)
        graph.add_edge("tools", "chat_node")
    else:
        graph.add_edge("chat_node", END)

    chatbot = graph.compile(checkpointer=checkpointer)
    return chatbot


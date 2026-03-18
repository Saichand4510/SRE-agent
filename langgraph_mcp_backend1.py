from typing import TypedDict, Annotated, List
import os
import aiosqlite

from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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
    model_name="openai/gpt-oss-120b",
    temperature=0.7,
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
checkpointer: AsyncSqliteSaver | None = None
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
        content="""
You are an expert SRE investigation agent.

TOOL USAGE POLICY:

- Use analyze_logs → when user asks for logs or errors.
- Use get_logs_in_time_range → when user mentions time window.
- Use detect_error_patterns → when user asks for dominant/repeated errors.
- Use service_health_summary → when user asks if a service is healthy, degraded, overall status, or general health check.
- Use metrics tools → when user asks about latency, CPU, memory, or performance numbers.
- Use runbook (rag) → when user asks for root cause, explanation, or remediation steps.
- Use detect_error_spike → when user asks about spike, sudden increase,
  burst, surge, anomaly, incident, or unusual rise in errors.
- Use detect_error_patterns_in_time_range → when user asks for dominant/repeated errors in a time window

RULES:

- Be decisive.
- Prefer tools over guessing.
- Use multiple tools if investigation requires.
- Always ground answers in tool outputs.
"""
    )

    response = await llm_with_tools.ainvoke(
        [system_message] + messages
    )

    return {"messages": [response]}

# ============================================================
# 6️⃣ CHATBOT FACTORY (CALLED BY FASTAPI STARTUP)
# ============================================================

async def create_chatbot():
    """
    Initializes:
    - MCP tools
    - LLM tool binding
    - SQLite checkpointer
    - LangGraph
    """

    global tools, llm_with_tools, checkpointer, chatbot

    # ✅ Load MCP tools
    try:
        tools = await client.get_tools()
    except Exception:
        tools = []

    # ✅ Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # ✅ Initialize SQLite checkpointer
    conn = await aiosqlite.connect(database="chatbot.db")
    checkpointer = AsyncSqliteSaver(conn)

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


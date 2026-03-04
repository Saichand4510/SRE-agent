from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag-server")

# ✅ robust absolute path
BASE_DIR = Path(__file__).resolve().parents[2]
RUNBOOK_PATH = BASE_DIR / "data" / "runbooks" / "database_timeout.md"


@mcp.tool()
def retrieve_runbook(query: str) -> str:
    """Retrieve relevant runbook context."""
    with open(RUNBOOK_PATH, "r", encoding="utf-8") as f:
        return f.read()[:1000]


if __name__ == "__main__":
    mcp.run()
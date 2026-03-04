import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("metrics-server")

# ✅ robust absolute path (works in MCP subprocess)
BASE_DIR = Path(__file__).resolve().parents[2]
METRICS_PATH = BASE_DIR / "data" / "metrics" / "system_metrics.json"


# =====================================================
# 🔥 SMART SERVICE MATCHER (same as logs server)
# =====================================================
def _match_service(metric_service: str, query_service: str) -> bool:
    """
    Flexible service matching:
    - exact match
    - contains match
    - ignores hyphens and spaces

    Examples that will match:
    user → user-api
    user api → user-api
    USER → user-api
    """
    ms = metric_service.lower().replace("-", "").replace(" ", "").strip()
    qs = query_service.lower().replace("-", "").replace(" ", "").strip()
    return qs in ms or ms in qs


# =====================================================
# 🧠 HELPER — get latest metrics safely
# =====================================================
def _get_latest_metrics(entry):
    """
    Supports both:
    - snapshot dict
    - time-series list (returns latest point)
    """
    if isinstance(entry, list):
        return entry[-1] if entry else {}
    return entry


# =====================================================
# 🟢 TOOL 1 — GET METRICS
# =====================================================
@mcp.tool()
def get_metrics(service: str) -> dict:
    """Fetch latest system metrics for a service."""

    with open(METRICS_PATH, "r") as f:
        db = json.load(f)

    matched_key = None
    for key in db.keys():
        if _match_service(key, service):
            matched_key = key
            break

    if not matched_key:
        return {"error": f"No metrics found for service '{service}'"}

    latest_metrics = _get_latest_metrics(db[matched_key])

    return {
        "service": matched_key,
        "metrics": latest_metrics,
    }


# =====================================================
# 🟡 TOOL 2 — SERVICE HEALTH
# =====================================================
@mcp.tool()
def service_health_summary(service: str) -> dict:
    """
    Provide overall health assessment of a service based on latest metrics.
    """

    with open(METRICS_PATH, "r") as f:
        db = json.load(f)

    matched_key = None
    for key in db.keys():
        if _match_service(key, service):
            matched_key = key
            break

    if not matched_key:
        return {"error": f"No metrics found for service '{service}'"}

    metrics = _get_latest_metrics(db[matched_key])

    issues = []

    if metrics.get("latency_ms", 0) > 500:
        issues.append("High latency")

    if metrics.get("error_rate", 0) > 0.05:
        issues.append("Elevated error rate")

    if metrics.get("cpu_usage", 0) > 80:
        issues.append("High CPU usage")

    if metrics.get("memory_usage", 0) > 80:
        issues.append("High memory usage")

    health_status = "healthy" if not issues else "degraded"

    return {
        "service": matched_key,
        "health_status": health_status,
        "issues_detected": issues,
        "metrics": metrics,
    }


if __name__ == "__main__":
    mcp.run()
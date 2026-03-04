import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta, timezone

mcp = FastMCP("logs-server")

# ✅ robust absolute path
BASE_DIR = Path(__file__).resolve().parents[2]
LOGS_PATH = BASE_DIR / "data" / "logs" / "api_logs.json"
def _parse_iso(ts: str) -> datetime:
    """Parse ISO timestamp and normalize to naive datetime."""
    dt = datetime.fromisoformat(ts)
    return dt.replace(tzinfo=None)

# =====================================================
# 🔥 SMART SERVICE MATCHER (VERY IMPORTANT)
# =====================================================
def _match_service(log_service: str, query_service: str) -> bool:
    """
    Flexible service matching:
    - exact match
    - contains match
    - ignores hyphens and spaces
    """
    ls = log_service.lower().replace("-", "").replace(" ", "").strip()
    qs = query_service.lower().replace("-", "").replace(" ", "").strip()
    return qs in ls or ls in qs


# =====================================================
# 🟢 TOOL 1 — FULL LOG ANALYSIS
# =====================================================
@mcp.tool()
def analyze_logs(service: str) -> dict:
    """
    Retrieve and analyze ALL available logs for a given service.
    """

    with open(LOGS_PATH, "r") as f:
        logs = json.load(f)

    service_logs = [
        l for l in logs
        if _match_service(l["service"], service)
    ]

    errors = [
        l["message"]
        for l in service_logs
        if l["level"] == "ERROR"
    ]

    return {
        "total_logs": len(service_logs),
        "error_count": len(errors),
        "top_error": errors[0] if errors else "none",
        "logs": service_logs,
    }


# =====================================================
# 🟡 TOOL 2 — TIME RANGE FILTER
# =====================================================
@mcp.tool()
def get_logs_in_time_range(service: str, start_time: str, end_time: str) -> dict:
    """
    Retrieve logs for a service within a specific ISO time range.
    Time format: YYYY-MM-DDTHH:MM:SS
    """

    with open(LOGS_PATH, "r") as f:
        logs = json.load(f)

    try:
        start_dt = _parse_iso(start_time)
        end_dt = _parse_iso(end_time)
    except Exception:
        return {
            "error": "Invalid time format. Use ISO format YYYY-MM-DDTHH:MM:SS"
        }

    filtered_logs = []

    for log in logs:
        if not _match_service(log["service"], service):
            continue

        try:
            log_time = _parse_iso(log["timestamp"])
        except Exception:
            continue

        if start_dt <= log_time <= end_dt:
            filtered_logs.append(log)

    errors = [
        l["message"]
        for l in filtered_logs
        if l["level"] == "ERROR"
    ]

    return {
        "time_window": {
            "start": start_time,
            "end": end_time,
        },
        "total_logs": len(filtered_logs),
        "error_count": len(errors),
        "top_error": errors[0] if errors else "none",
        "logs": filtered_logs,
    }


# =====================================================
# 🔴 TOOL 3 — ERROR PATTERN DETECTOR
# =====================================================
@mcp.tool()
def detect_error_patterns(service: str) -> dict:
    """
    Detect dominant error patterns for a service.
    """

    with open(LOGS_PATH, "r") as f:
        logs = json.load(f)

    service_errors = [
        l for l in logs
        if _match_service(l["service"], service)
        and l["level"] == "ERROR"
    ]

    if not service_errors:
        return {"message": "No errors found."}

    freq = {}
    for log in service_errors:
        msg = log["message"]
        freq[msg] = freq.get(msg, 0) + 1

    top_error = max(freq, key=freq.get)

    return {
        "total_errors": len(service_errors),
        "unique_error_types": len(freq),
        "most_frequent_error": top_error,
        "frequency_map": freq,
    }
@mcp.tool()
def detect_error_patterns_in_time_range(
    service: str,
    start_time: str,
    end_time: str
) -> dict:
    """
    Detect dominant error patterns within a specific time window.
    Useful for incident window analysis.
    """

    with open(LOGS_PATH, "r") as f:
        logs = json.load(f)

    try:
        
        start_dt = _parse_iso(start_time)
        end_dt = _parse_iso(end_time)
    except Exception:
        return {"error": "Invalid time format. Use ISO format"}

    window_errors = []

    for log in logs:
        if not _match_service(log["service"], service):
            continue

        if log["level"] != "ERROR":
            continue

        try:
            log_time = _parse_iso(log["timestamp"])
        except Exception:
            continue

        if start_dt <= log_time <= end_dt:
            window_errors.append(log)

    if not window_errors:
        return {"message": "No errors found in time window"}

    freq = {}
    for log in window_errors:
        msg = log["message"]
        freq[msg] = freq.get(msg, 0) + 1

    top_error = max(freq, key=freq.get)

    return {
        "time_window": {"start": start_time, "end": end_time},
        "total_errors": len(window_errors),
        "unique_error_types": len(freq),
        "most_frequent_error": top_error,
        "frequency_map": freq,
    }
@mcp.tool()
def detect_error_spike(
    service: str,
    window_minutes: int = 5,
    threshold: int = 3
) -> dict:
    """
    Detect sudden burst of errors in recent time window.
    Useful for incident early warning.
    """

    

    with open(LOGS_PATH, "r") as f:
        logs = json.load(f)

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)

    error_count = 0
    spike_logs = []

    for log in logs:
        if not _match_service(log["service"], service):
            continue

        if log["level"] != "ERROR":
            continue

        try:
            log_time = _parse_iso(log["timestamp"])
        except Exception:
            continue

        if log_time >= window_start:
            error_count += 1
            spike_logs.append(log)

    is_spike = error_count >= threshold

    return {
        "service": service,
        "window_minutes": window_minutes,
        "error_count_in_window": error_count,
        "threshold": threshold,
        "spike_detected": is_spike,
        "recent_errors": spike_logs,
    }
if __name__ == "__main__":
    mcp.run()
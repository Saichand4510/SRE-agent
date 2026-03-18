import json
import random
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_PATH = BASE_DIR / "data" / "logs" / "api_logs.json"
# =====================================================
# 🔥 SPIKE CONTROL (NEW)
# =====================================================
SPIKE_ACTIVE = False
SPIKE_END_TIME = 0
SPIKE_PROBABILITY = 0.08  # chance to start spike
SPIKE_DURATION_SEC = 30   # how long spike lasts
# ✅ ensure directory exists (important)
LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)

services = ["payment-api", "user-api", "order-api"]
MAX_LOGS = 100  # rolling window size

messages = {
    "INFO": [
        "Request processed successfully",
        "Service heartbeat OK",
        "Operation completed",
    ],
    "WARN": [
        "High response latency detected",
        "Connection pool nearing capacity",
        "Retrying failed request",
    ],
    "ERROR": [
        "Database connection timeout",
        "Connection pool exhausted",
        "Failed to reserve inventory",
        "User session validation failed",
    ],
}

def maybe_trigger_spike():
    """Randomly start or stop spike mode."""
    global SPIKE_ACTIVE, SPIKE_END_TIME

    now = time.time()

    # end spike if expired
    if SPIKE_ACTIVE and now > SPIKE_END_TIME:
        SPIKE_ACTIVE = False
       # print("✅ Spike ended — back to normal")

    # randomly start spike
    if not SPIKE_ACTIVE and random.random() < SPIKE_PROBABILITY:
        SPIKE_ACTIVE = True
        SPIKE_END_TIME = now + SPIKE_DURATION_SEC
       # print("🚨 ERROR SPIKE STARTED!")
def generate_log():
    """Generate normal or spike log."""

    # 🔥 spike-aware weights
    if SPIKE_ACTIVE:
        weights = [0.3, 0.2, 0.5]  # heavy errors during spike
    else:
        weights = [0.7, 0.2, 0.1]  # normal traffic

    level = random.choices(
        ["INFO", "WARN", "ERROR"],
        weights=weights,
    )[0]

    service = random.choice(services)

    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "service": service,
        "level": level,
        "message": random.choice(messages[level]),
    }


def safe_load_logs():
    """Robust JSON loader for streaming file."""
    if not LOGS_PATH.exists():
        return []

    try:
        with open(LOGS_PATH, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except json.JSONDecodeError:
        #print("⚠️ Corrupted JSON detected — resetting")
        return []


def main():
    #print("🚀 Log generator started...")

    while True:
        maybe_trigger_spike()
        log_entry = generate_log()

        # ✅ SAFE LOAD
        data = safe_load_logs()

        # append new log
        data.append(log_entry)

        # ✅ ROLLING WINDOW
        if len(data) > MAX_LOGS:
            data = data[-MAX_LOGS:]
            #print("♻️ Rolling window applied")

        # ✅ SAFE WRITE
        with open(LOGS_PATH, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()

        #print("Added log:", log_entry)

        time.sleep(3)


if __name__ == "__main__":
    main()
import json
import random
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
METRICS_PATH = BASE_DIR / "data" / "metrics" / "system_metrics.json"

METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)

services = ["payment-api", "user-api", "order-api"]
MAX_POINTS = 60  # keep last 60 datapoints


def generate_metrics(service):
    """Simulate realistic fluctuating metrics."""

    base_latency = {
        "payment-api": 200,
        "user-api": 120,
        "order-api": 180,
    }[service]

    return {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "latency_ms": max(50, int(random.gauss(base_latency, 40))),
        "error_rate": round(max(0, random.gauss(0.02, 0.02)), 3),
        "cpu_usage": min(100, max(10, int(random.gauss(50, 15)))),
        "memory_usage": min(100, max(20, int(random.gauss(60, 10)))),
    }


def safe_load():
    if not METRICS_PATH.exists():
        return {}

    try:
        with open(METRICS_PATH, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        return {}


def main():
    print("📊 Metrics generator started...")

    while True:
        data = safe_load()

        for svc in services:
            data.setdefault(svc, [])
            data[svc].append(generate_metrics(svc))

            # rolling window
            if len(data[svc]) > MAX_POINTS:
                data[svc] = data[svc][-MAX_POINTS:]

        with open(METRICS_PATH, "w") as f:
            json.dump(data, f, indent=2)

        print("Updated metrics")
        time.sleep(10)


if __name__ == "__main__":
    main()
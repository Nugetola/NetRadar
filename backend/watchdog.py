"""Run separately (Windows Task Scheduler/service) to detect a silent backend failure."""
import os
import sys
import time
import urllib.request

url = os.getenv("NETRADAR_HEALTH_URL", "http://127.0.0.1:8000/health")
while True:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status != 200: raise OSError(f"health endpoint returned {response.status}")
    except OSError as exc:
        print(f"NetRadar watchdog failure: {exc}", file=sys.stderr, flush=True)
        # A service manager can restart this process and/or act on its exit code.
        sys.exit(1)
    time.sleep(int(os.getenv("WATCHDOG_INTERVAL_SECONDS", "60")))

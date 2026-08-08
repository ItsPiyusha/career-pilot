"""
scheduler.py — runs scraper.py once per day at a configured time.
Run this in the background: python scheduler.py &
It logs each run to scheduler.log
"""

import time
import subprocess
import sys
import os
from datetime import datetime

# ── CONFIG ──────────────────────────────────────
RUN_AT_HOUR   = 8      # 24h clock — 8 = 8 AM local time
RUN_AT_MINUTE = 0
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler.log")
SCRAPER  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.py")
# ────────────────────────────────────────────────


def log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]  {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_scraper():
    log("▶  Starting scraper...")
    result = subprocess.run(
        [sys.executable, SCRAPER],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        log("   " + line)
    if result.returncode != 0:
        log(f"⚠️  Scraper exited with code {result.returncode}")
        for line in result.stderr.strip().splitlines():
            log("   ERR: " + line)
    else:
        log("✅  Scraper completed successfully")


def seconds_until_next_run() -> float:
    now = datetime.now()
    target = now.replace(hour=RUN_AT_HOUR, minute=RUN_AT_MINUTE, second=0, microsecond=0)
    if target <= now:
        # Already past today's slot — schedule for tomorrow
        from datetime import timedelta
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    log(f"🗓️  Scheduler started — will run scraper daily at {RUN_AT_HOUR:02d}:{RUN_AT_MINUTE:02d}")
    log(f"   Scraper: {SCRAPER}")
    log(f"   Log:     {LOG_FILE}")

    while True:
        wait = seconds_until_next_run()
        next_run = datetime.now()
        log(f"⏳  Next run in {wait/3600:.1f}h  (sleeping...)")
        time.sleep(wait)
        run_scraper()


if __name__ == "__main__":
    main()

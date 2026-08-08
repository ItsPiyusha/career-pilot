#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run.sh  —  Microsoft SDE Job Scraper
# Usage:
#   chmod +x run.sh   (first time only)
#   ./run.sh          (scrape now)
#   ./run.sh --daemon (run daily at 8 AM in background)
# ─────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Virtual env setup (only runs if venv doesn't exist) ──
if [ ! -d "$SCRIPT_DIR/venv" ]; then
  echo "📦  Creating virtual environment..."
  python3 -m venv "$SCRIPT_DIR/venv"
fi

source "$SCRIPT_DIR/venv/bin/activate"

# ── 2. Install dependencies ──
pip install -q requests

# ── 3. Run ──
if [ "$1" == "--daemon" ]; then
  echo "🗓  Starting daily scheduler (runs at 8 AM)..."
  nohup python "$SCRIPT_DIR/scheduler.py" > "$SCRIPT_DIR/scheduler.log" 2>&1 &
  echo "✅  Scheduler running in background (PID $!)"
  echo "    Logs: $SCRIPT_DIR/scheduler.log"
  echo "    Stop it: kill $!"
else
  echo "🚀  Running scraper now..."
  python "$SCRIPT_DIR/scraper.py"
  echo ""
  echo "✅  Done. Open ms_job_tracker.html in Chrome and drop microsoft_jobs.csv onto it."
  # Auto-open the dashboard in Chrome
  open -a "Google Chrome" "$SCRIPT_DIR/ms_job_tracker.html" 2>/dev/null || \
  open "$SCRIPT_DIR/ms_job_tracker.html"
fi

# Microsoft SDE Job Tracker

Automatically scrapes Microsoft Careers daily for SDE roles and tracks your application status.

## Files

| File | Purpose |
|------|---------|
| `scraper.py` | Fetches jobs from Microsoft Careers API |
| `scheduler.py` | Runs scraper daily at 8 AM (local machine) |
| `run.sh` | One-command setup + run (macOS/Linux) |
| `ms_job_tracker.html` | Visual dashboard — open in browser |
| `microsoft_jobs.csv` | All jobs found (auto-updated by CI) |
| `new_jobs.csv` | Only jobs new since last run |
| `seen_ids.json` | Deduplication state — don't delete |

## Quick Start (Local)

```bash
# First time
chmod +x run.sh
./run.sh

# Daily (background daemon)
./run.sh --daemon
```

## GitHub Actions (Automated)

The workflow in `.github/workflows/scrape.yml` runs every day at 8 AM UTC:
- Scrapes Microsoft Careers for SDE roles
- Commits fresh `microsoft_jobs.csv` + `new_jobs.csv` to this repo
- Shows a summary in the Actions tab

### Setup
1. Push this repo to GitHub
2. Go to **Actions** tab → enable workflows
3. That's it — it runs automatically every day

### Manual trigger
Go to **Actions** → **Microsoft Jobs Scraper** → **Run workflow**

### Optional: Email alerts
Add these secrets under **Settings → Secrets → Actions**:
- `GMAIL_USER` — your Gmail address
- `GMAIL_PASS` — Gmail App Password (not your regular password)

Then uncomment the email step in `scrape.yml`.

## Dashboard Usage

1. Open `ms_job_tracker.html` in Chrome
2. Drop `microsoft_jobs.csv` onto it
3. Use **Open**, **Applied**, **Skip** buttons per job
4. Statuses are saved in browser — safe to re-drop CSV anytime

## Customising Keywords

Edit `scraper.py` line:
```python
KEYWORDS = ["software engineer", "SDE", "software development engineer"]
```

"""
Microsoft Careers Scraper — SDE roles, all locations
Uses Microsoft's Eightfold SmartApply public API directly.
Outputs: microsoft_jobs.csv (all), new_jobs.csv (only new since last run)
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

# ── CONFIG ───────────────────────────────────────────────────
KEYWORDS      = ["software engineer", "SDE", "software development engineer"]
PAGE_SIZE     = 25
DELAY         = 1.5
OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "microsoft_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "new_jobs.csv")

BASE_URL = "https://microsoft.eightfold.ai/api/apply/v2/jobs"
HEADERS  = {
    "Accept":          "application/json",
    "Content-Type":    "application/json",
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":         "https://jobs.careers.microsoft.com/",
}


def fetch_page(keyword: str, start: int) -> dict:
    params = {
        "domain":   "microsoft.com",
        "hl":       "en",
        "start":    start,
        "num":      PAGE_SIZE,
        "q":        keyword,
        "pid":      "",
        "triggerGoButton": "false",
    }
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
    print(f"  [{resp.status_code}] start={start} | {resp.url[:100]}")
    resp.raise_for_status()
    return resp.json()


def scrape_keyword(keyword: str) -> list:
    all_jobs = []
    start = 0
    print(f"\n🔍  '{keyword}'")

    while True:
        try:
            data = fetch_page(keyword, start)
        except requests.RequestException as e:
            print(f"  Request failed: {e}")
            break

        positions = data.get("positions", [])
        total     = data.get("count", 0)

        if not positions:
            print(f"  No results at start={start} (total={total})")
            break

        all_jobs.extend(positions)
        print(f"  Got {len(positions)} jobs (total={total}, fetched={len(all_jobs)})")

        if len(all_jobs) >= total:
            break
        start += PAGE_SIZE
        time.sleep(DELAY)

    return all_jobs


def normalise(job: dict) -> dict:
    jid = str(job.get("id", ""))
    return {
        "jobId":       jid,
        "title":       job.get("name", "").strip(),
        "location":    job.get("location", "").strip(),
        "postingDate": (job.get("t_update", "") or "")[:10],
        "url":         f"https://jobs.careers.microsoft.com/global/en/job/{jid}/",
        "scraped_at":  datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set) -> None:
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(sorted(ids), f)


def write_csv(jobs: list, path: str) -> None:
    if not jobs:
        return
    fields = ["jobId", "title", "location", "postingDate", "url", "scraped_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)


def main() -> None:
    print("=" * 55)
    print("  Microsoft Careers Scraper — SDE, All Locations")
    print("=" * 55)

    raw: list = []
    for kw in KEYWORDS:
        raw.extend(scrape_keyword(kw))

    # Deduplicate within this run
    seen_this_run: dict = {}
    for job in raw:
        jid = str(job.get("id", ""))
        if jid and jid not in seen_this_run:
            seen_this_run[jid] = normalise(job)

    all_this_run = list(seen_this_run.values())
    print(f"\n✅  Unique jobs found: {len(all_this_run)}")

    seen_before = load_seen_ids()
    new_jobs = [j for j in all_this_run if j["jobId"] not in seen_before]
    print(f"🆕  New since last run: {len(new_jobs)}")

    write_csv(all_this_run, ALL_JOBS_CSV)
    write_csv(new_jobs, NEW_JOBS_CSV)
    save_seen_ids(seen_before | {j["jobId"] for j in all_this_run})

    print(f"\n📄  All jobs  → {ALL_JOBS_CSV}")
    print(f"📄  New jobs  → {NEW_JOBS_CSV}")

    if new_jobs:
        print("\n── New Jobs Preview ──────────────────────────────")
        for j in new_jobs[:10]:
            print(f"  [{j['postingDate']}]  {j['title']}")
            print(f"    📍 {j['location']}")
            print(f"    🔗 {j['url']}\n")
        if len(new_jobs) > 10:
            print(f"  ... and {len(new_jobs) - 10} more in new_jobs.csv")
    else:
        print("\n  No new postings since last run.")


if __name__ == "__main__":
    main()

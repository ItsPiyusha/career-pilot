"""
Microsoft Careers Scraper — SDE roles, all locations
Strategy: Use LinkedIn + Indeed via JobSpy, filtered to Microsoft only.
This works from GitHub Actions since it queries job aggregators, not MS directly.
Outputs: microsoft_jobs.csv (all), new_jobs.csv (only new since last run)
"""

import csv
import json
import os
from datetime import datetime, timezone

from jobspy import scrape_jobs

# ── CONFIG ───────────────────────────────────────────────────
SEARCH_TERM   = "software engineer Microsoft"
RESULTS       = 100
HOURS_OLD     = 72       # only jobs posted in last 3 days
OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "microsoft_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "new_jobs.csv")


def fetch_jobs() -> list:
    print("🔍  Searching LinkedIn + Indeed for Microsoft SDE roles...")
    jobs = scrape_jobs(
        site_name=["linkedin", "indeed"],
        search_term=SEARCH_TERM,
        results_wanted=RESULTS,
        hours_old=HOURS_OLD,
        country_indeed="worldwide",
        linkedin_fetch_description=False,
        verbose=1,
    )
    print(f"  Raw results: {len(jobs)}")

    # Filter to Microsoft only
    ms_jobs = jobs[
        jobs["company"].str.lower().str.contains("microsoft", na=False)
    ]
    print(f"  Microsoft only: {len(ms_jobs)}")
    return ms_jobs.to_dict("records")


def normalise(job: dict) -> dict:
    # Use job_url as unique ID since aggregators don't expose internal IDs
    url  = str(job.get("job_url", ""))
    jid  = url.split("/")[-1].split("?")[0] or url[-40:]
    return {
        "jobId":       jid,
        "title":       str(job.get("title", "")).strip(),
        "location":    str(job.get("location", "")).strip(),
        "postingDate": str(job.get("date_posted", ""))[:10],
        "url":         url,
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

    raw = fetch_jobs()
    normalised = [normalise(j) for j in raw]

    # Deduplicate
    seen_this_run: dict = {}
    for j in normalised:
        if j["jobId"] and j["jobId"] not in seen_this_run:
            seen_this_run[j["jobId"]] = j

    all_this_run = list(seen_this_run.values())
    print(f"\n✅  Unique jobs: {len(all_this_run)}")

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

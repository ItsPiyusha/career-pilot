"""
Microsoft Careers Scraper — SDE roles, all locations
Polls the internal search API used by careers.microsoft.com
Deduplicates across runs using seen_ids.json
Outputs: microsoft_jobs.csv (all), new_jobs.csv (only new since last run)
"""

import requests
import json
import csv
import time
import os
from datetime import datetime

# ──────────────────────────────────────────────
# CONFIG — edit these
# ──────────────────────────────────────────────
KEYWORDS = ["software engineer", "SDE", "software development engineer"]
LOCATION  = ""          # "" = worldwide; e.g. "India" or "United States"
PAGE_SIZE = 20          # max per page
DELAY     = 1.5         # seconds between requests (be polite)
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "microsoft_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "new_jobs.csv")

# ──────────────────────────────────────────────
# REQUEST SETUP
# ──────────────────────────────────────────────
BASE_URL    = "https://jobs.careers.microsoft.com/global/en/search"
WARMUP_URL  = "https://careers.microsoft.com/us/en/search-results"


def make_session() -> requests.Session:
    """
    Build a session that mimics a real browser.
    The warmup GET establishes cookies (MSCC consent, MUID, etc.)
    that the search API requires — without them you get 403.
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    # Warm up: load the search page so MS sets session cookies
    try:
        s.get(WARMUP_URL, timeout=15)
        time.sleep(1.0)
    except requests.RequestException:
        pass   # continue anyway; cookies might not be strictly required
    # Now switch to API headers
    s.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Referer": WARMUP_URL,
        "Origin": "https://careers.microsoft.com",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })
    return s


SESSION = None   # lazily initialised once


def fetch_page(keyword: str, location: str, page: int) -> dict:
    global SESSION
    if SESSION is None:
        SESSION = make_session()
    params = {
        "q":    keyword,
        "lc":   location,
        "l":    "en_us",
        "pg":   page,
        "pgSz": PAGE_SIZE,
        "o":    "Relevance",
        "flt":  "true",
    }
    resp = SESSION.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extract_jobs(data: dict) -> tuple[list, int]:
    result = data.get("operationResult", {}).get("result", {})
    jobs   = result.get("jobs", [])
    total  = result.get("totalJobs", 0)
    return jobs, total


def scrape_keyword(keyword: str, location: str) -> list:
    all_jobs = []
    page = 1
    print(f"\n🔍  Searching: '{keyword}' | location: '{location or 'All'}'")
    while True:
        try:
            data = fetch_page(keyword, location, page)
        except requests.RequestException as e:
            print(f"  ⚠️  Request failed on page {page}: {e}")
            break

        jobs, total = extract_jobs(data)
        if not jobs:
            break

        all_jobs.extend(jobs)
        print(f"  Page {page}: {len(jobs)} jobs (total reported: {total})")

        if len(all_jobs) >= total:
            break
        page += 1
        time.sleep(DELAY)

    return all_jobs


def normalise(job: dict) -> dict:
    jid = str(job.get("jobId", ""))
    return {
        "jobId":       jid,
        "title":       job.get("title", "").strip(),
        "location":    job.get("location", "").strip(),
        "postingDate": job.get("postingDate", "")[:10],   # YYYY-MM-DD
        "url":         f"https://jobs.careers.microsoft.com/global/en/job/{jid}/",
        "scraped_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(sorted(ids), f)


def write_csv(jobs: list, path: str, mode: str = "w"):
    if not jobs:
        return
    fields = ["jobId", "title", "location", "postingDate", "url", "scraped_at"]
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if mode == "w" or not file_exists:
            writer.writeheader()
        writer.writerows(jobs)


def main():
    print("=" * 55)
    print("  Microsoft Careers Scraper — SDE, All Locations")
    print("=" * 55)

    # 1. Scrape all keywords
    raw: list = []
    for kw in KEYWORDS:
        raw.extend(scrape_keyword(kw, LOCATION))

    # 2. Deduplicate within this run
    seen_this_run = {}
    for job in raw:
        jid = str(job.get("jobId", ""))
        if jid and jid not in seen_this_run:
            seen_this_run[jid] = normalise(job)

    all_this_run = list(seen_this_run.values())
    print(f"\n✅  Unique jobs found this run: {len(all_this_run)}")

    # 3. Compare against previous runs
    seen_before = load_seen_ids()
    new_jobs = [j for j in all_this_run if j["jobId"] not in seen_before]
    print(f"🆕  New since last run: {len(new_jobs)}")

    # 4. Persist
    write_csv(all_this_run, ALL_JOBS_CSV, mode="w")
    write_csv(new_jobs,     NEW_JOBS_CSV, mode="w")

    updated_ids = seen_before | {j["jobId"] for j in all_this_run}
    save_seen_ids(updated_ids)

    print(f"\n📄  All jobs  → {ALL_JOBS_CSV}")
    print(f"📄  New jobs  → {NEW_JOBS_CSV}")
    print(f"🗂️   Seen IDs  → {SEEN_IDS_FILE}  ({len(updated_ids)} total tracked)")

    # 5. Preview new jobs in terminal
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

"""
Microsoft Careers Scraper — SDE roles, all locations
Uses Playwright APIRequestContext to call the search API directly.
Outputs: microsoft_jobs.csv (all), new_jobs.csv (only new since last run)
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

# ── CONFIG ───────────────────────────────────────────────────
KEYWORDS      = ["software engineer", "SDE", "software development engineer"]
LOCATION      = ""
PAGE_SIZE     = 20
DELAY         = 2.0
OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "microsoft_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "new_jobs.csv")

BASE_URL = "https://jobs.careers.microsoft.com/global/en/search"


def fetch_jobs_page(request_ctx, keyword: str, location: str, pg: int) -> dict:
    params = {
        "q":    keyword,
        "lc":   location,
        "l":    "en_us",
        "pg":   str(pg),
        "pgSz": str(PAGE_SIZE),
        "o":    "Relevance",
        "flt":  "true",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}?{query}"
    print(f"  GET {url[:100]}")

    response = request_ctx.get(
        url,
        headers={
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer":         "https://careers.microsoft.com/",
            "Origin":          "https://careers.microsoft.com",
            "sec-fetch-dest":  "empty",
            "sec-fetch-mode":  "cors",
            "sec-fetch-site":  "same-site",
        },
    )
    print(f"  Status: {response.status}")
    print(f"  Content-Type: {response.headers.get('content-type', 'unknown')}")

    if response.status == 200:
        try:
            data = response.json()
            jobs = data.get("operationResult", {}).get("result", {}).get("jobs", [])
            print(f"  Jobs in response: {len(jobs)}")
            return data
        except ValueError as e:
            print(f"  JSON parse error: {e}")
            print(f"  Body (first 300): {response.text()[:300]}")
    else:
        print(f"  Body (first 300): {response.text()[:300]}")

    return {}


def scrape_keyword(request_ctx, keyword: str, location: str) -> list:
    all_jobs = []
    pg = 1
    print(f"\n🔍  Searching: '{keyword}' | location: '{location or 'All'}'")

    while True:
        data   = fetch_jobs_page(request_ctx, keyword, location, pg)
        result = data.get("operationResult", {}).get("result", {})
        jobs   = result.get("jobs", [])
        total  = result.get("totalJobs", 0)

        if not jobs:
            print(f"  No jobs on page {pg} (total reported: {total})")
            break

        all_jobs.extend(jobs)
        print(f"  Page {pg}: {len(jobs)} jobs (total: {total})")

        if len(all_jobs) >= total:
            break
        pg += 1
        time.sleep(DELAY)

    return all_jobs


def normalise(job: dict) -> dict:
    jid = str(job.get("jobId", ""))
    return {
        "jobId":       jid,
        "title":       job.get("title", "").strip(),
        "location":    job.get("location", "").strip(),
        "postingDate": job.get("postingDate", "")[:10],
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

    with sync_playwright() as p:
        # Use APIRequestContext — direct HTTP calls, no browser rendering
        request_ctx = p.request.new_context(
            base_url="https://jobs.careers.microsoft.com",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        raw: list = []
        for kw in KEYWORDS:
            raw.extend(scrape_keyword(request_ctx, kw, LOCATION))

        request_ctx.dispose()

    seen_this_run: dict = {}
    for job in raw:
        jid = str(job.get("jobId", ""))
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

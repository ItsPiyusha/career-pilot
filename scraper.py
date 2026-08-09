"""
Microsoft Careers Scraper — SDE roles, all locations
Uses Playwright (headless browser) to bypass 403 bot detection
Outputs: microsoft_jobs.csv (all), new_jobs.csv (only new since last run)
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

from playwright.sync_api import Route, sync_playwright

# ── CONFIG ───────────────────────────────────────────────────
KEYWORDS      = ["software engineer", "SDE", "software development engineer"]
LOCATION      = ""
PAGE_SIZE     = 20
DELAY         = 2.0
OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "microsoft_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "new_jobs.csv")

BASE_URL   = "https://jobs.careers.microsoft.com/global/en/search"
WARMUP_URL = "https://careers.microsoft.com/us/en/search-results"


def fetch_jobs_page(page, keyword: str, location: str, pg: int) -> dict:
    params = "&".join([
        f"q={keyword.replace(' ', '+')}",
        f"lc={location}",
        "l=en_us",
        f"pg={pg}",
        f"pgSz={PAGE_SIZE}",
        "o=Relevance",
        "flt=true",
    ])
    url = f"{BASE_URL}?{params}"
    captured: dict = {}

    def handle_route(route: Route) -> None:
        response = route.fetch()
        print(f"  [route] {response.status} {response.url[:80]}")
        if response.status == 200:
            content_type = response.headers.get("content-type", "")
            print(f"  [route] content-type: {content_type}")
            if "json" in content_type or "text/plain" in content_type:
                try:
                    captured["data"] = response.json()
                    print(f"  [route] captured JSON, keys: {list(captured['data'].keys())[:5]}")
                except ValueError as e:
                    print(f"  [route] JSON parse failed: {e}")
        route.fulfill(response=response)

    page.route("**/jobs.careers.microsoft.com/**", handle_route)
    print(f"  Navigating to: {url[:100]}")
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    page.unroute("**/jobs.careers.microsoft.com/**", handle_route)

    if not captured:
        print(f"  ⚠️  Nothing captured — dumping all network requests:")
        # Try direct API fetch via page.evaluate as fallback
        print("  Trying direct fetch fallback...")
        try:
            result = page.evaluate(f"""
                async () => {{
                    const r = await fetch('{url}', {{
                        headers: {{
                            'Accept': 'application/json',
                        }}
                    }});
                    return {{ status: r.status, body: await r.text() }};
                }}
            """)
            print(f"  Direct fetch status: {result['status']}")
            if result['status'] == 200:
                captured["data"] = json.loads(result['body'])
                print(f"  Direct fetch captured {len(captured['data'])} keys")
        except Exception as e:
            print(f"  Direct fetch failed: {e}")

    return captured.get("data", {})


def scrape_keyword(page, keyword: str, location: str) -> list:
    all_jobs = []
    pg = 1
    print(f"\n🔍  Searching: '{keyword}' | location: '{location or 'All'}'")

    while True:
        data   = fetch_jobs_page(page, keyword, location, pg)
        result = data.get("operationResult", {}).get("result", {})
        jobs   = result.get("jobs", [])
        total  = result.get("totalJobs", 0)

        if not jobs:
            print(f"  No jobs on page {pg} (total reported: {total})")
            print(f"  Data keys: {list(data.keys())[:10]}")
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
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print("\n🌐  Loading Microsoft Careers to establish session...")
        page.goto(WARMUP_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        print(f"✅  Page title: {page.title()}")
        print(f"✅  URL after load: {page.url}")

        raw: list = []
        for kw in KEYWORDS:
            raw.extend(scrape_keyword(page, kw, LOCATION))

        browser.close()

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

"""
scraper_all_companies.py — Multi-company job scraper
Covers 40+ companies from your list using Greenhouse and Lever public APIs.
No auth required. Works from GitHub Actions and local Mac.

Usage:
    python3 scraper_all_companies.py

Output:
    all_companies_jobs.csv  — all jobs found this run
    all_companies_new.csv   — only new since last run
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

# ── CONFIG ───────────────────────────────────────────────────
KEYWORDS  = ["engineer", "software", "developer", "SDE", "backend", "frontend", "fullstack", "full stack", "ML", "data"]
INDIA_KEYWORDS = ["india", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "chennai", "delhi", "gurgaon", "noida", "remote"]
FILTER_INDIA_ONLY = False   # Set True to show only India + Remote jobs
DELAY     = 0.5
OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_FILE = os.path.join(OUTPUT_DIR, "seen_ids_all.json")
ALL_JOBS_CSV  = os.path.join(OUTPUT_DIR, "all_companies_jobs.csv")
NEW_JOBS_CSV  = os.path.join(OUTPUT_DIR, "all_companies_new.csv")

# ── COMPANY → ATS MAPPING ────────────────────────────────────
# Format: { "Company Name": ("ats_type", "slug") }
# Greenhouse: boards-api.greenhouse.io/v1/boards/{slug}/jobs
# Lever:      api.lever.co/v0/postings/{slug}?mode=json

COMPANIES = {
    # 🔥 FAANG & Big Tech
    "Uber":           ("greenhouse", "uber"),
    "Salesforce":     ("greenhouse", "salesforce"),
    "Adobe":          ("greenhouse", "adobe"),

    # 🚀 AI Companies
    "OpenAI":         ("greenhouse", "openai"),
    "Anthropic":      ("greenhouse", "anthropic"),
    "Databricks":     ("greenhouse", "databricks"),
    "Cohere":         ("greenhouse", "cohere"),
    "Perplexity":     ("greenhouse", "perplexityai"),
    "Scale AI":       ("greenhouse", "scaleai"),
    "Mistral AI":     ("lever",      "mistral"),
    "Cursor":         ("greenhouse", "anysphere"),
    "Hugging Face":   ("lever",      "huggingface"),
    "xAI":            ("greenhouse", "xai"),

    # ⭐ SaaS & Dev Tools
    "Stripe":         ("greenhouse", "stripe"),
    "Figma":          ("greenhouse", "figma"),
    "Notion":         ("greenhouse", "notion"),
    "Dropbox":        ("greenhouse", "dropbox"),
    "Cloudflare":     ("greenhouse", "cloudflare"),
    "HubSpot":        ("greenhouse", "hubspot"),
    "Atlassian":      ("greenhouse", "atlassian"),
    "GitHub":         ("greenhouse", "github"),
    "Shopify":        ("greenhouse", "shopify"),
    "Block":          ("greenhouse", "block"),
    "Twilio":         ("greenhouse", "twilio"),

    # ⭐ Data & Infra
    "Snowflake":      ("greenhouse", "snowflake"),
    "MongoDB":        ("greenhouse", "mongodb"),
    "Confluent":      ("greenhouse", "confluent"),
    "Datadog":        ("greenhouse", "datadog"),
    "Elastic":        ("greenhouse", "elastic"),
    "HashiCorp":      ("greenhouse", "hashicorp"),

    # 🔥 Fintech
    "Airbnb":         ("greenhouse", "airbnb"),
    "DoorDash":       ("greenhouse", "doordash"),
    "Lyft":           ("greenhouse", "lyft"),
    "Snap":           ("greenhouse", "snap"),
    "Pinterest":      ("greenhouse", "pinterest"),
    "Booking.com":    ("greenhouse", "booking"),

    # Lever companies
    "Netflix":        ("lever",      "netflix"),
    "Waymo":          ("lever",      "waymo"),
    "Palantir":       ("lever",      "palantir"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
}


def is_india_or_remote(location: str) -> bool:
    """Returns True if job is in India, Remote, or location is unspecified."""
    if not FILTER_INDIA_ONLY:
        return True
    if not location:
        return True  # include unspecified locations
    loc_lower = location.lower()
    return any(kw in loc_lower for kw in INDIA_KEYWORDS)


def is_engineering_role(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in KEYWORDS)


# ── GREENHOUSE ────────────────────────────────────────────────

def fetch_greenhouse(company: str, slug: str) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            print(f"  ⚠  {company}: board not found (slug may be wrong)")
            return []
        resp.raise_for_status()
        jobs = resp.json().get("jobs", [])
        filtered = []
        for j in jobs:
            if not is_engineering_role(j.get("title", "")):
                continue
            loc = ""
            if j.get("offices"):
                loc = j["offices"][0].get("name", "")
            elif j.get("location"):
                loc = j["location"].get("name", "")
            if is_india_or_remote(loc):
                filtered.append(j)
        print(f"  ✓  {company}: {len(filtered)} eng roles (of {len(jobs)} total)")
        return [normalise_greenhouse(j, company) for j in filtered]
    except Exception as e:
        print(f"  ✗  {company}: {e}")
        return []


def normalise_greenhouse(job: dict, company: str) -> dict:
    jid = str(job.get("id", ""))
    loc = ""
    if job.get("offices"):
        loc = job["offices"][0].get("name", "")
    elif job.get("location"):
        loc = job["location"].get("name", "")
    return {
        "jobId":       f"gh_{jid}",
        "company":     company,
        "title":       job.get("title", "").strip(),
        "location":    loc,
        "postingDate": job.get("updated_at", "")[:10],
        "url":         job.get("absolute_url", ""),
        "ats":         "Greenhouse",
        "scraped_at":  datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── LEVER ─────────────────────────────────────────────────────

def fetch_lever(company: str, slug: str) -> list:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            print(f"  ⚠  {company}: board not found (slug may be wrong)")
            return []
        resp.raise_for_status()
        jobs = resp.json()
        filtered = []
        for j in jobs:
            if not is_engineering_role(j.get("text", "")):
                continue
            cats = j.get("categories", {})
            loc = cats.get("location", "")
            all_locs = " ".join(cats.get("allLocations", []))
            if is_india_or_remote(loc + " " + all_locs):
                filtered.append(j)
        print(f"  ✓  {company}: {len(filtered)} eng roles (of {len(jobs)} total)")
        return [normalise_lever(j, company) for j in filtered]
    except Exception as e:
        print(f"  ✗  {company}: {e}")
        return []


def normalise_lever(job: dict, company: str) -> dict:
    jid = job.get("id", "")
    cats = job.get("categories", {})
    return {
        "jobId":       f"lv_{jid}",
        "company":     company,
        "title":       job.get("text", "").strip(),
        "location":    cats.get("location", cats.get("allLocations", [""])[0] if cats.get("allLocations") else ""),
        "postingDate": datetime.fromtimestamp(
            job["createdAt"] / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d") if job.get("createdAt") else "",
        "url":         job.get("hostedUrl", ""),
        "ats":         "Lever",
        "scraped_at":  datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── STORAGE ───────────────────────────────────────────────────

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
    fields = ["jobId", "company", "title", "location", "postingDate", "url", "ats", "scraped_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
    print(f"  → {path} ({len(jobs)} jobs)")


# ── MAIN ──────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Career Pilot — Multi-Company Job Scraper")
    print(f"  {len(COMPANIES)} companies | Greenhouse + Lever APIs")
    print("=" * 55)

    all_jobs: list = []

    for company, (ats, slug) in COMPANIES.items():
        if ats == "greenhouse":
            all_jobs.extend(fetch_greenhouse(company, slug))
        elif ats == "lever":
            all_jobs.extend(fetch_lever(company, slug))
        time.sleep(DELAY)

    print(f"\n✅  Total engineering jobs found: {len(all_jobs)}")

    # Deduplicate within this run
    seen_this_run: dict = {}
    for job in all_jobs:
        jid = job["jobId"]
        if jid and jid not in seen_this_run:
            seen_this_run[jid] = job

    all_this_run = list(seen_this_run.values())

    # Compare against previous runs
    seen_before = load_seen_ids()
    new_jobs = [j for j in all_this_run if j["jobId"] not in seen_before]
    print(f"🆕  New since last run: {len(new_jobs)}")

    # Save
    write_csv(all_this_run, ALL_JOBS_CSV)
    write_csv(new_jobs, NEW_JOBS_CSV)
    save_seen_ids(seen_before | {j["jobId"] for j in all_this_run})

    # Summary by company
    print("\n── Summary ───────────────────────────────────────────")
    from collections import Counter
    counts = Counter(j["company"] for j in all_this_run)
    for company, count in sorted(counts.items(), key=lambda x: -x[1]):
        new_count = sum(1 for j in new_jobs if j["company"] == company)
        new_str = f" (+{new_count} new)" if new_count else ""
        print(f"  {company:<20} {count:>4} jobs{new_str}")


if __name__ == "__main__":
    main()

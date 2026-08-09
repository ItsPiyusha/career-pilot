"""
Microsoft Careers Autofill — Eightfold AI portal
Extends autofill.py with a Microsoft-specific handler.

Usage:
    # Single job:
    python autofill_microsoft.py --url "https://jobs.careers.microsoft.com/global/en/job/1234567/"

    # From your scraped CSV (processes new jobs one by one):
    python autofill_microsoft.py --csv microsoft_jobs.csv

Install:
    pip install playwright
    playwright install chromium

Prerequisites:
    - Edit profile.json with your details (or edit DEFAULT_PROFILE below)
    - Put your resume PDF at the path set in profile["resume_path"]
"""

import asyncio
import argparse
import csv
import json
from pathlib import Path
from playwright.async_api import async_playwright, Page


# ──────────────────────────────────────────────────────────────
# YOUR PROFILE — edit profile.json or change defaults here
# ──────────────────────────────────────────────────────────────

DEFAULT_PROFILE = {
    "first_name":          "Piyusha",
    "last_name":           "Lomate",
    "email":               "piyushavpawar@gmail.com",
    "phone":               "+917249575797",
    "linkedin":            "https://linkedin.com/in/piyusha-lomate",
    "github":              "https://github.com/ItsPiyusha",
    "portfolio":           "https://github.com/ItsPiyusha",
    "location":            "Hyderabad, India",
    "resume_path":         "resume.pdf",
    "years_experience":    "9",
    "notice_period":       "30 days",
    "work_authorization":  "No",
    "require_sponsorship": "YES",
    "gender":              "Female",
    "veteran_status":      "I am not a veteran",
    "disability_status":   "I do not have a disability",
}


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

async def fill_text(page: Page, locator, value: str):
    try:
        await locator.click()
        await locator.fill("")
        await locator.type(value, delay=40)
        await page.wait_for_timeout(200)
    except Exception as e:
        print(f"  ⚠  fill_text failed: {e}")


async def pause(page: Page, reason: str):
    print(f"\n⏸  PAUSE — {reason}")
    print("   Complete this step in the browser, then press Enter to continue...")
    input("   > ")
    await page.wait_for_timeout(500)


async def try_fill_field(page: Page, hints: list[str], value: str, label: str):
    """Try multiple CSS selectors / aria labels to find and fill a field."""
    for selector in hints:
        try:
            el = page.locator(selector).first
            if await el.count() > 0 and await el.is_visible():
                await fill_text(page, el, value)
                print(f"  ✓  {label} → {value[:50]}")
                return True
        except Exception:
            continue
    print(f"  –  {label} field not found (skip)")
    return False


async def try_upload(page: Page, resume_path: str):
    """Upload resume to any visible file input."""
    p = Path(resume_path)
    if not p.exists():
        print(f"  ⚠  Resume not found at '{resume_path}' — skipping upload")
        return
    inputs = page.locator("input[type='file']")
    count  = await inputs.count()
    for i in range(count):
        inp = inputs.nth(i)
        try:
            if await inp.is_visible() or True:   # file inputs are often hidden
                await inp.set_input_files(str(p))
                print(f"  ✓  Resume uploaded: {p.name}")
                await page.wait_for_timeout(1500)
                return
        except Exception:
            continue
    print("  –  No file input found")


async def try_select(page: Page, selector: str, value: str, label: str):
    """Try to select a dropdown option."""
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            try:
                await el.select_option(label=value)
            except Exception:
                await el.select_option(value=value)
            print(f"  ✓  {label} → {value}")
    except Exception as e:
        print(f"  –  {label} select failed: {e}")


async def try_radio(page: Page, question_text: str, answer: str):
    """Find a radio group by question text and click the matching answer."""
    try:
        group = page.locator(
            f"[role='radiogroup']:has-text('{question_text}'), "
            f"fieldset:has(legend:has-text('{question_text}'))"
        ).first
        if await group.count() == 0:
            return False
        options = group.locator("label, [role='radio']")
        for i in range(await options.count()):
            opt = options.nth(i)
            text = (await opt.inner_text()).strip().lower()
            if answer.lower() in text:
                await opt.click()
                await page.wait_for_timeout(300)
                print(f"  ✓  '{question_text}' → {answer}")
                return True
    except Exception as e:
        print(f"  ⚠  radio '{question_text}': {e}")
    return False


# ──────────────────────────────────────────────────────────────
# MICROSOFT / EIGHTFOLD HANDLER
# apply.careers.microsoft.com — Eightfold SmartApply portal
# ──────────────────────────────────────────────────────────────

async def handle_microsoft(page: Page, profile: dict):
    """
    Microsoft uses Eightfold AI at apply.careers.microsoft.com.

    Flow:
    1.  Open the job page on jobs.careers.microsoft.com
    2.  Click "Apply" — redirects to apply.careers.microsoft.com
    3.  Sign in with Microsoft account (manual — we pause here)
    4.  Eightfold auto-parses your resume on upload
    5.  We fill remaining fields and pause before submit
    """
    print("\n🪟  Microsoft Careers (Eightfold AI) detected")

    # ── Step 1: Click Apply button ──────────────────────────
    print("\n[1/6] Looking for Apply button...")
    apply_btn = page.locator(
        "a:has-text('Apply'), button:has-text('Apply'), "
        "[data-ph-at-id='apply-button'], .apply-button"
    ).first
    if await apply_btn.count() > 0 and await apply_btn.is_visible():
        await apply_btn.click()
        await page.wait_for_timeout(2000)
        print("  ✓  Clicked Apply")
    else:
        print("  –  Apply button not found — you may already be on the form")

    # ── Step 2: Sign in (manual) ────────────────────────────
    print("\n[2/6] Microsoft sign-in required")
    await pause(page, "Sign in with your Microsoft account, then press Enter")

    # ── Step 3: Upload resume ───────────────────────────────
    print("\n[3/6] Uploading resume...")
    await try_upload(page, profile["resume_path"])
    await page.wait_for_timeout(2000)

    # ── Step 4: Fill text fields ────────────────────────────
    print("\n[4/6] Filling form fields...")

    await try_fill_field(page, [
        "input[name*='firstName' i]",
        "input[placeholder*='first name' i]",
        "input[aria-label*='first name' i]",
        "input[id*='firstName' i]",
    ], profile["first_name"], "First name")

    await try_fill_field(page, [
        "input[name*='lastName' i]",
        "input[placeholder*='last name' i]",
        "input[aria-label*='last name' i]",
        "input[id*='lastName' i]",
    ], profile["last_name"], "Last name")

    await try_fill_field(page, [
        "input[type='email']",
        "input[name*='email' i]",
        "input[placeholder*='email' i]",
    ], profile["email"], "Email")

    await try_fill_field(page, [
        "input[type='tel']",
        "input[name*='phone' i]",
        "input[placeholder*='phone' i]",
        "input[placeholder*='mobile' i]",
    ], profile["phone"], "Phone")

    await try_fill_field(page, [
        "input[name*='linkedin' i]",
        "input[placeholder*='linkedin' i]",
        "input[aria-label*='linkedin' i]",
    ], profile["linkedin"], "LinkedIn")

    await try_fill_field(page, [
        "input[name*='location' i]",
        "input[placeholder*='city' i]",
        "input[placeholder*='location' i]",
        "input[aria-label*='location' i]",
    ], profile["location"], "Location")

    # ── Step 5: Yes/No questions ────────────────────────────
    print("\n[5/6] Answering yes/no questions...")

    await try_radio(page, "authorized to work",  profile["work_authorization"])
    await try_radio(page, "work authorization",  profile["work_authorization"])
    await try_radio(page, "visa sponsorship",    profile["require_sponsorship"])
    await try_radio(page, "require sponsorship", profile["require_sponsorship"])

    # EEO dropdowns
    await try_select(page,
        "select[name*='gender' i], select[aria-label*='gender' i]",
        profile["gender"], "Gender"
    )
    await try_select(page,
        "select[name*='veteran' i], select[aria-label*='veteran' i]",
        profile["veteran_status"], "Veteran status"
    )
    await try_select(page,
        "select[name*='disability' i], select[aria-label*='disability' i]",
        profile["disability_status"], "Disability status"
    )

    # ── Step 6: Human review before submit ──────────────────
    print("\n[6/6] Form filled — please review")
    await pause(page, "Review all fields carefully, then SUBMIT manually in the browser")
    print("\n✅  Application flow complete for this job")


# ──────────────────────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────────────────────

async def run_single(url: str, profile: dict):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,   # visible browser — you need to interact
            slow_mo=60,
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        print(f"\n🌐  Opening: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(1500)
        await handle_microsoft(page, profile)
        print("\n✅  Done. You can close the browser.")
        await page.wait_for_timeout(5000)
        await browser.close()


async def run_csv(csv_path: str, profile: dict):
    """
    Read microsoft_jobs.csv and process jobs with status 'new' one by one.
    After each job, ask if you want to continue to the next.
    """
    jobs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            jobs.append(row)

    print(f"\n📋  Loaded {len(jobs)} jobs from {csv_path}")
    new_jobs = [j for j in jobs if j.get("status", "new") != "skip"]
    print(f"    {len(new_jobs)} non-skipped jobs to process\n")

    for i, job in enumerate(new_jobs, 1):
        print(f"\n{'='*55}")
        print(f"  Job {i}/{len(new_jobs)}: {job.get('title', '?')}")
        print(f"  📍 {job.get('location', '?')}")
        print(f"  🔗 {job.get('url', '?')}")
        print(f"{'='*55}")

        go = input("\nApply to this job? [y/n/q to quit]: ").strip().lower()
        if go == "q":
            print("Quitting.")
            break
        if go != "y":
            print("Skipped.")
            continue

        url = job.get("url", "")
        if not url:
            print("  ⚠  No URL found for this job")
            continue

        await run_single(url, profile)

        if i < len(new_jobs):
            cont = input("\nContinue to next job? [y/n]: ").strip().lower()
            if cont != "y":
                break

    print("\n✅  Session complete.")


# ──────────────────────────────────────────────────────────────
# ENTRYPOINT
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Microsoft Careers autofill — Eightfold AI portal"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single job URL to apply to")
    group.add_argument("--csv", help="Path to microsoft_jobs.csv — processes jobs one by one")
    parser.add_argument(
        "--profile", default="profile.json",
        help="Path to profile JSON (default: profile.json)"
    )
    args = parser.parse_args()

    # Load profile
    profile_path = Path(args.profile)
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)
        print(f"✓ Loaded profile from {profile_path}")
    else:
        print(f"⚠  {profile_path} not found — using built-in default profile")
        profile = DEFAULT_PROFILE

    if args.url:
        asyncio.run(run_single(args.url, profile))
    else:
        asyncio.run(run_csv(args.csv, profile))


if __name__ == "__main__":
    main()

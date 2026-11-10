import asyncio
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import sqlite3
from playwright.async_api import async_playwright
import profile_paths

CLOSED_PHRASES = [
    "no longer accepting applications",
    "no longer accepting applicants",
    "this job is no longer available",
    "this job has expired",
    "job posting has expired",
    "no longer active",
    "position has been filled",
    "position has already been filled",
    "this position has been filled",
    "job is closed",
    "vacancy is closed",
    "applications are closed",
    "sorry, this job is no longer available",
    "esta oferta ya no está disponible",
    "ya no acepta solicitudes",
]

async def check_url(context, url: str) -> dict:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(2000)
        text = (await page.locator("body").inner_text()).lower()
        for phrase in CLOSED_PHRASES:
            if phrase in text:
                return {"status": "CLOSED", "reason": phrase}
        if len(text.strip()) < 200:
            return {"status": "UNKNOWN", "reason": "página casi vacía (posible bloqueo/authwall)"}
        if "sign in" in text[:400] and "linkedin" in url and "view" not in text[:2000]:
            return {"status": "UNKNOWN", "reason": "posible authwall de LinkedIn"}
        return {"status": "OPEN", "reason": ""}
    except Exception as e:
        return {"status": "UNKNOWN", "reason": f"error cargando: {str(e)[:120]}"}
    finally:
        await page.close()

async def main():
    conn = sqlite3.connect(profile_paths.resolve("jobs.db"))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""SELECT id, title, company, match_percentage, url FROM jobs
                   WHERE status = 'CV Generado' AND title != 'Trabajo de Prueba'
                   ORDER BY match_percentage DESC""")
    jobs = [dict(r) for r in cur.fetchall()]
    conn.close()

    print(f"Chequeando {len(jobs)} vacantes...\n")
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        for i, job in enumerate(jobs, 1):
            r = await check_url(context, job["url"])
            print(f"[{i}/{len(jobs)}] {job['match_percentage']}% | {job['title'][:45]} @ {job['company'][:25]} -> {r['status']} {('(' + r['reason'] + ')') if r['reason'] else ''}")
            results.append({**job, **r})
        await browser.close()

    with open("job_status_check.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    open_jobs = [r for r in results if r["status"] == "OPEN"]
    closed_jobs = [r for r in results if r["status"] == "CLOSED"]
    unknown_jobs = [r for r in results if r["status"] == "UNKNOWN"]
    print(f"\n=== RESUMEN ===")
    print(f"OPEN: {len(open_jobs)} | CLOSED: {len(closed_jobs)} | UNKNOWN: {len(unknown_jobs)}")

if __name__ == "__main__":
    asyncio.run(main())

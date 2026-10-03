"""Completa la ubicación de las vacantes de LinkedIn ya guardadas (página pública de la oferta, sin login) y oculta
(No Elegible) las que están en un país donde no la pueden contratar, con la misma regla que el scout
(job_filters.location_reason). Las ya marcadas como aplicadas no se tocan.
Uso: python locate_jobs.py > locate_jobs.log"""
import html
import re
import sqlite3
import time
import urllib.request

import database
import job_filters
from job_scraper import clean_job_description

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def linkedin_location(url: str) -> str:
    m = re.search(r"/jobs/view/(?:[^/]*-)?(\d+)", url)
    if not m:
        return ""
    req = urllib.request.Request(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}", headers=UA)
    page = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    loc = re.search(r"topcard__flavor--bullet[^>]*>\s*([^<]+)<", page)
    return html.unescape(loc.group(1).strip()) if loc else ""


database.init_db()  # crea la columna location si todavía no existe
c = sqlite3.connect("jobs.db")
rows = c.execute("SELECT id, title, company, url, scraped_content FROM jobs WHERE location IS NULL AND applied_at IS NULL "
                 "AND status IN ('CV Generado', 'Aprobado', 'Match Insuficiente') AND url LIKE '%linkedin.com/jobs/view/%'").fetchall()
print(f"{len(rows)} vacantes de LinkedIn sin ubicación", flush=True)
hidden = 0
for jid, title, company, url, content in rows:
    try:
        location = linkedin_location(url)
    except Exception as e:  # oferta cerrada o rate-limit: queda como estaba y se reintenta en otra corrida
        print(f"{jid} | ERROR {e}", flush=True)
        time.sleep(10)
        continue
    reason = job_filters.location_reason(location, clean_job_description(content or ""))
    if reason:
        c.execute("UPDATE jobs SET location = ?, status = 'No Elegible' WHERE id = ?", (location, jid))
        hidden += 1
    else:
        c.execute("UPDATE jobs SET location = ? WHERE id = ?", (location or "", jid))
    c.commit()
    print(f"{jid} | {location or '?'} | {'OCULTA: ' + reason if reason else 'ok'} | {company} | {title[:45]}", flush=True)
    time.sleep(2)  # ritmo amable con LinkedIn
print(f"FIN — {hidden} ocultas", flush=True)

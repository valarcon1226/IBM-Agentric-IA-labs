"""
Compara el scoring nuevo (extracción + puntaje determinístico, job_scoring.py) contra el match que
dio Gemini/Groq en su momento, sobre vacantes ya evaluadas. Por defecto fuerza el modelo LOCAL
(peor caso) para ver si el método aguanta sin las APIs.

    python validate_scoring.py <db_con_evaluaciones_de_referencia> [ids_extra_de_jobs.db ...]
"""
import sqlite3
import sys
import time

import llm_chain
import job_scoring
from job_scraper import clean_job_description

llm_chain._CHAIN = [c for c in llm_chain._CHAIN if c[0] == "Ollama"]

ref_db = sys.argv[1]
extra_ids = [int(x) for x in sys.argv[2:]]

rows = sqlite3.connect(ref_db).execute(
    "SELECT id, title, company, scraped_content, match_percentage, status FROM jobs "
    "WHERE length(scraped_content) > 300 ORDER BY id").fetchall()
rows = [(f"ref{r[0]}",) + r[1:] for r in rows]
if extra_ids:
    q = ",".join("?" * len(extra_ids))
    rows += [(f"new{r[0]}",) + r[1:] for r in sqlite3.connect("jobs.db").execute(
        f"SELECT id, title, company, scraped_content, match_percentage, status FROM jobs WHERE id IN ({q})",
        extra_ids).fetchall()]

results = []
for rid, title, company, content, old_pct, status in rows:
    t = time.time()
    try:
        facts = job_scoring.extract_facts(title, clean_job_description(content))
        viable, pct, missing, why = job_scoring.score(facts)
    except Exception as e:
        print(f"{rid:>7} ERROR {type(e).__name__}: {str(e)[:120]}")
        continue
    results.append((old_pct, pct))
    print(f"{rid:>7} | antes {old_pct:>3} -> nuevo {pct:>3} {'OK ' if viable else 'NO '}| {time.time()-t:4.0f}s | "
          f"{company[:18]:<18} | {title[:45]:<45} | {why[:110]}", flush=True)

if results:
    diffs = [abs(a - b) for a, b in results]
    print(f"\n{len(results)} vacantes | diferencia media {sum(diffs)/len(diffs):.1f} pts | "
          f"nuevo promedio {sum(b for _, b in results)/len(results):.0f} vs antes {sum(a for a, _ in results)/len(results):.0f} | "
          f"valores distintos de puntaje nuevo: {len(set(b for _, b in results))}")

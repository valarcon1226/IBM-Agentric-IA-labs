"""Re-puntúa con job_scoring (solo modelo local) las vacantes visibles y les aplica las franjas del scout:
70+ -> Aprobado (o sigue 'CV Generado' si ya tiene CV) · 40-69 -> Match Insuficiente · <40 o rol fuera de
AI/FDE/QA -> No Elegible (oculta). Las ya marcadas como aplicadas no se ocultan.
Uso: python rescore.py > rescore.log   ·   solo algunas: python rescore.py 49 51"""
import sqlite3

import profile_paths
import sys
import job_scoring
import llm_chain
from job_scraper import clean_job_description

c = sqlite3.connect(profile_paths.resolve("jobs.db"))
rows = c.execute("SELECT id, title, company, match_percentage, scraped_content, status, cv_path, applied_at FROM jobs "
                 "WHERE status IN ('Aprobado', 'CV Generado', 'Match Insuficiente')").fetchall()
ids = {int(a) for a in sys.argv[1:]}
rows = [r for r in rows if not ids or r[0] in ids]
print(f"{len(rows)} vacantes a re-puntuar", flush=True)
for jid, title, company, old, content, status, cv_path, applied_at in rows:
    try:
        facts = job_scoring.extract_facts(title, clean_job_description(content or ""), local_only=True)
    except llm_chain.AllProvidersExhausted:
        raise
    except Exception as e:  # una JD rara no debe frenar el lote; queda como estaba
        print(f"{jid} | ERROR {e}", flush=True)
        continue
    viable, pct, missing, why = job_scoring.score(facts)
    if (not viable or pct < 40) and not applied_at:
        new = "No Elegible"
    elif pct >= 70:
        new = "CV Generado" if cv_path else "Aprobado"
    else:
        new = "Match Insuficiente"
    c.execute("UPDATE jobs SET status=?, match_percentage=?, gap_analysis=? WHERE id=?", (new, pct, ", ".join(missing), jid))
    c.commit()
    print(f"{jid} | {old}->{pct} | {status}->{new} | {company} | {title[:45]} | {why}", flush=True)
print("FIN", flush=True)

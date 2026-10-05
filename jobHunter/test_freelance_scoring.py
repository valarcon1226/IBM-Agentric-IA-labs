"""Chequeo mínimo de score_gig (sin LLM): python test_freelance_scoring.py
Usa un perfil de prueba propio (no el de nadie), así corre en cualquier PC."""
import json
import os
import tempfile

import profile_paths

_tmp = tempfile.mkdtemp()
with open(os.path.join(_tmp, "master_profile.json"), "w", encoding="utf-8") as f:
    json.dump({"technical_stacks": [{"ability": "Dev", "ability_description":
               "Python, Selenium, n8n, OpenAI, React, Linux, VPS, Google Sheets, email automation"}]}, f)
profile_paths.resolve = lambda name: os.path.join(_tmp, name)

from freelance_hunter_agent import GigFacts, score_gig  # noqa: E402


def fit(category, skills, clear=True, days=4, platform="Freelancer"):
    facts = GigFacts(category=category, required_skills=skills, scope_is_clear=clear,
                     estimated_days=days, deliverable="x")
    return score_gig({"platform": platform}, facts)


assert fit("web_scraping", ["Python", "Selenium"]).is_good_fit
assert fit("automation_integration", ["n8n", "OpenAI", "Google Sheets", "Email"]).is_good_fit
assert fit("automation_integration", ["Linux", "VPS", "Python"]).is_good_fit
assert fit("full_product", ["React"]).is_good_fit  # 2026-10-02: los proyectos grandes también interesan
assert not fit("non_technical", []).is_good_fit
assert fit("ai_agent", ["Python"], days=30).is_good_fit
assert not fit("ai_agent", ["Python"], days=120).is_good_fit  # más de FREELANCE_MAX_DAYS (90)
assert fit("website", ["Python", "Rust"]).missing_skills == ["Rust"]
assert not fit("dashboard_webapp", ["Laravel", "PHP", "Vue"], clear=False).is_good_fit
assert "sin skills declaradas" in fit("web_scraping", []).reasoning
print("ok")

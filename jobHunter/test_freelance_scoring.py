"""Chequeo mínimo de score_gig (sin LLM): python test_freelance_scoring.py"""
from freelance_hunter_agent import GigFacts, score_gig


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

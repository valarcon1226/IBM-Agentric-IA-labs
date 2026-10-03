"""Chequeo sin LLM ni red del agrupado del Trend Spotter: py test_trend_grouping.py"""
from trend_spotter_agent import group_signals

S = lambda d, t, when="2026-09-28 10:00:00": {"domain": d, "task": t, "deliverable": "doc", "automatable": "high", "extracted_at": when}

groups = group_signals([
    S("legal", "draft legal contracts"),
    S("legal", "draft legal contract"),            # casi igual -> mismo grupo
    S("legal", "draft legal contracts", "2026-09-01 10:00:00"),
    S("medical", "write clinical visit notes"),
    S("medical", "draft legal contracts"),          # otro dominio -> otro grupo
], recent_since="2026-09-21 00:00:00")

assert groups[0]["domain"] == "legal" and groups[0]["count"] == 3, groups[0]
assert groups[0]["count_7d"] == 2, groups[0]
assert len(groups) == 3, groups
print("ok")

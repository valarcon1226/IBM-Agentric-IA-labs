# Test Case Generator Evaluation Report — `qwen3:4b-instruct-2507-q4_K_M`

- **Model Evaluated:** `qwen3:4b-instruct-2507-q4_K_M`
- **Split:** `test`
- **Timestamp (UTC):** `2026-11-11T07:04:32.631568+00:00`
- **Total Requirements:** 4
- **Total Generated Test Cases:** 31
- **Overall Evaluation Status:** **⚠️ THRESHOLD BREACH DETECTED**

## Summary Metrics vs. Pre-Registered Thresholds

| Metric | Measured Score | Pre-Registered Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Schema Valid Rate (1st Try)** | 75.0% (0.7500) | >= 90.0% | ❌ FAIL |
| **Declared Criteria Coverage** | 100.0% (1.0000) | >= 70.0% | ✅ PASS |
| **Verified Regex Coverage** | 93.8% (0.9375) | >= 70.0% | ✅ PASS |
| **Hallucinated Criterion Refs** | 3.2% (0.0323) | <= 2.0% | ❌ FAIL |
| **Duplicate Case Rate (difflib ≥ 0.9)** | 6.5% (0.0645) | <= 10.0% | ✅ PASS |
| **Negative/Edge Test Case Presence** | 100.0% (1.0000) | >= 100.0% | ✅ PASS |

## Per-Requirement Breakdown

| Requirement ID | Title | Cases | 1st Try Valid? | Level Distribution |
| :--- | :--- | :---: | :---: | :--- |
| `REQ-09` | Seguimiento y trazabilidad de pedidos | 7 | No (1 retry) | 2 edge, 2 functional, 2 negative, 1 smoke |
| `REQ-10` | Administración de listas de deseos y favoritos | 8 | Yes | 2 edge, 3 functional, 2 negative, 1 smoke |
| `REQ-11` | Sistema de reseñas y valoraciones de producto | 8 | Yes | 2 edge, 3 functional, 2 negative, 1 smoke |
| `REQ-12` | Alertas automáticas de reposición de inventario | 8 | Yes | 2 edge, 3 functional, 3 negative |

## Notes on Evaluation Rigor

- **Harness Self-Check:** When running with `--model stub`, this suite verifies that the
  evaluator, acceptance criteria regular expressions, and parsing logic agree.
- **Goalpost Protection:** Thresholds were committed in `evals/config.toml` prior to
  evaluating production local models.

# Test Case Generator Evaluation Report — `qwen3:4b-instruct-2507-q4_K_M`

- **Model Evaluated:** `qwen3:4b-instruct-2507-q4_K_M`
- **Split:** `dev`
- **Timestamp (UTC):** `2026-11-11T06:40:13.287040+00:00`
- **Total Requirements:** 8
- **Total Generated Test Cases:** 70
- **Overall Evaluation Status:** **⚠️ THRESHOLD BREACH DETECTED**

## Summary Metrics vs. Pre-Registered Thresholds

| Metric | Measured Score | Pre-Registered Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Schema Valid Rate (1st Try)** | 75.0% (0.7500) | >= 90.0% | ❌ FAIL |
| **Declared Criteria Coverage** | 100.0% (1.0000) | >= 70.0% | ✅ PASS |
| **Verified Regex Coverage** | 56.2% (0.5625) | >= 70.0% | ❌ FAIL |
| **Hallucinated Criterion Refs** | 2.9% (0.0286) | <= 2.0% | ❌ FAIL |
| **Duplicate Case Rate (difflib ≥ 0.9)** | 2.9% (0.0286) | <= 10.0% | ✅ PASS |
| **Negative/Edge Test Case Presence** | 100.0% (1.0000) | >= 100.0% | ✅ PASS |

## Per-Requirement Breakdown

| Requirement ID | Title | Cases | 1st Try Valid? | Level Distribution |
| :--- | :--- | :---: | :---: | :--- |
| `REQ-01` | Autenticación de usuarios y control de sesiones | 8 | Yes | 2 edge, 1 functional, 4 negative, 1 smoke |
| `REQ-02` | Registro de nuevos clientes y validación de credenciales | 10 | Yes | 4 edge, 5 negative, 1 smoke |
| `REQ-03` | Búsqueda y filtrado de productos en catálogo | 8 | Yes | 3 edge, 2 functional, 2 negative, 1 smoke |
| `REQ-04` | Gestión del carrito de compras | 7 | Yes | 2 edge, 3 functional, 2 negative |
| `REQ-05` | Aplicación de cupones de descuento y promociones | 8 | No (1 retry) | 2 edge, 2 functional, 3 negative, 1 smoke |
| `REQ-06` | Pasarela de pago y confirmación de pedidos | 10 | Yes | 3 edge, 2 functional, 4 negative, 1 smoke |
| `REQ-07` | Libreta de direcciones de entrega | 9 | Yes | 3 edge, 2 functional, 3 negative, 1 smoke |
| `REQ-08` | Solicitud de devoluciones y reembolsos | 10 | No (1 retry) | 1 edge, 5 functional, 3 negative, 1 smoke |

## Notes on Evaluation Rigor

- **Harness Self-Check:** When running with `--model stub`, this suite verifies that the
  evaluator, acceptance criteria regular expressions, and parsing logic agree.
- **Goalpost Protection:** Thresholds were committed in `evals/config.toml` prior to
  evaluating production local models.

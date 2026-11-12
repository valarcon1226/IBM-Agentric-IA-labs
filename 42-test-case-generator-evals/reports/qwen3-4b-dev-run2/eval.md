# Test Case Generator Evaluation Report — `qwen3:4b-instruct-2507-q4_K_M`

- **Model Evaluated:** `qwen3:4b-instruct-2507-q4_K_M`
- **Split:** `dev`
- **Timestamp (UTC):** `2026-11-11T06:56:57.817879+00:00`
- **Total Requirements:** 8
- **Total Generated Test Cases:** 66
- **Overall Evaluation Status:** **⚠️ THRESHOLD BREACH DETECTED**

## Summary Metrics vs. Pre-Registered Thresholds

| Metric | Measured Score | Pre-Registered Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Schema Valid Rate (1st Try)** | 87.5% (0.8750) | >= 90.0% | ❌ FAIL |
| **Declared Criteria Coverage** | 100.0% (1.0000) | >= 70.0% | ✅ PASS |
| **Verified Regex Coverage** | 90.6% (0.9062) | >= 70.0% | ✅ PASS |
| **Hallucinated Criterion Refs** | 1.5% (0.0152) | <= 2.0% | ✅ PASS |
| **Duplicate Case Rate (difflib ≥ 0.9)** | 12.1% (0.1212) | <= 10.0% | ❌ FAIL |
| **Negative/Edge Test Case Presence** | 100.0% (1.0000) | >= 100.0% | ✅ PASS |

## Per-Requirement Breakdown

| Requirement ID | Title | Cases | 1st Try Valid? | Level Distribution |
| :--- | :--- | :---: | :---: | :--- |
| `REQ-01` | Autenticación de usuarios y control de sesiones | 8 | Yes | 2 edge, 1 functional, 4 negative, 1 smoke |
| `REQ-02` | Registro de nuevos clientes y validación de credenciales | 8 | No (1 retry) | 2 edge, 5 negative, 1 smoke |
| `REQ-03` | Búsqueda y filtrado de productos en catálogo | 8 | Yes | 3 edge, 2 functional, 2 negative, 1 smoke |
| `REQ-04` | Gestión del carrito de compras | 8 | Yes | 2 edge, 3 functional, 3 negative |
| `REQ-05` | Aplicación de cupones de descuento y promociones | 7 | Yes | 2 edge, 1 functional, 3 negative, 1 smoke |
| `REQ-06` | Pasarela de pago y confirmación de pedidos | 11 | Yes | 2 edge, 3 functional, 5 negative, 1 smoke |
| `REQ-07` | Libreta de direcciones de entrega | 8 | Yes | 3 edge, 1 functional, 3 negative, 1 smoke |
| `REQ-08` | Solicitud de devoluciones y reembolsos | 8 | Yes | 1 edge, 3 functional, 3 negative, 1 smoke |

## Notes on Evaluation Rigor

- **Harness Self-Check:** When running with `--model stub`, this suite verifies that the
  evaluator, acceptance criteria regular expressions, and parsing logic agree.
- **Goalpost Protection:** Thresholds were committed in `evals/config.toml` prior to
  evaluating production local models.

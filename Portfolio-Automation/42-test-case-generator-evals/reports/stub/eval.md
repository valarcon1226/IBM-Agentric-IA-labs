# Test Case Generator Evaluation Report — `stub`

- **Model Evaluated:** `stub`
- **Split:** `dev`
- **Timestamp (UTC):** `2026-11-11T03:59:15.776067+00:00`
- **Total Requirements:** 8
- **Total Generated Test Cases:** 32
- **Overall Evaluation Status:** **✅ ALL THRESHOLDS PASSED**

## Summary Metrics vs. Pre-Registered Thresholds

| Metric | Measured Score | Pre-Registered Threshold | Status |
| :--- | :---: | :---: | :---: |
| **Schema Valid Rate (1st Try)** | 100.0% (1.0000) | >= 90.0% | ✅ PASS |
| **Declared Criteria Coverage** | 100.0% (1.0000) | >= 70.0% | ✅ PASS |
| **Verified Regex Coverage** | 100.0% (1.0000) | >= 70.0% | ✅ PASS |
| **Hallucinated Criterion Refs** | 0.0% (0.0000) | <= 2.0% | ✅ PASS |
| **Duplicate Case Rate (difflib ≥ 0.9)** | 0.0% (0.0000) | <= 10.0% | ✅ PASS |
| **Negative/Edge Test Case Presence** | 100.0% (1.0000) | >= 100.0% | ✅ PASS |

## Per-Requirement Breakdown

| Requirement ID | Title | Cases | 1st Try Valid? | Level Distribution |
| :--- | :--- | :---: | :---: | :--- |
| `REQ-01` | Autenticación de usuarios y control de sesiones | 4 | Yes | 1 edge, 1 functional, 1 negative, 1 smoke |
| `REQ-02` | Registro de nuevos clientes y validación de credenciales | 4 | Yes | 1 edge, 1 functional, 2 negative |
| `REQ-03` | Búsqueda y filtrado de productos en catálogo | 4 | Yes | 2 functional, 1 negative, 1 smoke |
| `REQ-04` | Gestión del carrito de compras | 4 | Yes | 1 edge, 1 functional, 1 negative, 1 smoke |
| `REQ-05` | Aplicación de cupones de descuento y promociones | 4 | Yes | 1 edge, 1 functional, 1 negative, 1 smoke |
| `REQ-06` | Pasarela de pago y confirmación de pedidos | 4 | Yes | 1 edge, 2 functional, 1 smoke |
| `REQ-07` | Libreta de direcciones de entrega | 4 | Yes | 1 edge, 1 functional, 1 negative, 1 smoke |
| `REQ-08` | Solicitud de devoluciones y reembolsos | 4 | Yes | 1 edge, 1 functional, 1 negative, 1 smoke |

## Notes on Evaluation Rigor

- **Harness Self-Check:** When running with `--model stub`, this suite verifies that the
  evaluator, acceptance criteria regular expressions, and parsing logic agree.
- **Goalpost Protection:** Thresholds were committed in `evals/config.toml` prior to
  evaluating production local models.

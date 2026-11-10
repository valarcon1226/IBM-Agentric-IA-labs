# Análisis de Riesgos de Seguridad y Disponibilidad (IAM)

> **Nota Metodológica:** Este modelo de amenazas y análisis de riesgos está **modelado en** los capítulos V2 (Verificación de Autenticación), V3 (Gestión de Sesión), V13 (Verificación de APIs) y V14 (Configuración) del estándar **OWASP ASVS v4.0.3**. No constituye ni declara certificación o cumplimiento formal ("compliant"), sino una evaluación de controles de ingeniería de calidad frente a vectores de ataque comunes en arquitecturas IAM (Keycloak 26).

---

## 1. Matriz de Evaluación de Riesgos ($L \times I$)

| ID | Vector de Riesgo | Probabilidad ($L$) | Impacto ($I$) | Severidad | Control SUT / Mitigación | Referencia ASVS v4.0.3 (Modelado en) | Requerimiento Trazable |
|---|---|---|---|---|---|---|---|
| **RSK-001** | **Credential Stuffing / Fuerza Bruta** | 5 (Muy Alta) | 4 (Alto) | **ALTO (20)** | Protección contra fuerza bruta con factor de fallo configurable (3 intentos), incremento progresivo de espera y bloqueo temporal. | ASVS 2.2.1, 2.2.2 | `REQ-IAM-001` |
| **RSK-002** | **Replay de Authorization Code / Refresh Token** | 4 (Alta) | 5 (Crítico) | **ALTO (20)** | Intercambio de código de un solo uso; rotación forzada de tokens de refresco (`revokeRefreshToken: true`) y revocación inmediata de sesión si se detecta reuso. | ASVS 3.5.2, 3.5.3 | `REQ-IAM-002` |
| **RSK-003** | **Fijación de Sesión / Ataques de Inyección de Token** | 3 (Media) | 4 (Alto) | **MEDIO (12)** | Emisión estricta de nuevo identificador de sesión y validación criptográfica de tokens OIDC (firma RS256, `nonce`, `state`, PKCE S256). | ASVS 3.2.1, 3.2.3 | `REQ-IAM-003` |
| **RSK-004** | **Abuso de Restablecimiento de Contraseña / Enumeración de Cuentas** | 4 (Alta) | 4 (Alto) | **ALTO (16)** | Token de restablecimiento de un solo uso, expiración breve y respuesta genérica indiferenciada ante cuentas inexistentes o fallos de transporte SMTP. | ASVS 2.5.2, 2.5.6 | `REQ-IAM-004` |
| **RSK-005** | **Sobrecarga de Tráfico y Caída Catastrófica (DoS)** | 4 (Alta) | 4 (Alto) | **ALTO (16)** | Mecanismo de contrapresión (`KC_HTTP_MAX_QUEUED_REQUESTS`); descarte de exceso con HTTP 503 (sin errores 500) y recuperación inmediata. | ASVS 13.1.5 | `REQ-IAM-005` |
| **RSK-006** | **Inconsistencia y Duplicación en Paginación Administrativa** | 3 (Media) | 3 (Medio) | **MEDIO (9)** | Paginación determinista en `/admin/realms/{realm}/users` con parámetros `first` y `max`; coherencia entre recorrido y endpoint de conteo. | ASVS 13.2.3 | `REQ-IAM-006` |
| **RSK-007** | **Fallos Parciales en Importación Masiva de Identidades** | 3 (Media) | 4 (Alto) | **ALTO (12)** | Validación y aislamiento de colisiones de identidad en `partialImport` bajo políticas SKIP, OVERWRITE y FAIL. | ASVS 13.2.1 | `REQ-IAM-007` |
| **RSK-008** | **Degradación o Corrupción Criptográfica en Upgrade (N-1 a N)** | 3 (Media) | 5 (Crítico) | **ALTO (15)** | Validación de login con contraseñas históricas, credenciales MFA (TOTP) y secretos de clientes OAuth tras migraciones Liquibase. | ASVS 14.2.3 | `REQ-IAM-008` |

---

## 2. Mapa de Cobertura de Riesgos Altos

Cada riesgo con calificación **ALTO** cuenta con su requerimiento formal asociado, suite de pruebas automatizada y objetivo numérico:

- **RSK-001 (Credential Stuffing):** Cubierto por `REQ-IAM-001`, validado en `tests/ui/test_mfa_lockout.py`. Meta: Bloqueo exactamente al intento $N=3$.
- **RSK-002 (Replay de Tokens):** Cubierto por `REQ-IAM-002`, validado en `tests/api/test_replay.py`. Meta: 0 reusos exitosos.
- **RSK-004 (Abuso Password Reset):** Cubierto por `REQ-IAM-004`, validado en `tests/ui/test_password_reset.py`. Meta: No enumeración y enlaces de un solo uso.
- **RSK-005 (Sobrecarga de Tráfico):** Cubierto por `REQ-IAM-005`, validado en `tests/perf/test_overload.py` y Locust. Meta: 0 respuestas 5xx durante ráfaga de 300 req.
- **RSK-007 (Fallos en Importación):** Cubierto por `REQ-IAM-007`, validado en `tests/api/test_partial_import.py`. Meta: Consistencia exacta entre conteos reportados y BD.
- **RSK-008 (Upgrade de Versión):** Cubierto por `REQ-IAM-008`, validado en `tests/migration/test_upgrade.py`. Meta: 20/20 logins exitosos post-upgrade; tiempo $\le$ 5 min.

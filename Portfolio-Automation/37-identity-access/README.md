# Keycloak Identity and Access Management (Project 37)

Quality engineering, protocol compliance, resilience, and security test suite for Keycloak IAM backed by PostgreSQL, Mailpit, and Toxiproxy.

Evaluates OAuth 2.0 / OpenID Connect Core 1.0, PKCE S256, refresh token rotation and replay revocation (RFC 6749, RFC 9700), multi-factor authentication (MFA/TOTP), brute-force account lockout, resilient password reset during SMTP outages, load shedding backpressure, 10k-user deterministic pagination, partial import atomicity, and major schema migration (Keycloak 25 to 26).

---

## Architectural Concerns & Test Verification

| Concern | How It Is Tested | ASVS / RFC Mapping | Test Location |
|---|---|---|---|
| **Cryptographic Token Validation** | Full OIDC Code Flow with PKCE S256 on Microsoft Edge; cryptographic RS256 ID token verification against JWKS (iss, aud, exp, nonce). | RFC 7636, ASVS V3.2.1, V3.2.3 | [`tests/oidc.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/oidc.py) |
| **Replay & Retry Semantics** | Exchange authorization code twice (`invalid_grant`). With refresh token rotation on, reusing an old refresh token revokes the entire user session. | RFC 6749 §4.1.2, RFC 9700 §4.14, ASVS V3.5.2, V3.5.3 | [`tests/api/test_replay.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/api/test_replay.py) |
| **MFA & Brute-Force Lockout** | Enroll TOTP via pyotp from QR manual secret. Wrong TOTP counts as failure. Account lockout triggers at exactly $N=3$ consecutive failures across Edge, Firefox, and WebKit. Admin unlock verified. | ASVS V2.2.1, V2.2.2, V2.8.1 | [`tests/ui/test_mfa_lockout.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/ui/test_mfa_lockout.py) |
| **Resilient Password Reset** | Happy path reset via Mailpit API; action token single-use and expiration. Toxiproxy cuts SMTP: UI displays generic error without disclosing account existence. | ASVS V2.5.2, V2.5.4, V2.5.6 | [`tests/ui/test_password_reset.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/ui/test_password_reset.py) |
| **Backpressure & Load Shedding** | Locust load tests at 10, 50, 100 rps. Concurrent burst of 300 token requests with `--http-max-queued-requests 20`: excess requests return HTTP 503 and 0 HTTP 500s; recovers within 2s. | ASVS V13.1.5 | [`tests/perf/test_load.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/perf/test_load.py), [`tests/resilience/test_overload.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/resilience/test_overload.py) |
| **Admin User Pagination** | Walk 10,000 users via admin REST API with `max` 100, 37, and 1: identical set of IDs, 0 duplicates. Walk during concurrent 300-user insertion: 0 baseline missed, 0 repeated. Prefix search agrees with count. | ASVS V13.2.3 | [`tests/api/test_pagination.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/api/test_pagination.py) |
| **Partial Import Collision Policies** | Import 1,000 users with 50 conflicts under SKIP, OVERWRITE, and FAIL policies on fresh realms. FAIL verified as atomic all-or-nothing rollback (409 Conflict). | ASVS V13.2.1 | [`tests/api/test_partial_import.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/api/test_partial_import.py) |
| **Major Schema Migration** | Upgrade from Keycloak 25.0.6 (N-1) to 26.0.5 (N) with 10k users. All 20/20 users log in with old password and TOTP. Client secrets match. Migration duration recorded. | ASVS V14.2.3 | [`tests/migration/test_upgrade.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/migration/test_upgrade.py) |

---

## Measured Quality Targets (`targets.toml`)

| Metric / Requirement | Target SLA | Measured Value | Compliance | Test Evidence |
|---|---|---|---|---|
| **Token endpoint (`client_credentials`) p95 at 50 rps** | $\le$ 300 ms | **16.0 ms** | **PASS** | [`results/metrics.json`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/results/metrics.json) |
| **Password login p95 at 10 rps** | $\le$ 800 ms | **62.65 ms** | **PASS** | [`results/metrics.json`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/results/metrics.json) |
| **Unhandled 5xx responses during 300-request burst** | 0 (503 allowed) | **0 (500s: 0, 503s: 216)** | **PASS** | [`tests/resilience/test_overload.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/resilience/test_overload.py) |
| **Successful reuse of auth code or rotated refresh token** | 0 | **0** | **PASS** | [`tests/api/test_replay.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/api/test_replay.py) |
| **Lockout threshold after failed attempts** | Exactly $N=3$ | **3 (exact)** | **PASS** | [`tests/ui/test_mfa_lockout.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/ui/test_mfa_lockout.py) |
| **Users missed or repeated in 10k pagination walk** | 0 | **0** | **PASS** | [`tests/api/test_pagination.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/api/test_pagination.py) |
| **Major schema upgrade duration (10k users)** | $\le$ 300 s (5 min) | **15.06 s** | **PASS** | [`tests/migration/test_upgrade.py`](file:///C:/Users/valentina.alarcon/Documents/PER/Cursos/Claudia/Portfolio%20Gemini/Portfolio-Automation/37-identity-access/tests/migration/test_upgrade.py) |

---

## ASVS Coverage & Scope Boundaries

### Evaluated Areas (Modeled on OWASP ASVS v4.0.3)
- **V2: Authentication:** V2.2 (Brute Force Protection), V2.5 (Credential Recovery), V2.8 (Multi-Factor Authentication).
- **V3: Session Management:** V3.2 (Token-based Session Management), V3.5 (Token Revocation and Replay Mitigation).
- **V13: API and Web Service Verification:** V13.1 (Load Shedding & Service Hardening), V13.2 (Data Consistency, Pagination & Batch Operations).
- **V14: Configuration Verification:** V14.2 (Upgrade Integrity & Schema Migration).

### Excluded Scope & Known Limits
- **No LDAP / Active Directory Federation:** Users and credentials are managed directly in Keycloak's relational datastore.
- **No External Social Login:** Identity providers (Google, GitHub, Microsoft) are not configured to keep testing deterministic and isolated offline.
- **Local Isolated Stack:** Tests execute against containerized services bound strictly to `127.0.0.1`.

---

## Quickstart & Execution

```powershell
# 1. Start Docker stack
docker compose up -d --wait

# 2. Seed baseline database (10,000 users)
uv run python scripts/seed_users.py

# 3. Install Playwright browser engines
uv run playwright install --with-deps msedge firefox webkit

# 4. Run test suites
uv run pytest tests/oidc.py -v
uv run pytest tests/api/test_replay.py tests/ui/test_mfa_lockout.py tests/ui/test_password_reset.py -v
uv run pytest tests/perf/test_load.py tests/resilience/test_overload.py -v
uv run pytest tests/api/test_pagination.py -v
uv run pytest tests/api/test_partial_import.py -v
uv run pytest tests/migration/test_upgrade.py -v

# 5. Tear down stack
docker compose down -v
```

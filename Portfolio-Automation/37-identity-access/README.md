# Keycloak Identity and Access Management (Project 37)

Quality engineering, protocol compliance, resilience, and security test suite for Keycloak IAM backed by PostgreSQL, Mailpit, and Toxiproxy.

Evaluates OAuth 2.0 / OpenID Connect Core 1.0, PKCE S256, refresh token rotation and replay revocation (RFC 6749, RFC 9700), multi-factor authentication (MFA/TOTP), brute-force account lockout, resilient password reset during SMTP outages, load shedding backpressure, 10k-user deterministic pagination, partial import atomicity, and major schema migration (Keycloak 25 to 26).

---

## Architectural Concerns & Test Verification

| Concern | How It Is Tested | ASVS / RFC Mapping | Test Location |
|---|---|---|---|
| **Cryptographic Token Validation** | Full OIDC Code Flow with PKCE S256 on Microsoft Edge; cryptographic RS256 ID token verification against JWKS (iss, aud, exp, nonce). | RFC 7636, ASVS V3.2.1, V3.2.3 | [`tests/oidc.py`](tests/oidc.py) |
| **Replay & Retry Semantics** | Exchange authorization code twice (`invalid_grant`). With refresh token rotation on, reusing an old refresh token revokes the entire user session. | RFC 6749 §4.1.2, RFC 9700 §4.14, ASVS V3.5.2, V3.5.3 | [`tests/api/test_replay.py`](tests/api/test_replay.py) |
| **MFA & Brute-Force Lockout** | Enroll TOTP via pyotp from QR manual secret. Wrong TOTP counts as failure. Account lockout triggers at exactly $N=3$ consecutive failures across Edge, Firefox, and WebKit. Admin unlock verified. | ASVS V2.2.1, V2.2.2, V2.8.1 | [`tests/ui/test_mfa_lockout.py`](tests/ui/test_mfa_lockout.py) |
| **Resilient Password Reset** | Happy path reset via Mailpit API; action token single-use and expiration. Toxiproxy cuts SMTP: UI displays generic error without disclosing account existence. | ASVS V2.5.2, V2.5.4, V2.5.6 | [`tests/ui/test_password_reset.py`](tests/ui/test_password_reset.py) |
| **Backpressure & Load Shedding** | Async httpx load loop at 10, 50 and 100 rps target (one request in flight at a time, 3 × 4 s windows per rate). Concurrent burst of 300 token requests with `--http-max-queued-requests 20`: excess requests return HTTP 503 and 0 HTTP 500s; recovers within 2s. | ASVS V13.1.5 | [`tests/perf/test_load.py`](tests/perf/test_load.py), [`tests/resilience/test_overload.py`](tests/resilience/test_overload.py) |
| **Admin User Pagination** | Walk 10,000 users via admin REST API with `max` 100, 37, and 1: identical set of IDs, 0 duplicates. Walk during concurrent 300-user insertion: 0 baseline users missed; repeats are allowed up to the number created (see FIND-008). Prefix search agrees with count. | ASVS V13.2.3 | [`tests/api/test_pagination.py`](tests/api/test_pagination.py) |
| **Partial Import Collision Policies** | Import 1,000 users with 50 conflicts under SKIP, OVERWRITE, and FAIL policies on fresh realms. FAIL verified as atomic all-or-nothing rollback (409 Conflict). | ASVS V13.2.1 | [`tests/api/test_partial_import.py`](tests/api/test_partial_import.py) |
| **Major Schema Migration** | **Not in CI yet.** The first version read files from a manual laptop run instead of upgrading the stack; it is being rewritten to start 25.0.6, enroll TOTP, switch to 26.0.5 and log in again. | ASVS V14.2.3 | [`tests/migration/test_upgrade.py`](tests/migration/test_upgrade.py) |

---

## Measured Quality Targets (`targets.toml`)

Numbers from the nightly run [39543095736](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39543095736) on a GitHub `ubuntu-latest` runner (PR gate 9m14s, nightly 11m09s). The PR gate also passed in runs [39539664683](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39539664683) and [39541739365](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39541739365).

| Metric / Requirement | Target | Measured on CI | Result | Test |
|---|---|---|---|---|
| Token endpoint (`client_credentials`) p95 at 50 rps | ≤ 300 ms | 8.34 ms (577 requests, ~48 rps reached) | PASS | [`tests/perf/test_load.py`](tests/perf/test_load.py) |
| Password login p95 at 10 rps | ≤ 800 ms | 51.05 ms (120 requests) | PASS | [`tests/perf/test_load.py`](tests/perf/test_load.py) |
| Unhandled 500s during a 300-request burst | 0 (503 allowed) | 0; every rejection was 503; a request 2 s later got 200 | PASS | [`tests/resilience/test_overload.py`](tests/resilience/test_overload.py) |
| Successful reuse of an auth code or rotated refresh token | 0 | 0 | PASS | [`tests/api/test_replay.py`](tests/api/test_replay.py) |
| Lockout after failed attempts (Edge, Firefox, WebKit) | exactly 3 | 3 | PASS | [`tests/ui/test_mfa_lockout.py`](tests/ui/test_mfa_lockout.py) |
| Baseline users missed in a 10k walk with 300 created mid-walk | 0 | 0 missed, 300 repeated (FIND-008) | PASS | [`tests/api/test_pagination.py`](tests/api/test_pagination.py) |
| Partial import of 1,000 users with 50 conflicts (SKIP, OVERWRITE, FAIL) | FAIL is all-or-nothing | 3/3 policies as specified | PASS | [`tests/api/test_partial_import.py`](tests/api/test_partial_import.py) |
| Major upgrade 25.0.6 → 26.0.5 | ≤ 300 s | not measured on CI yet | — | [`tests/migration/test_upgrade.py`](tests/migration/test_upgrade.py) |

Other load numbers from the same run (p95): `client_credentials` 10.99 ms at 10 rps and 6.76 ms at 100 rps (~94 rps reached). A password login takes about 40 ms, so with one request in flight the loop tops out near 26 rps: the 50 and 100 rps login steps reached ~26 and ~27 rps (p95 45.36 ms and 42.08 ms). They show latency, not capacity at those rates.

On CI the 10,000-user seed needed two retries: Keycloak (memory limit 1.5 GB) dropped the connection during the first import batch. The seed script retries dropped batches, and `ifResourceExists=SKIP` makes the retry safe.
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

# Security & Operational Quality Findings — Keycloak IAM (Project 37)

This document formalizes the security and operational resilience findings identified during the quality verification of the Keycloak Identity and Access Management (IAM) stack. All requirements and evaluations are **modeled on OWASP ASVS v4.0.3**, RFC 6749, RFC 7636, and RFC 9700.

---

## Summary of Findings

| ID | Title | Related ASVS / RFC | Severity | Status / Behavior |
|---|---|---|---|---|
| **FIND-001** | Refresh Token Replay Cascading Session Revocation | ASVS V3.5.3, RFC 9700 §4.14 | **High** | Secure / Compliant |
| **FIND-002** | Anti-Enumeration Protection on SMTP Downstream Outage | ASVS V2.5.4, V2.5.6 | **Medium** | Secure / Compliant |
| **FIND-003** | Rapid-Burst Heuristic Mitigation vs Failure Threshold | ASVS V2.2.1, V2.2.2 | **Informational** | Documented & Tuned |
| **FIND-004** | Netty Queue Load Shedding Under Concurrency Bursts | ASVS V13.1.5 | **High** | Resilient / Backpressure OK |
| **FIND-005** | Master Realm Administrative Token Short Expiration | ASVS V13.2.3, V3.2.1 | **Low** | Operational / Handled |
| **FIND-006** | Atomicity and Rollback in Partial Import Collisions | ASVS V13.2.1 | **Medium** | Atomic / All-or-Nothing |
| **FIND-007** | Major Schema Upgrade Credential & Secret Continuity | ASVS V14.2.3 | **Critical** | Zero Regression |
| **FIND-008** | Admin user list repeats users when users are created mid-walk | — | **Low** | Offset pagination; dedupe by ID |

---

## Detailed Security Findings

### FIND-001: Refresh Token Replay Cascading Session Revocation
- **Severity:** High
- **Specification:** OWASP ASVS v4.0.3 V3.5.3 ("Verify that re-use of revoked or rotated tokens is prevented"), RFC 9700 §4.14 ("Refresh Token Compromise").
- **Observation:** When refresh token rotation (`revokeRefreshToken: true`) is active, exchanging a refresh token returns a new token pair and marks the previous refresh token as consumed. When an attacker or replayed request submits the previously used refresh token:
  1. Keycloak rejects the request with HTTP 400 and error code `invalid_grant`.
  2. In accordance with RFC 9700 §4.14, Keycloak invalidates the underlying user session (`UserSessionModel`), which automatically revokes the newly issued refresh token and marks all active access tokens as inactive upon token introspection.
- **Remediation / Configuration:** Ensure `refreshTokenMaxReuse: 0` and `revokeRefreshToken: true` remain active in realm configuration.

### FIND-002: Anti-Enumeration Protection on SMTP Downstream Outage
- **Severity:** Medium
- **Specification:** OWASP ASVS v4.0.3 V2.5.4, V2.5.6 ("Verify the application displays generic messages on password reset requests").
- **Observation:** When downstream SMTP infrastructure is severed (simulated via Toxiproxy cutting upstream connection to Mailpit), submitting a password reset request displays:
  > *"Failed to send email, please try again later."*
  The response is uniform regardless of whether the submitted username exists in the realm or not. No usernames, email addresses, or system error stack traces are reflected back to the client.
- **Remediation / Configuration:** Keep custom login theme error messages aligned with the default generic response.

### FIND-003: Rapid-Burst Heuristic Mitigation vs Exact Lockout Threshold
- **Severity:** Informational
- **Specification:** OWASP ASVS v4.0.3 V2.2.1, V2.2.2.
- **Observation:** Keycloak's brute-force attack detection includes `quickLoginCheckMilliSeconds` (default: 1000ms). Submitting multiple failed credentials within a 1-second interval triggers rapid-burst mitigation before the configured `failureFactor` (e.g. $N=3$) is reached. In high-speed automated integration test suites, setting `quickLoginCheckMilliSeconds: 0` isolates the exact failure count threshold for deterministic validation.
- **Remediation / Configuration:** In production, leave `quickLoginCheckMilliSeconds: 1000` enabled for defense-in-depth against scripted bots.

### FIND-004: Netty Queue Load Shedding Under Concurrency Bursts
- **Severity:** High
- **Specification:** OWASP ASVS v4.0.3 V13.1.5.
- **Observation:** Under a concurrent burst of 300 simultaneous token requests with `--http-max-queued-requests 20`, Keycloak gracefully sheds excess load by returning HTTP `503 Service Unavailable` (*"Server not Available"*) for 216 requests. Exactly 0 unhandled HTTP 500 internal server errors occurred, and the service recovered instantly (HTTP 200 within 2 seconds). This protects the PostgreSQL thread and connection pools from exhaustion.
- **Remediation / Configuration:** Size `--http-max-queued-requests` and worker pool threads proportionally to database connection pool limits.

### FIND-005: Master Realm Administrative Token Short Expiration
- **Severity:** Low
- **Specification:** OWASP ASVS v4.0.3 V13.2.3.
- **Observation:** Access tokens issued to `admin-cli` in the `master` realm have an enforced lifespan of 60 seconds. Long-running batch operations (such as walking 10,000 users with `max=1` taking ~66 seconds) fail midway with `401 Unauthorized` if tokens are not proactively refreshed.
- **Remediation / Configuration:** Automated scripts and API consumers must use token management wrappers (`_AdminAuthManager`) that dynamically renew tokens before the 60-second boundary.

### FIND-006: Atomicity and Rollback in Partial Import Collisions
- **Severity:** Medium
- **Specification:** OWASP ASVS v4.0.3 V13.2.1.
- **Observation:** When executing `/admin/realms/{realm}/partialImport` with policy `ifResourceExists: "FAIL"` on a payload containing both new users and conflicting users, encountering a duplicate throws a `ModelDuplicateException`. Keycloak executes the import inside a unified Jakarta Transaction (JTA). The transaction rolls back atomically, leaving the database completely clean with 0 new users persisted.
- **Remediation / Configuration:** Document policy behavior: use `FAIL` when strict atomicity is required, or `SKIP` / `OVERWRITE` for idempotent ETL imports.

### FIND-007: Major Schema Upgrade Credential & Secret Continuity
- **Severity:** Critical
- **Specification:** OWASP ASVS v4.0.3 V14.2.3.
- **Observation:** An automated major version upgrade from Keycloak 25.0.6 (N-1) to Keycloak 26.0.5 (N) over 10,000 seeded users executed 10 Liquibase change sets in **15.06 seconds** (SLA $\le$ 300s). All 20 enrolled TOTP secrets and Argon2 password hashes remained fully functional, authenticating 20 out of 20 users without credential invalidation or re-enrollment. Confidential client secrets remained identical (`confidential-secret-1234`).
- **Remediation / Configuration:** Maintain database backup snapshots (`results/snapshot_n1.sql`) before production upgrades.

### FIND-008: Admin user list repeats users when users are created mid-walk
- **Severity:** Low
- **Observation:** `GET /admin/realms/{realm}/users` pages with `first`/`max`, an offset into the list sorted by username. In CI run [39540623713](https://github.com/valarcon1226/IBM-Agentric-IA-labs/actions/runs/39540623713), 300 users named `conc_user_p8_*` were imported while a walk of 10,000 users was past that point in the alphabet. Every later page shifted by 300, and the walk returned exactly 300 baseline users twice. No user was missed. On the laptop the import landed ahead of the cursor, so the same test saw 0 repeats; the result depends on timing.
- **Remediation / Configuration:** Clients that export or sync users must deduplicate by user ID, or page by a stable key (for example a username range with `search`) instead of an offset. Deleting users during a walk would shift the list the other way and skip users; that case is not tested here.

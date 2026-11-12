# Traceability Matrix

Generated automatically by qa_common pytest plugin.

| Requirement | Test | Outcome |
|-------------|------|---------|
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_admin_unlock_via_api[firefox]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_admin_unlock_via_api[msedge]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_admin_unlock_via_api[webkit]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_happens_at_exactly_configured_failures[firefox]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_happens_at_exactly_configured_failures[msedge]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_happens_at_exactly_configured_failures[webkit]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_lasts_configured_time_and_expires[firefox]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_lasts_configured_time_and_expires[msedge]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_lockout_lasts_configured_time_and_expires[webkit]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_totp_enrollment_and_login_flow[firefox]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_totp_enrollment_and_login_flow[msedge]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_totp_enrollment_and_login_flow[webkit]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_wrong_totp_code_counts_as_failure[firefox]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_wrong_totp_code_counts_as_failure[msedge]` | PASSED |
| REQ-IAM-001 | `tests/ui/test_mfa_lockout.py::test_wrong_totp_code_counts_as_failure[webkit]` | PASSED |
| REQ-IAM-002 | `tests/api/test_replay.py::test_authorization_code_replayed_returns_invalid_grant_and_revokes_tokens` | PASSED |
| REQ-IAM-002 | `tests/api/test_replay.py::test_parallel_refreshes_behavior_documented` | PASSED |
| REQ-IAM-002 | `tests/api/test_replay.py::test_refresh_token_rotation_and_old_token_reuse_revokes_session` | PASSED |
| REQ-IAM-003 | `tests/oidc.py::test_oidc_happy_path_pkce_s256` | PASSED |
| REQ-IAM-003 | `tests/oidc.py::test_oidc_negative_missing_pkce_on_enforced_client` | PASSED |
| REQ-IAM-003 | `tests/oidc.py::test_oidc_negative_nonce_mismatch` | PASSED |
| REQ-IAM-003 | `tests/oidc.py::test_oidc_negative_redirect_uri_mismatch` | PASSED |
| REQ-IAM-003 | `tests/oidc.py::test_oidc_negative_wrong_code_verifier` | PASSED |
| REQ-IAM-004 | `tests/ui/test_password_reset.py::test_password_reset_happy_path_and_replay_and_expiration` | PASSED |
| REQ-IAM-004 | `tests/ui/test_password_reset.py::test_password_reset_smtp_down_and_recovery` | PASSED |
| REQ-IAM-005 | `tests/perf/test_load.py::test_client_credentials_token_latency` | PASSED |
| REQ-IAM-005 | `tests/perf/test_load.py::test_password_login_latency` | PASSED |
| REQ-IAM-005 | `tests/resilience/test_overload.py::test_backpressure_sheds_load_with_503_and_recovers` | PASSED |
| REQ-IAM-006 | `tests/api/test_pagination.py::test_admin_pagination_concurrent_creation_during_walk` | PASSED |
| REQ-IAM-006 | `tests/api/test_pagination.py::test_admin_pagination_search_prefix_agrees_with_count` | PASSED |
| REQ-IAM-006 | `tests/api/test_pagination.py::test_admin_pagination_walk_with_different_page_sizes` | PASSED |
| REQ-IAM-007 | `tests/api/test_partial_import.py::test_partial_import_fail_policy` | PASSED |
| REQ-IAM-007 | `tests/api/test_partial_import.py::test_partial_import_overwrite_policy` | PASSED |
| REQ-IAM-007 | `tests/api/test_partial_import.py::test_partial_import_skip_policy` | PASSED |
| REQ-IAM-008 | `tests/migration/test_upgrade.py::test_keycloak_major_version_upgrade_25_to_26` | PASSED |

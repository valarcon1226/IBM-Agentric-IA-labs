# Traceability Matrix — Data Cleaning & Transformation API

**Analysis date:** 2026-09-24 (updated after auth, error-handling and config fixes)
**Status:** 24 of 33 scenarios automated by 27 passing tests. The other 9 are `Not Implemented` and have no test path listed.

| Area       | Risk   | Scenario ID | Scenario                                                   | Priority | Decision       | Status          | Automated test                                                  |
| ---------- | ------ | ----------- | ---------------------------------------------------------- | -------- | -------------- | --------------- | --------------------------------------------------------------- |
| Ops        | DC-R01 | DC-OPS-001  | Production app exposes every documented `/api/v1` route    | Critical | Automate       | Implemented     | `tests/test_api.py::test_production_app_exposes_versioned_routes` |
| Ops        | DC-R10 | DC-OPS-002  | Health returns 200 when DB and Redis respond               | Medium   | Automate       | Implemented     | `tests/test_api.py::test_health_ok_when_dependencies_respond`   |
| Ops        | DC-R10 | DC-OPS-003  | Health returns 503 when the DB fails                       | Medium   | Automate       | Implemented     | `tests/test_api.py::test_health_reports_503_when_database_fails` |
| Ops        | DC-R08 | DC-OPS-004  | `.env.example` satisfies every required setting            | High     | Automate       | Implemented     | `tests/test_config.py::test_env_example_satisfies_required_settings` |
| Ops | DC-R08 | DC-OPS-005 | Storage and config read the same bucket variable | Medium | Automate | Implemented | `tests/test_api.py::test_storage_uses_configured_bucket` |
| Ops        | DC-R10 | DC-OPS-006  | Health stays public while `/api/v1` requires a key         | Medium   | Automate       | Implemented     | `tests/test_api.py::test_health_does_not_require_api_key`       |
| Contract   | DC-R13 | DC-DOC-001  | README transform/enrich request bodies are accepted (200)  | High     | Automate       | Implemented     | `tests/test_api.py::test_transform_accepts_documented_payload`, `tests/test_api.py::test_enrich_accepts_documented_payload` |
| Contract   | DC-R13 | DC-DOC-002  | Internal Celery argument shape is rejected by the API (422) | Medium  | Automate       | Implemented     | `tests/test_api.py::test_transform_rejects_internal_task_shape` |
| Security | DC-R03 | DC-SEC-001 | Request without API key is rejected with 401 | Critical | Automate | Implemented | `tests/test_api.py::test_api_rejects_missing_api_key`, `tests/test_api.py::test_api_rejects_wrong_api_key` |
| Security | DC-R03 | DC-SEC-002 | Request with valid API key is accepted | Critical | Automate | Implemented | `tests/test_api.py::test_clean_small_file_sync` (and every authenticated test) |
| Security | DC-R12 | DC-SEC-003 | 500 responses do not expose exception details | Low | Automate | Implemented | `tests/test_api.py::test_internal_errors_do_not_leak_details` |
| Cleaning   | DC-R02 | DC-CLEAN-001 | Duplicate rows removed                                    | High     | Automate       | Implemented     | `tests/test_cleaner.py::test_remove_duplicates`, `tests/test_api.py::test_clean_small_file_sync` |
| Cleaning   | DC-R02 | DC-CLEAN-002 | Numeric nulls interpolated                                | High     | Automate       | Implemented     | `tests/test_cleaner.py::test_fill_na_interpolate`               |
| Cleaning   | DC-R02 | DC-CLEAN-003 | Surrounding whitespace trimmed                            | Medium   | Automate       | Implemented     | `tests/test_cleaner.py::test_trim_whitespace`                   |
| Cleaning   | DC-R02 | DC-CLEAN-004 | Fully empty rows dropped                                  | Medium   | Automate       | Implemented     | `tests/test_cleaner.py::test_remove_empty_rows`                 |
| Cleaning   | DC-R02 | DC-CLEAN-005 | `handle_nulls=drop` / `fill_value` behave as documented   | High     | Automate       | Not Implemented |                                                                 |
| Cleaning   | DC-R05 | DC-CLEAN-006 | Malformed options JSON returns 400                        | High     | Automate       | Implemented     | `tests/test_api.py::test_clean_rejects_malformed_options_json`  |
| Cleaning | DC-R05 | DC-CLEAN-007 | Unparseable CSV returns a 4xx with a usable message | High | Automate | Implemented | `tests/test_api.py::test_clean_rejects_empty_file`, `tests/test_api.py::test_clean_rejects_non_utf8_file` |
| Cleaning   | DC-R06 | DC-CLEAN-008 | File above threshold is queued, not processed inline      | High     | Automate       | Implemented     | `tests/test_api.py::test_clean_large_file_is_queued_not_processed_inline` |
| Cleaning   | DC-R09 | DC-CLEAN-009 | Excel and JSON uploads accepted                           | High     | Automate       | Not Implemented |                                                                 |
| Validation | DC-R07 | DC-VAL-001  | Valid rows reported as `valid`                             | High     | Automate       | Implemented     | `tests/test_api.py::test_validate_valid_data`                   |
| Validation | DC-R07 | DC-VAL-002  | Invalid rows reported with failure cases                   | High     | Automate       | Implemented     | `tests/test_api.py::test_validate_invalid_data`                 |
| Validation | DC-R07 | DC-VAL-003  | Unknown schema returns 404                                 | Medium   | Automate       | Implemented     | `tests/test_api.py::test_validate_unknown_schema_returns_404`   |
| Validation | DC-R07 | DC-VAL-004  | Schema created via `/schemas` is usable in `/validate`     | High     | Automate       | Not Implemented |                                                                 |
| Schemas    | DC-R07 | DC-SCH-001  | Schema can be created                                      | Medium   | Automate       | Implemented     | `tests/test_api.py::test_create_schema`                         |
| Schemas    | DC-R07 | DC-SCH-002  | Schemas can be listed                                      | Low      | Automate       | Implemented     | `tests/test_api.py::test_list_schemas`                          |
| Schemas    | DC-R07 | DC-SCH-003  | Schemas survive a restart (persisted in Postgres)          | High     | Automate       | Not Implemented |                                                                 |
| Jobs       | DC-R04 | DC-JOB-001  | Unknown job result returns 404                             | Medium   | Automate       | Implemented     | `tests/test_api.py::test_unknown_job_result_returns_404`        |
| Jobs       | DC-R04 | DC-JOB-002  | Job moves PROCESSING → COMPLETED / FAILED                  | Critical | Automate       | Not Implemented |                                                                 |
| Jobs       | DC-R04 | DC-JOB-003  | Completed job returns a working download URL               | High     | Automate       | Not Implemented |                                                                 |
| Jobs       | DC-R04 | DC-JOB-004  | Full stack: upload → async clean → poll → download         | Critical | Manual         | Not Implemented |                                                                 |
| Transform  | DC-R11 | DC-TRF-001  | pivot / melt / merge / split / aggregate produce expected shapes | Medium | Automate    | Not Implemented |                                                                 |
| Enrich     | DC-R11 | DC-ENR-001  | Email validation and phone normalization flag bad values   | Medium   | Automate       | Not Implemented |                                                                 |

## Coverage interpretation

Every scenario maps to at least one risk in [`RISK-ANALYSIS.md`](RISK-ANALYSIS.md). Two Critical risks (DC-R02 partially, DC-R04)
still have open scenarios, so this service is **not production-ready**. It is
a working synchronous cleaning/validation API with a documented roadmap for auth, job persistence,
and multi-format input.

Line coverage from `pytest --cov` is 58%. That number reflects executed lines, not verified
behaviour; this matrix is the source of truth for the second.

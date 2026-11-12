# Traceability Matrix

Generated automatically by qa_common pytest plugin.

| Requirement | Test | Outcome |
|-------------|------|---------|
| REQ-ING-001 | `tests/resilience/test_burst.py::test_burst_500_upload_accounting` | PASSED |
| REQ-ING-002 | `tests/resilience/test_faults.py::test_fault_redis_restart` | XFAIL |
| REQ-ING-002 | `tests/resilience/test_faults.py::test_fault_toxiproxy_connection_cut` | PASSED |
| REQ-ING-002 | `tests/resilience/test_faults.py::test_fault_toxiproxy_timeout_toxic` | PASSED |
| REQ-ING-003 | `tests/resilience/test_faults.py::test_retry_idempotency_10_completed_tasks` | PASSED |
| REQ-ING-003 | `tests/resilience/test_faults.py::test_retry_idempotency_single_file` | PASSED |
| REQ-ING-004 | `tests/api/test_partial.py::test_corrupt_file_isolated_failure` | PASSED |
| REQ-ING-005 | `tests/api/test_partial.py::test_bulk_edit_partial_missing_ids` | PASSED |
| REQ-ING-006 | `tests/api/test_partial.py::test_password_protected_pdf_rejection` | PASSED |
| REQ-ING-007 | `tests/api/test_pagination.py::test_page_size_limits_and_invalid_page` | PASSED |
| REQ-ING-007 | `tests/api/test_pagination.py::test_pagination_sort_ties_consistency` | PASSED |
| REQ-ING-008 | `tests/api/test_pagination.py::test_full_text_search_and_latencies` | PASSED |
| REQ-ING-008 | `tests/api/test_pagination.py::test_index_freshness` | PASSED |
| REQ-ING-009 | `tests/eval/test_classifier.py::test_classifier_pre_registered_eval` | PASSED |
| REQ-ING-010 | `tests/migration/test_upgrade.py::test_schema_upgrade_n1_to_n` | PASSED |
| REQ-ING-011 | `tests/ui/test_document_flow.py::test_01_ui_upload_through_file_input` | PASSED |
| REQ-ING-011 | `tests/ui/test_document_flow.py::test_02_find_document_with_search` | PASSED |
| REQ-ING-011 | `tests/ui/test_document_flow.py::test_03_edit_document_tags_and_verify` | PASSED |
| REQ-ING-011 | `tests/ui/test_document_flow.py::test_04_axe_core_accessibility_scan` | XFAIL |

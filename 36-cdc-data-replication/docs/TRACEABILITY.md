# Traceability Matrix

Generated automatically by qa_common pytest plugin.

| Requirement | Test | Outcome |
|-------------|------|---------|
| REQ-CDC-002 | `tests/perf/test_lag.py::test_replication_lag_under_load` | PASSED |
| REQ-CDC-003 | `tests/resilience/test_slow_sink.py::test_slow_sink_backpressure_and_recovery` | PASSED |
| REQ-CDC-004 | `tests/resilience/test_crash.py::test_crash_connect_worker_redelivery` | PASSED |
| REQ-CDC-004 | `tests/resilience/test_crash.py::test_crash_source_postgres_recovery` | PASSED |
| REQ-CDC-005 | `tests/resilience/test_poison.py::test_kafka_connect_dlq_poison_pill_routing` | PASSED |
| REQ-CDC-005 | `tests/resilience/test_poison.py::test_poison_row_isolation_and_dlq` | PASSED |
| REQ-CDC-005 | `tests/resilience/test_poison.py::test_stricter_warehouse_constraint_failure_behavior` | FAILED |
| REQ-CDC-006 | `tests/migration/test_schema_changes.py::test_migration_1_add_nullable_backfill_set_not_null` | PASSED |
| REQ-CDC-006 | `tests/migration/test_schema_changes.py::test_migration_2_rename_column_expand_contract` | PASSED |
| REQ-CDC-006 | `tests/migration/test_schema_changes.py::test_migration_3_widen_int_to_bigint` | PASSED |
| REQ-CDC-006 | `tests/migration/test_schema_changes.py::test_migration_4_add_column_with_default` | PASSED |
| REQ-CDC-007 | `tests/migration/test_snapshot_upgrade.py::test_connector_upgrade_n_minus_1_to_n` | PASSED |
| REQ-CDC-007 | `tests/ops/test_snapshot_upgrade.py::test_initial_snapshot_1m_rows` | PASSED |

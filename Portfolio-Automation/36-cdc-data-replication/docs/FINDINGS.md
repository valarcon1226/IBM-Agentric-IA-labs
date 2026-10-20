# Findings and System Limitations (CDC Replication Suite)

Defects, unexpected behaviors, and architectural edge cases identified during quality and resilience testing of the CDC replication pipeline (PostgreSQL 16, Debezium 2.7.3/2.6.2, Redpanda 24.2.7).

---

### FINDING-001: Debezium JDBC Sink Connector Lacks KIP-610 ErrantRecordReporter Support for SQL Constraint Violations
- **Component:** `io.debezium.connector.jdbc.JdbcSinkConnector` (Debezium 2.7.3.Final / 2.6.2.Final)
- **Severity:** High
- **Upstream Issue:** [DBZ-7877 / GitHub #984](https://github.com/debezium/debezium/issues/984)
- **Observed Behavior:**
  When a message payload arrives at the warehouse database that violates a relational constraint (such as a PostgreSQL `CHECK` constraint or tighter column length limit not present on the source), the JDBC Sink connector fails the entire batch and crashes the task into `FAILED` state:
  ```text
  org.apache.kafka.connect.errors.ConnectException: Exiting WorkerSinkTask due to unrecoverable exception
  Caused by: org.postgresql.util.PSQLException: ERROR: new row for relation "ledger" violates check constraint "chk_amount_positive"
  ```
  Despite configuring `errors.tolerance=all` and `errors.deadletterqueue.topic.name=dlq_ledger`, the faulty message is **not** routed to the DLQ.
- **Root Cause:**
  Kafka Connect KIP-610 introduced the `ErrantRecordReporter` interface allowing sink connectors to isolate individual database errors to the Dead Letter Queue. The Debezium JDBC Sink connector implementation does not invoke `ErrantRecordReporter.report(...)` upon catching `SQLException`, but instead wraps it in an unrecoverable `ConnectException`.
  DLQ routing currently functions only for Key/Value Converter and Single Message Transform (SMT) serialization failures.
- **Mitigation / Safe Pattern:**
  1. Enforce identical DDL constraints between source and warehouse databases.
  2. Implement pre-replication schema validation in producer applications or Kafka Connect SMTs.

---

### FINDING-002: Basic Schema Evolution Does Not Support In-Place Type Widening
- **Component:** `io.debezium.connector.jdbc.RecordWriter` / `schema.evolution: basic`
- **Severity:** Medium
- **Observed Behavior:**
  When a source column is migrated from `integer` to `bigint` under active workload, Debezium Postgres source connector detects `Type.INT64` and emits 64-bit integer values in the CDC stream.
  However, `schema.evolution: basic` in the JDBC Sink connector only issues `ALTER TABLE ... ADD COLUMN` for non-existent columns; it never alters existing column data types.
  When a value exceeds `2,147,483,647` (e.g. `5,000,000,000`), PostgreSQL warehouse aborts with:
  ```text
  org.postgresql.util.PSQLException: ERROR: value "5000000000" is out of range for type integer
  ```
- **Root Cause:**
  Automatic column type mutation in live production tables carries high risk of table-rewrite locks or unexpected truncation. Debezium purposefully restricts `basic` evolution to additive operations.
- **Standard Operating Procedure:**
  Apply type widening in reverse order (**downstream warehouse first**):
  1. Run `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;` on warehouse.
  2. Verify pipeline health.
  3. Run `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;` on source database.

---

### FINDING-003: Hibernate Column Metadata Caching Requires Task Restart for Online Schema Synchronization
- **Component:** Kafka Connect JDBC Sink Connection Pool / Hibernate
- **Severity:** Low
- **Observed Behavior:**
  After executing certain DDL statements directly against warehouse tables, subsequent write operations may intermittently report `PSQLException: column does not exist` or use stale type mappings until the sink task is restarted via the Connect REST API (`POST /connectors/jdbc-sink/tasks/0/restart`).
- **Root Cause:**
  The underlying JDBC dialect and statement preparer cache PostgreSQL catalog metadata for the lifetime of the database session pool.
- **Mitigation:**
  Automate task restart via deployment hooks whenever non-additive DDL is executed against the warehouse.

# Risk Analysis — CDC Data Replication Pipeline

This document analyzes operational and data integrity risks for the change-data-capture (CDC) replication pipeline (PostgreSQL $\rightarrow$ Debezium $\rightarrow$ Redpanda $\rightarrow$ JDBC Sink $\rightarrow$ PostgreSQL Warehouse).

## Risk Matrix Methodology

- **Likelihood ($L$):** 1 (Rare) to 5 (Frequent / Expected under churn)
- **Impact ($I$):** 1 (Insignificant) to 5 (Catastrophic / Severe data corruption)
- **Risk Score ($R = L \times I$):**
  - **High ($R \ge 15$):** Critical risk requiring mandatory automated verification in CI (P1 Tier).
  - **Medium ($8 \le R \le 14$):** Managed risk covered in secondary suites or monitoring.
  - **Low ($R < 8$):** Accepted risk.

## Risk Assessment and Requirement Mapping

| Risk ID | Failure Mode | $L$ | $I$ | $R$ | Severity | Mapped Requirement | Verification Test |
|---|---|---|---|---|---|---|---|
| **RISK-DATA-LOSS** | Uncommitted WAL events or worker crash leads to missing records in analytics warehouse. | 4 | 5 | **20** | **High** | `REQ-CDC-001`, `REQ-CDC-004` | `test_crash.py`, `reconcile_ledger` |
| **RISK-DUPLICATES** | Network retry or worker re-delivery causes phantom row duplications or double counting. | 5 | 4 | **20** | **High** | `REQ-CDC-001`, `REQ-CDC-004` | `test_crash.py`, `reconcile_ledger` |
| **RISK-ORDERING** | Out-of-order delivery results in an older UPDATE overwriting a newer state or resurrecting deleted rows. | 4 | 4 | **16** | **High** | `REQ-CDC-001` | `test_reconciler.py`, `test_lag.py` |
| **RISK-SCHEMA-DRIFT** | DDL migration on source breaks the sink connector, dropping events or causing silent divergence. | 4 | 4 | **16** | **High** | `REQ-CDC-006` | `test_schema_changes.py` |
| **RISK-BACKPRESSURE** | Slow warehouse ingestion blocks Redpanda broker buffers or causes unbounded lag. | 4 | 4 | **16** | **High** | `REQ-CDC-003` | `test_slow_sink.py` |
| **RISK-POISON** | Record violating target schema constraint crashes the connector task or silently vanishes. | 4 | 4 | **16** | **High** | `REQ-CDC-005` | `test_poison.py` |
| **RISK-CONNECTOR-UPGRADE** | Upgrading Debezium image loses consumer offsets, triggering duplicate snapshots or missing gaps. | 3 | 5 | **15** | **High** | `REQ-CDC-008` | `test_upgrade.py` |
| **RISK-SNAPSHOT-GAP** | Initial 1M-row bootstrap misses rows due to concurrent transactional lock contention or pagination gaps. | 3 | 5 | **15** | **High** | `REQ-CDC-007` | `test_snapshot.py` |
| **RISK-RECONCILER** | Reconciler produces false positives during concurrent writes or fails to meet latency targets. | 3 | 4 | **12** | **Medium** | `REQ-CDC-009` | `test_reconciler.py`, `benchmark_reconciler_1m.py` |

## Detailed Risk Profiles

### 1. RISK-DATA-LOSS: Uncommitted WAL Events or Worker Crash
- **Context:** If the Kafka Connect worker or the source Postgres instance is terminated ungracefully, in-flight WAL events could be lost if offsets are improperly tracked.
- **Mitigation & Guarantee:** At-least-once delivery with durable replication slots (`wal_level=logical`) and persistent offset topics (`connect_offsets`).
- **Target:** 0 differences between source and warehouse post-recovery.

### 2. RISK-DUPLICATES: Redelivery Under Faults
- **Context:** At-least-once delivery guarantees that every record is delivered *at least* once. When faults occur, redeliveries are inevitable.
- **Mitigation & Guarantee:** Sink connector runs in `upsert` mode keyed by primary key (`record_key`). Redelivered rows are absorbed idempotently via `INSERT ... ON CONFLICT (id) DO UPDATE`.

### 3. RISK-ORDERING: Partition Partitioning and Causality
- **Context:** Multiple Kafka partitions or concurrent threads could process updates out of order.
- **Mitigation:** Source connector partitions topics strictly by primary key (`id`). All events for a single ledger row are strictly ordered in the same partition.

### 4. RISK-SCHEMA-DRIFT: Uncoordinated DDL Alterations
- **Context:** Upstream developers alter columns (add, drop, rename, widen) without coordinating with warehouse schemas.
- **Mitigation:** Debezium `schema.evolution: basic` handles additive changes; incompatibilities must be routed to DLQ rather than silently lost.

### 5. RISK-BACKPRESSURE: Downstream Latency Spikes
- **Context:** High downstream load adds latency to warehouse inserts, building up consumer lag.
- **Mitigation:** Redpanda broker buffers streaming events. Once latency normalizes, the sink connector must catch up without data loss or memory exhaustion.

### 6. RISK-POISON: Constraint Violations
- **Context:** A payload valid in source fails a stricter warehouse constraint (e.g., CHECK or VARCHAR length).
- **Mitigation:** Kafka Connect `errors.tolerance=all` with DLQ routing (`dlq_ledger`) isolates bad rows with diagnostic headers while allowing healthy traffic to flow unimpeded.

### 7. RISK-CONNECTOR-UPGRADE: Engine Migration Regressions
- **Context:** Upgrading connector versions from N-1 to N might corrupt offset serialization or re-trigger unwanted snapshot phases.
- **Mitigation:** Pinned offset storage topic compatibility and verification of seamless resumption.

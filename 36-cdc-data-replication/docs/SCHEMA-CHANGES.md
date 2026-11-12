# Schema Migrations Under Load in CDC Pipelines

This document details the observed behavior, failure domains, and safe production patterns for applying online schema changes (DDL) to a PostgreSQL source database replicated continuously via Debezium CDC and Kafka Connect JDBC Sink into a target PostgreSQL data warehouse.

---

## 1. Summary Matrix of Schema Changes

| Schema Change | SUT Observed Outcome | Debezium / Sink Behavior | How to Make It Safe (Production Pattern) |
| :--- | :--- | :--- | :--- |
| **1. Add nullable column, backfill, SET NOT NULL** | **Supported** (with bounded backfill) | Debezium captures the DDL and updates the Avro/JSON schema. The JDBC sink (`schema.evolution: basic`) executes `ALTER TABLE ledger ADD COLUMN ...` in the warehouse automatically. | **Expand/Contract with Bounded Backfill:**<br>1. `ADD COLUMN <col> <type>` (instant metadata DDL).<br>2. Backfill in small indexed keyset chunks (`LIMIT 1000..5000`), never a full-table `UPDATE` that would flood WAL with 1M CDC events.<br>3. `ALTER COLUMN <col> SET DEFAULT ...`<br>4. `ALTER COLUMN <col> SET NOT NULL`. |
| **2. Rename column (Expand/Contract)** | **Supported** (Additive in Warehouse) | Direct `ALTER TABLE RENAME` drops old column mapping in Debezium and can break downstream readers. With Expand/Contract, both old and new columns replicate cleanly. | **Two-Phase Expand/Contract:**<br>1. Expand: `ADD COLUMN <new_col>` in source.<br>2. Dual-write/copy: application populates `<new_col>` and backfills missing historical rows.<br>3. Switch readers to `<new_col>`.<br>4. Contract: `DROP COLUMN <old_col>` on source. Note: `schema.evolution: basic` preserves `<old_col>` in warehouse for historical queries without data loss. |
| **3. Widen int to bigint** | **Sink Crash / Range Error if Unordered** | Debezium detects `int64` in the source event schema, but `schema.evolution: basic` **does not alter existing column types** in the target warehouse. When values exceed `2,147,483,647`, PostgreSQL warehouse rejects the insert with `value out of range for type integer`, crashing the sink task. | **Downstream-First Migration:**<br>1. Pre-widen warehouse: `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;`<br>2. Verify warehouse accepts 64-bit values.<br>3. Widen source: `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;`<br>4. Resume/continue writes. Both sides now support 64-bit integers with zero downtime. |
| **4. Add column with DEFAULT** | **Supported** (Instant DDL) | In PostgreSQL 11+, `ADD COLUMN ... DEFAULT <val>` updates catalog metadata without rewriting the table. Debezium captures the schema change with `defaultValue` metadata; JDBC sink provisions the column in warehouse. | **Instant DDL Safe:**<br>Always supply a static default (avoid volatile functions like `random()` or `clock_timestamp()` during DDL). Existing and newly inserted rows replicate with 0 differences. |

---

## 2. In-Depth Technical Analysis

### Scenario 1: Add Nullable Column $\rightarrow$ Backfill $\rightarrow$ `SET NOT NULL`
- **Source DDL:**
  ```sql
  -- Step 1: Add nullable column (instant)
  ALTER TABLE ledger ADD COLUMN IF NOT EXISTS tier_code text;

  -- Step 2: Bounded Backfill (keyset pagination)
  UPDATE ledger SET tier_code = 'STANDARD'
  WHERE id IN (
      SELECT id FROM ledger WHERE tier_code IS NULL LIMIT 5000
  );

  -- Step 3: Enforce NOT NULL with default
  ALTER TABLE ledger ALTER COLUMN tier_code SET DEFAULT 'STANDARD';
  ALTER TABLE ledger ALTER COLUMN tier_code SET NOT NULL;
  ```
- **CDC Operational Danger:**
  Running an unconstrained `UPDATE ledger SET tier_code = 'STANDARD';` over a 1,000,000-row table produces 1,000,000 individual PostgreSQL WAL records. Debezium logical decoding must read, serialize, and publish 1,000,000 CDC update events into Redpanda, creating massive consumer lag (> 400,000 messages) that temporarily chokes the pipeline.
- **Remediation:**
  Always throttle backfills in batches of 1,000–5,000 rows with a sleep interval between batches to allow the CDC pipeline to drain stably.

---

### Scenario 2: Rename Column via Expand/Contract
- **Why Naive `RENAME` Fails in CDC:**
  A native `ALTER TABLE ledger RENAME COLUMN old_name TO new_name;` causes Debezium to immediately stop publishing `old_name` and start publishing `new_name`. If the warehouse table still expects `old_name` or if downstream analytics queries expect either column, the pipeline breaks.
- **The Safe Expand/Contract Lifecycle:**
  1. **Phase 1 (Expand):** Add `new_name` as a nullable column.
  2. **Phase 2 (Migrate):** Update applications to dual-write or read from `new_name` with fallback to `old_name`. Backfill historical rows.
  3. **Phase 3 (Contract):** Drop `old_name` on the source.
  4. **Warehouse Persistence:** Debezium's JDBC Sink connector (`schema.evolution: basic`) does **not** issue `ALTER TABLE DROP COLUMN` on the warehouse. This protects analytical data integrity by retaining historical values in `old_name` while writing current data into `new_name`.

---

### Scenario 3: Widen Type (`integer` to `bigint`)
- **Root Cause of Sink Failure:**
  When a source column is changed from `int4` (`integer`) to `int8` (`bigint`), Debezium's Postgres connector inspects the new catalog metadata and publishes Kafka Connect events where the field schema is `Type.INT64`.
  However, the JDBC Sink Connector's basic schema evolution only executes `ALTER TABLE ADD COLUMN` for *missing* columns; it **never modifies existing column definitions**.
  When a value $> 2^{31}-1$ (e.g. `5,000,000,000`) arrives:
  ```text
  org.postgresql.util.PSQLException: ERROR: value "5000000000" is out of range for type integer
  ```
  The sink task throws an uncaught exception and halts in `FAILED` state.
- **Standard Operating Procedure:**
  In distributed CDC architectures, **type widening migrations must always be applied in reverse (downstream first)**:
  1. Execute `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;` on all warehouse/sink targets.
  2. Verify that Kafka Connect and warehouse are running healthy.
  3. Execute `ALTER TABLE ledger ALTER COLUMN <col> TYPE bigint;` on the source database.

---

### Scenario 4: Add Column with `DEFAULT`
- **Performance Characteristics:**
  Starting in PostgreSQL 11, adding a column with a constant default (`ALTER TABLE ... ADD COLUMN ... DEFAULT <val>`) updates table metadata instantaneously without rewriting the table or acquiring long-held exclusive locks.
- **Debezium Behavior:**
  Debezium reads the column's default value from the PostgreSQL system catalog (`pg_attrdef`) and populates the Kafka Connect `SchemaBuilder.defaultValue(...)` property. The JDBC sink connector creates the column in the destination warehouse with compatible types.

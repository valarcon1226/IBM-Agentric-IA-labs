CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS tasks (
    task_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    schedule VARCHAR(100),
    max_retries INT DEFAULT 3,
    retry_backoff INT DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    consecutive_failures INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL,
    stdout TEXT,
    stderr TEXT,
    exit_code INT,
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    duration_ms INT
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
    depends_on_task_id UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on_task_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_active ON tasks(is_active);
CREATE INDEX IF NOT EXISTS idx_tasks_polling ON tasks(is_active, last_run_at);
CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id);

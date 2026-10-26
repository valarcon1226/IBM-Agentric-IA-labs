"""Migration tests for LiteLLM schema upgrade from N-1 (v1.58.0) to N (v1.59.8).

Verifies:
1. REQ-LLM-011: Data integrity across version upgrade.
   - Pinned images:
     * N-1: ghcr.io/berriai/litellm:main-v1.58.0
       (digest: sha256:f949aa73fb4880ad197669e15e6736e170127a6187d4836ee6abeff303b712ee)
     * N: ghcr.io/berriai/litellm:main-v1.59.8
       (digest: sha256:36ebd57542257f81efc32181aa6a76aa7b229001767a114ecc440ef077969d88)
   - Procedure:
     1. Stand up N-1 against clean isolated database 'litellm_migration' on port 4005.
     2. Populate N-1 with virtual keys, budgets (max_budget), and spend records.
     3. Snapshot complete state via API (/key/list, /key/info) and direct SQL.
     4. Switch container to N, letting N run its startup database migrations.
     5. Record migration wall-clock duration in seconds.
     6. Verify 0 differences in keys, budgets, and spend records.
     7. Assert migration_upgrade_differences == 0 against targets.toml.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from qa_common.metrics import MetricsRecorder
from qa_common.targets import assert_target

from tests.conftest import wait_until
from tests.fake_upstream import FakeUpstreamServer

N_MINUS_1_IMAGE = "ghcr.io/berriai/litellm:main-v1.58.0"
N_IMAGE = "ghcr.io/berriai/litellm:main-v1.59.8"
MIGRATION_PORT = 4005
MIGRATION_DB = "litellm_migration"
MIGRATION_MASTER_KEY = "sk-upgrade-test-master-key-1234"
CONTAINER_NAME = "llm-litellm-migration-test"


def docker_cmd(args: List[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute docker command using list arguments to avoid shell quoting pitfalls."""
    docker_exe = shutil.which("docker") or "docker"
    res = subprocess.run([docker_exe, *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        err_msg = (
            f"Docker command failed: {' '.join(args)}\n"
            f"Stderr: {res.stderr}\nStdout: {res.stdout}"
        )
        raise RuntimeError(err_msg)
    return res


def psql_cmd(query: str, db: str = "postgres") -> str:
    """Run SQL query in postgres container via docker exec."""
    args = [
        "exec", "llm-postgres",
        "psql", "-U", "postgres", "-d", db,
        "-t", "-A", "-c", query,
    ]
    res = docker_cmd(args)
    return res.stdout.strip()


def run_litellm_container(image: str, config_path: str) -> None:
    """Launch a LiteLLM container on port 4005 pointing to the migration database."""
    # Ensure any previous instance is removed
    docker_cmd(["rm", "-f", CONTAINER_NAME], check=False)

    db_url = f"postgresql://postgres:postgrespassword@127.0.0.1:5432/{MIGRATION_DB}"
    args = [
        "run", "-d",
        "--name", CONTAINER_NAME,
        "--network", "host",
        "-m", "1536m",
        "-e", f"DATABASE_URL={db_url}",
        "-e", f"LITELLM_MASTER_KEY={MIGRATION_MASTER_KEY}",
        "-v", f"{config_path}:/app/config.yaml:ro",
        image,
        "--config", "/app/config.yaml",
        "--port", str(MIGRATION_PORT),
        "--host", "127.0.0.1",
    ]
    docker_cmd(args)


@pytest.mark.migration
def test_litellm_upgrade_n_minus_1_to_n(
    fake_upstream_server: FakeUpstreamServer,
) -> None:
    """Verify clean upgrade from N-1 (v1.58.0) to N (v1.59.8) with 0 data differences."""
    # Check docker available
    if not shutil.which("docker"):
        pytest.skip("Docker is not available in test runner environment")

    base_url = f"http://127.0.0.1:{MIGRATION_PORT}"
    headers = {"Authorization": f"Bearer {MIGRATION_MASTER_KEY}"}

    # Resolve config path
    config_file = Path(__file__).resolve().parent.parent.parent / "litellm" / "config.yaml"
    assert config_file.exists(), f"Config file not found at {config_file}"
    config_path_str = str(config_file)

    # 1. Setup clean test database
    psql_cmd(f"DROP DATABASE IF EXISTS {MIGRATION_DB};")
    psql_cmd(f"CREATE DATABASE {MIGRATION_DB};")

    try:
        # 2. Launch N-1 (v1.58.0)
        run_litellm_container(N_MINUS_1_IMAGE, config_path_str)

        # Wait for N-1 liveliness
        def _check_n1_healthy() -> bool:
            try:
                r = httpx.get(f"{base_url}/health/liveliness", timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False

        wait_until(_check_n1_healthy, description="LiteLLM N-1 startup", timeout=30.0, interval=1.0)

        # 3. Populate N-1 with keys, budgets, and spend records
        created_keys_info: Dict[str, Dict[str, Any]] = {}
        with httpx.Client(base_url=base_url, timeout=15.0) as client:
            # Create 6 keys with various budgets
            key_specs = [
                {"alias": "test-upg-key-01", "budget": 10.0, "models": ["fake-cost"]},
                {
                    "alias": "test-upg-key-02",
                    "budget": 25.0,
                    "models": ["fake-cost", "fake-primary"],
                },
                {"alias": "test-upg-key-03", "budget": 0.05, "models": ["fake-cost"]},
                {"alias": "test-upg-key-04", "budget": 50.0, "models": ["fake-primary"]},
                {"alias": "test-upg-key-05", "budget": 100.0, "models": ["fake-primary"]},
                {"alias": "test-upg-key-06", "budget": 200.0, "models": ["fake-cost"]},
            ]
            for spec in key_specs:
                payload = {
                    "key_alias": spec["alias"],
                    "max_budget": spec["budget"],
                    "models": spec["models"],
                    "user_id": "migration-eval-user",
                }
                res = client.post("/key/generate", headers=headers, json=payload)
                assert res.status_code == 200, f"Failed generating key {spec['alias']}: {res.text}"
                k_data = res.json()
                created_keys_info[k_data["key"]] = spec

            # Send 5 requests using key 01 to generate spend records and token logs
            key_01 = next(
                k for k, v in created_keys_info.items() if v["alias"] == "test-upg-key-01"
            )
            for i in range(5):
                resp = client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key_01}"},
                    json={
                        "model": "fake-cost",
                        "messages": [{"role": "user", "content": f"msg {i}"}],
                    },
                )
                assert resp.status_code == 200

            # Wait 7s for LiteLLM spend batcher to flush spend to DB
            time.sleep(7.0)

            # 4. Snapshot state from N-1
            # A. API Snapshot
            api_snapshot: Dict[str, Any] = {}
            list_res = client.get("/key/list?size=100", headers=headers)
            assert list_res.status_code == 200
            for token_hash in list_res.json().get("keys", []):
                info_res = client.get(f"/key/info?key={token_hash}", headers=headers)
                assert info_res.status_code == 200
                info_data = info_res.json().get("info", {})
                alias = info_data.get("key_alias")
                if alias and str(alias).startswith("test-upg-key"):
                    api_snapshot[alias] = {
                        "spend": info_data.get("spend", 0.0),
                        "max_budget": info_data.get("max_budget"),
                        "models": sorted(info_data.get("models", [])),
                        "user_id": info_data.get("user_id"),
                    }

        # B. Direct SQL Snapshot
        sql_query = (
            'SELECT json_agg(t) FROM (SELECT key_alias, spend, max_budget, user_id '
            'FROM "LiteLLM_VerificationToken" '
            'WHERE key_alias LIKE \'test-upg-key%\' '
            'ORDER BY key_alias) t;'
        )
        sql_raw = psql_cmd(sql_query, db=MIGRATION_DB)
        sql_snapshot = json.loads(sql_raw) if sql_raw else []

        assert len(api_snapshot) == len(key_specs), "All generated keys must appear in N-1 snapshot"
        assert len(sql_snapshot) == len(key_specs), "All generated keys must appear in SQL snapshot"

        # 5. Execute upgrade from N-1 to N
        # Stop N-1 container, switch image to N, measure wall-clock migration time
        t_start = time.monotonic()
        docker_cmd(["stop", CONTAINER_NAME])
        docker_cmd(["rm", "-f", CONTAINER_NAME])

        # Start N (v1.59.8) - runs database migrations on startup
        run_litellm_container(N_IMAGE, config_path_str)

        # Wait until N is healthy
        def _check_n_healthy() -> bool:
            try:
                r = httpx.get(f"{base_url}/health/liveliness", timeout=2.0)
                return r.status_code == 200
            except Exception:
                return False

        wait_until(
            _check_n_healthy,
            description="LiteLLM N startup and migration",
            timeout=45.0,
            interval=1.0,
        )
        t_end = time.monotonic()
        migration_duration_s = t_end - t_start

        # 6. Verify everything in N
        differences = 0
        diff_details: List[str] = []

        with httpx.Client(base_url=base_url, timeout=15.0) as client:
            list_res = client.get("/key/list?size=100", headers=headers)
            assert list_res.status_code == 200

            n_api_snapshot: Dict[str, Any] = {}
            for token_hash in list_res.json().get("keys", []):
                info_res = client.get(f"/key/info?key={token_hash}", headers=headers)
                assert info_res.status_code == 200
                info_data = info_res.json().get("info", {})
                alias = info_data.get("key_alias")
                if alias and str(alias).startswith("test-upg-key"):
                    n_api_snapshot[alias] = {
                        "spend": info_data.get("spend", 0.0),
                        "max_budget": info_data.get("max_budget"),
                        "models": sorted(info_data.get("models", [])),
                        "user_id": info_data.get("user_id"),
                    }

        # Compare API state
        for alias, expected in api_snapshot.items():
            actual = n_api_snapshot.get(alias)
            if actual is None:
                differences += 1
                diff_details.append(f"Missing key in N: {alias}")
                continue
            for field in ["spend", "max_budget", "models", "user_id"]:
                exp_val = expected[field]
                act_val = actual[field]
                if exp_val != act_val:
                    differences += 1
                    diff_details.append(
                        f"Key {alias} field {field} mismatch: expected {exp_val}, got {act_val}"
                    )

        # Compare SQL state
        sql_n_raw = psql_cmd(sql_query, db=MIGRATION_DB)
        sql_n_snapshot = json.loads(sql_n_raw) if sql_n_raw else []
        if sql_n_snapshot != sql_snapshot:
            differences += 1
            diff_details.append(f"SQL row mismatch:\nN-1: {sql_snapshot}\nN: {sql_n_snapshot}")

        # 7. Record metrics
        results_path = Path(__file__).resolve().parent.parent.parent / "results" / "metrics.json"
        recorder = MetricsRecorder()
        recorder.record("migration_upgrade_differences", float(differences))
        recorder.record("migration_wall_clock_s", migration_duration_s)
        recorder.save(results_path)

        # 8. Assertions
        assert differences == 0, (
            f"Found {differences} upgrade differences:\n" + "\n".join(diff_details)
        )
        assert_target("migration_upgrade_differences", differences)

    finally:
        # 9. Clean up container and test database
        docker_cmd(["rm", "-f", CONTAINER_NAME], check=False)
        psql_cmd(f"DROP DATABASE IF EXISTS {MIGRATION_DB};")

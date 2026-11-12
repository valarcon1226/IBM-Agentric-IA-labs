"""Static checks on every ``workflows/*.json`` file (DECISIONES-14 A6): valid JSON, no secrets
embedded, and every credential referenced only by stable ``id``/``name`` (never by value).

Pure unit test — no Docker required.
"""

import json
import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"

# Patterns that would indicate a real secret leaked into a workflow file instead of a
# `${VAR}` placeholder or an `={{ expression }}` reference by id/name.
SECRET_LIKE_PATTERNS = [
    re.compile(r"://[^/\s\"']+:[^/\s\"'@]+@"),  # scheme://user:pass@ connection strings
    re.compile(r"sk-[A-Za-z0-9]{10,}"),  # common API-key-looking tokens
]

KNOWN_CREDENTIAL_TYPES = {"postgres", "smtp", "httpHeaderAuth", "crypto"}


def _workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS_DIR.glob("*.json"))
    assert files, f"No workflow files found in {WORKFLOWS_DIR}"
    return files


def test_every_workflow_file_is_valid_json() -> None:
    for path in _workflow_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name}: expected a single workflow object"
        assert "nodes" in data and "connections" in data, f"{path.name}: missing nodes/connections"


def test_no_secret_like_values_in_workflow_files() -> None:
    for path in _workflow_files():
        raw = path.read_text(encoding="utf-8")
        for pattern in SECRET_LIKE_PATTERNS:
            assert not pattern.search(raw), (
                f"{path.name}: matched secret-like pattern {pattern.pattern}"
            )


def test_credentials_are_referenced_only_by_id_and_name() -> None:
    for path in _workflow_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            credentials = node.get("credentials", {})
            for cred_type, ref in credentials.items():
                assert cred_type in KNOWN_CREDENTIAL_TYPES, (
                    f"{path.name}: unexpected credential type {cred_type!r} on node "
                    f"{node.get('name')!r}"
                )
                assert set(ref.keys()) <= {"id", "name"}, (
                    f"{path.name}: credential reference on node {node.get('name')!r} has "
                    f"unexpected keys {sorted(ref.keys())} (must be id/name only, never a value)"
                )
                assert isinstance(ref.get("id"), str) and ref["id"], (
                    f"{path.name}: credential reference on node {node.get('name')!r} is missing a "
                    "stable id"
                )


def test_every_flow_has_an_error_workflow_configured() -> None:
    # A5: every flow (F1-F4) must route failures to the shared error handler instead of failing
    # silently.
    flow_files = [p for p in _workflow_files() if p.name != "shared-error-handler.json"]
    assert len(flow_files) == 4, f"expected F1-F4, found {[p.name for p in flow_files]}"
    for path in flow_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("settings", {}).get("errorWorkflow") == "shared-error-handler", (
            f"{path.name}: missing settings.errorWorkflow pointing at shared-error-handler"
        )


def test_no_workflow_reads_env_vars() -> None:
    # Security follow-up (T-14-lote-b review): n8n's `N8N_BLOCK_ENV_ACCESS_IN_NODE` stays at its
    # secure default (true) because the n8n container's own environment also holds
    # N8N_ENCRYPTION_KEY and DB_POSTGRESDB_PASSWORD. F2/F3's LLM endpoint is substituted into the
    # workflow JSON by n8n-init at import time (render-workflows.mjs) instead, so no workflow may
    # reference `$env` at runtime.
    for path in _workflow_files():
        raw = path.read_text(encoding="utf-8")
        assert "$env" not in raw, (
            f"{path.name}: must not read $env (n8n-init substitutes at import time)"
        )


def test_every_inbound_webhook_is_protected() -> None:
    # A3: F1/F2 webhooks use Header Auth, F4's uses its own HMAC check (so it stays
    # "authentication": "none" at the node level, see f4-payment-to-order.json). F3's manual
    # demo webhook is also Header Auth.
    webhooks_requiring_header_auth = {
        ("f1-lead-to-crm.json", "Lead Form Webhook"),
        ("f2-invoice-to-data.json", "Invoice Webhook"),
        ("f3-daily-report.json", "Manual Report Webhook"),
    }
    for filename, node_name in webhooks_requiring_header_auth:
        data = json.loads((WORKFLOWS_DIR / filename).read_text(encoding="utf-8"))
        node = next(n for n in data["nodes"] if n["name"] == node_name)
        assert node["parameters"].get("authentication") == "headerAuth", (
            f"{filename}: {node_name} must use headerAuth"
        )
        assert node["credentials"]["httpHeaderAuth"]["id"] == "cred-webhook-api-key"

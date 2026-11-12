"""LiteLLM setup script.

Creates a standard key from the master key (read from environment variable LITELLM_MASTER_KEY)
and queries the proxy to print all models reachable through that key.
"""

from __future__ import annotations

import os
import sys

import httpx


def main() -> None:
    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if not master_key:
        print("ERROR: LITELLM_MASTER_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")

    print(f"Connecting to LiteLLM proxy at {base_url}...")
    headers = {
        "Authorization": f"Bearer {master_key}",
        "Content-Type": "application/json",
    }

    # 1. Generate a virtual API key
    payload = {
        "key_alias": "setup-verification-key",
        "duration": "30d",
        "models": ["primary-model", "fallback-model", "fake-primary", "fake-fallback"],
    }

    with httpx.Client(timeout=30.0) as client:
        # Check health first
        try:
            health = client.get(f"{base_url}/health/liveliness")
            health.raise_for_status()
            print("LiteLLM liveliness check: HEALTHY")
        except Exception as exc:
            print(f"ERROR connecting to LiteLLM health endpoint: {exc}", file=sys.stderr)
            sys.exit(1)

        resp = client.post(f"{base_url}/key/generate", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"ERROR generating key ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)

        key_data = resp.json()
        generated_key = key_data.get("key") or key_data.get("token")
        key_alias = key_data.get("key_alias", "setup-verification-key")
        print(f"Generated key alias: {key_alias}")
        print(f"Key preview: {generated_key[:8]}...{generated_key[-4:]}")

        # 2. Query models with the newly generated key
        key_headers = {"Authorization": f"Bearer {generated_key}"}
        models_resp = client.get(f"{base_url}/v1/models", headers=key_headers)
        if models_resp.status_code != 200:
            # Fallback to /models
            models_resp = client.get(f"{base_url}/models", headers=key_headers)

        if models_resp.status_code != 200:
            print(
                f"ERROR fetching models ({models_resp.status_code}): {models_resp.text}",
                file=sys.stderr,
            )
            sys.exit(1)

        models_data = models_resp.json()
        model_list = [m.get("id") for m in models_data.get("data", []) if isinstance(m, dict)]
        print(f"Reachable models ({len(model_list)}): {model_list}")


if __name__ == "__main__":
    main()

#!/bin/sh
# Runs once per `docker compose up`: renders credentials AND workflow templates from env vars
# (so F2/F3's LLM endpoint is baked into the imported workflow instead of n8n reading `$env` at
# runtime, which would need N8N_BLOCK_ENV_ACCESS_IN_NODE=false for every node in every workflow
# -- a security hole, since that same container also holds N8N_ENCRYPTION_KEY and
# DB_POSTGRESDB_PASSWORD), imports credentials and workflows via the n8n CLI, and activates every
# workflow marked "active" in its own JSON (DECISIONES-14 A2/A3). `n8n` (the long-running
# service) depends on this container finishing with exit code 0.
set -e

echo "[n8n-init] rendering credential templates..."
node /init/render-credentials.mjs /credentials /tmp/credentials.json

echo "[n8n-init] rendering workflow templates..."
node /init/render-workflows.mjs /workflows /tmp/workflows

echo "[n8n-init] importing credentials..."
n8n import:credentials --input=/tmp/credentials.json

echo "[n8n-init] importing workflows..."
n8n import:workflow --separate --input=/tmp/workflows

echo "[n8n-init] activating workflows marked active in their JSON..."
for id in $(node /init/list-active-workflow-ids.mjs /workflows); do
  echo "[n8n-init]   activating ${id}"
  n8n update:workflow --id="${id}" --active=true
done

echo "[n8n-init] done."

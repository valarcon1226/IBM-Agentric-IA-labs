#!/usr/bin/env bash
# Runs inside the CI emulator step: starts Appium, waits for it, runs the suite.
# One file because android-emulator-runner executes each script line in its own shell.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts results

appium --port 4723 --log artifacts/appium.log &
APPIUM_PID=$!
trap 'kill "$APPIUM_PID" 2>/dev/null || true' EXIT

ready=0
for _ in $(seq 1 30); do
  if curl -s http://127.0.0.1:4723/status | grep -q '"ready":true'; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "Appium server did not become ready; see artifacts/appium.log" >&2
  exit 1
fi

export APPIUM_SERVER_URL="http://127.0.0.1:4723"
export ANDROID_PLATFORM_VERSION="14"
export ANDROID_APP_PATH="$PWD/apps/mda-2.3.0-27.apk"

.venv/bin/python -m pytest tests/ -v --junitxml=results/junit.xml

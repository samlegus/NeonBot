#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing virtualenv interpreter: ${PYTHON_BIN}" >&2
  echo "Create it with: python3 -m venv .venv" >&2
  exit 1
fi

echo "[1/5] Checking required packages in .venv"
"${PYTHON_BIN}" -m pip show requests python-dotenv pillow >/dev/null

echo "[2/5] Checking nai_job help"
"${PYTHON_BIN}" "${ROOT_DIR}/src/nai_job.py" --help >/dev/null

echo "[3/5] Checking nai_cli help"
"${PYTHON_BIN}" "${ROOT_DIR}/src/nai_cli.py" --help >/dev/null

echo "[4/5] Checking JSON bridge dry-run"
"${PYTHON_BIN}" "${ROOT_DIR}/src/nai_job.py" \
  --json '{"prompt":"smoke test","mode":"text"}' \
  --dry-run >/dev/null

echo "[5/5] Checking payload preview mode"
"${PYTHON_BIN}" "${ROOT_DIR}/src/nai_cli.py" \
  --prompt "smoke test" \
  --debug-payload >/dev/null

echo "Smoke test passed."

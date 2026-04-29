#!/usr/bin/env bash
# Start DocPrinter with the project venv (not Docker). From repository root:
#   ./docker/run_local.sh [run args... e.g. --port 9001]
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
PY="${ROOT}/.venv/bin/python"
CFG="${CONFIG_PATH:-${ROOT}/config/docprinter.server.json}"
if [[ ! -x "${PY}" ]]; then
  echo "Missing venv interpreter: ${PY}" >&2
  exit 1
fi
exec "${PY}" -m docprinter run -c "${CFG}" "$@"

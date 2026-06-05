#!/bin/bash
# Stop and remove DocPrinter Docker container (used by systemd before/after service).
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

DEFAULT=/etc/default/docprinter
if [[ -f "$DEFAULT" ]]; then
  # shellcheck source=/dev/null
  . "$DEFAULT"
fi
: "${DOCPRINTER_NAME:=docprinter}"

if ! command -v docker >/dev/null 2>&1; then
  exit 0
fi

if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "${DOCPRINTER_NAME}"; then
  echo "docprinter: removing container ${DOCPRINTER_NAME} for recreate" >&2
  docker stop -t 30 "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true
  docker rm -f "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true
  sleep 1
fi

exit 0

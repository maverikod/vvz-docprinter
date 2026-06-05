#!/usr/bin/env bash
# Fresh-install smoke test for docprinter .deb (requires root).
# 1. Remove local Docker images for vasilyvz/docprinter
# 2. Purge existing docprinter package if installed
# 3. Install .deb from parent directory
# 4. Verify docker pull, service, and /health
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(sed -n '1s/docprinter (\([^)]*\)).*/\1/p' "${ROOT}/debian/changelog")"
deb="${ROOT}/../docprinter_${version}_all.deb"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ${ROOT}/scripts/test-fresh-install.sh" >&2
  exit 1
fi

if [[ ! -f "${deb}" ]]; then
  echo "Missing ${deb}; run ./scripts/assemble-deb.sh first" >&2
  exit 1
fi

echo "=== Removing local DocPrinter images ==="
docker rmi -f vasilyvz/docprinter:latest vasilyvz/docprinter:"${version}" 2>/dev/null || true

if dpkg-query -W -f='${Status}' docprinter 2>/dev/null | grep -q "install ok installed"; then
  echo "=== Purging existing docprinter package ==="
  systemctl stop docprinter 2>/dev/null || true
  dpkg --purge docprinter || true
fi

echo "=== Installing ${deb} ==="
dpkg -i "${deb}" || apt-get install -f -y
dpkg -i "${deb}"

echo "=== Post-install checks ==="
id docprinter
groups docprinter
test -f /etc/docprinter/conf.json
test -d /var/docprinter/output
docker images vasilyvz/docprinter --format '{{.Repository}}:{{.Tag}}'

echo "=== Service status ==="
systemctl is-active docprinter
sleep 3
systemctl status docprinter --no-pager || true

echo "=== HTTP health ==="
curl -sf "http://127.0.0.1:9001/health" && echo

echo "Fresh install test OK."

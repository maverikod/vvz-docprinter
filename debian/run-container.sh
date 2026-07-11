#!/bin/bash
# Start DocPrinter in Docker (Debian package): detached container, docker wait,
# systemd STATUS from container state, logs streamed to /var/log/docprinter/docprinter.log.
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

DEFAULT=/etc/default/docprinter
if [[ -f "$DEFAULT" ]]; then
  # shellcheck source=/dev/null
  . "$DEFAULT"
fi
: "${DOCPRINTER_IMAGE:=docprinter:latest}"
: "${DOCPRINTER_NAME:=docprinter}"
: "${DOCPRINTER_PORT:=9001}"

LOG_FILE=/var/log/docprinter/docprinter.log

if ! command -v docker >/dev/null 2>&1; then
  echo "docprinter: docker not found in PATH" >&2
  exit 1
fi

if ! getent passwd docprinter >/dev/null 2>&1; then
  echo "docprinter: system user docprinter is missing" >&2
  exit 1
fi

uid="$(id -u docprinter)"
gid="$(id -g docprinter)"
RUNTIME_BASE=/var/lib/docprinter/runtime

if [[ ! -f /etc/docprinter/conf.json ]]; then
  echo "docprinter: missing /etc/docprinter/conf.json" >&2
  exit 1
fi

extra_args=()
if docker run --help 2>&1 | grep -q 'host-gateway'; then
  extra_args+=(--add-host=host.docker.internal:host-gateway)
fi

notifier_pid=""
logfollow_pid=""

stop_sidecars() {
  if [[ -n "${logfollow_pid:-}" ]] && kill -0 "${logfollow_pid}" 2>/dev/null; then
    kill "${logfollow_pid}" 2>/dev/null || true
    wait "${logfollow_pid}" 2>/dev/null || true
  fi
  if [[ -n "${notifier_pid:-}" ]] && kill -0 "${notifier_pid}" 2>/dev/null; then
    kill "${notifier_pid}" 2>/dev/null || true
    wait "${notifier_pid}" 2>/dev/null || true
  fi
}

on_term() {
  stop_sidecars
  docker stop -t 30 "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true
  exit 0
}

trap on_term INT TERM

docker rm -f "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true

docker run -d --name "${DOCPRINTER_NAME}" \
  --user "${uid}:${gid}" \
  -e HOME=/tmp \
  -p "${DOCPRINTER_PORT}:${DOCPRINTER_PORT}" \
  -v /etc/docprinter:/app/config:ro \
  -v /var/log/docprinter:/app/logs:rw \
  -v "${RUNTIME_BASE}/output:/app/runtime/output:rw" \
  -v "${RUNTIME_BASE}/work:/app/runtime/work:rw" \
  -v "${RUNTIME_BASE}/uploads:/app/runtime/uploads:rw" \
  "${extra_args[@]}" \
  -w /app \
  "${DOCPRINTER_IMAGE}" \
  python -m docprinter run -c config/conf.json --host 0.0.0.0 --port "${DOCPRINTER_PORT}"

touch "${LOG_FILE}"

# Stream container stdout/stderr into the host log file (same role as unit append before).
docker logs -f --tail 0 "${DOCPRINTER_NAME}" >>"${LOG_FILE}" 2>&1 &
logfollow_pid=$!

if [[ -n "${NOTIFY_SOCKET:-}" ]]; then
  (
    while docker inspect "${DOCPRINTER_NAME}" >/dev/null 2>&1; do
      st=$(docker inspect -f '{{.State.Status}}' "${DOCPRINTER_NAME}" 2>/dev/null || echo "?")
      line="DocPrinter (${DOCPRINTER_NAME}): ${st}"
      if docker inspect -f '{{if .State.Health}}1{{end}}' "${DOCPRINTER_NAME}" 2>/dev/null | grep -q 1; then
        hs=$(docker inspect -f '{{.State.Health.Status}}' "${DOCPRINTER_NAME}" 2>/dev/null || echo "?")
        line="${line}; health=${hs}"
      fi
      systemd-notify --status="${line}" 2>/dev/null || true
      case "${st}" in
        running | restarting | created | paused) sleep 4 ;;
        *) break ;;
      esac
    done
  ) &
  notifier_pid=$!
  systemd-notify --ready
fi

set +e
docker wait "${DOCPRINTER_NAME}"
rc=$?
set -e

stop_sidecars
exit "${rc}"

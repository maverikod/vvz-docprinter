#!/bin/bash
# Start DocPrinter in Docker (Debian package): detached container, docker wait,
# systemd STATUS from container state, logs streamed to /var/log/docprinter/docprinter.log.
#
# Host mounts:
#   /etc/docprinter  -> /app/config  (read-only)
#   /var/log/docprinter -> /app/logs
#   /var/docprinter  -> /app/runtime (output/work/uploads cache)
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

DEFAULT=/etc/default/docprinter
if [[ -f "$DEFAULT" ]]; then
  # shellcheck source=/dev/null
  . "$DEFAULT"
fi
: "${DOCPRINTER_IMAGE:?docprinter: set DOCPRINTER_IMAGE in /etc/default/docprinter}"
: "${DOCPRINTER_NAME:=docprinter}"
: "${DOCPRINTER_CONTAINER_PORT:=${DOCPRINTER_PORT:-9001}}"
: "${DOCPRINTER_HOST_PORT:=${DOCPRINTER_PORT:-${DOCPRINTER_CONTAINER_PORT}}}"
: "${DOCPRINTER_BIND:=127.0.0.1}"
: "${DOCPRINTER_NETWORK:=bridge}"

LOG_FILE=/var/log/docprinter/docprinter.log
CACHE_DIR=/var/docprinter
PUBLISH_SPEC="${DOCPRINTER_BIND}:${DOCPRINTER_HOST_PORT}:${DOCPRINTER_CONTAINER_PORT}"
ACTIVE_NETWORK="${DOCPRINTER_NETWORK}"

case "${DOCPRINTER_NETWORK}" in
  bridge | host) ;;
  *)
    echo "docprinter: DOCPRINTER_NETWORK must be bridge or host, got: ${DOCPRINTER_NETWORK}" >&2
    exit 1
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "docprinter: docker not found in PATH" >&2
  exit 1
fi

if ! getent passwd docprinter >/dev/null 2>&1; then
  echo "docprinter: system user docprinter is missing" >&2
  exit 1
fi

if ! getent group docker >/dev/null 2>&1; then
  echo "docprinter: docker group is missing (install docker.io or docker-ce)" >&2
  exit 1
fi

if ! id -nG docprinter | tr ' ' '\n' | grep -qx docker; then
  echo "docprinter: user docprinter is not in group docker" >&2
  exit 1
fi

uid="$(id -u docprinter)"
gid="$(id -g docprinter)"

if [[ ! -f /etc/docprinter/conf.json ]]; then
  echo "docprinter: missing /etc/docprinter/conf.json" >&2
  exit 1
fi

for subdir in output work uploads; do
  if [[ ! -d "${CACHE_DIR}/${subdir}" ]]; then
    echo "docprinter: missing cache directory ${CACHE_DIR}/${subdir}" >&2
    exit 1
  fi
done

extra_args=()
if docker run --help 2>&1 | grep -q 'host-gateway'; then
  extra_args+=(--add-host=host.docker.internal:host-gateway)
fi

notifier_pid=""
logfollow_pid=""

dump_container_logs() {
  echo "docprinter: last container logs:" >&2
  docker logs "${DOCPRINTER_NAME}" 2>&1 | tail -100 >&2 || true
}

wait_container_running() {
  local i st
  for i in $(seq 1 20); do
    st=$(docker inspect -f '{{.State.Status}}' "${DOCPRINTER_NAME}" 2>/dev/null || echo missing)
    case "${st}" in
      running) return 0 ;;
      exited | dead)
        dump_container_logs
        echo "docprinter: container exited during startup (status=${st})" >&2
        return 1
        ;;
    esac
    sleep 1
  done
  dump_container_logs
  echo "docprinter: container did not reach running state in time" >&2
  return 1
}

stop_sidecars() {
  if [[ -n "${logfollow_pid:-}" ]] && kill -0 "${logfollow_pid}" 2>/dev/null; then
    kill "${logfollow_pid}" 2>/dev/null || true
    wait "${logfollow_pid}" 2>/dev/null || true
  fi
}

on_term() {
  stop_sidecars
  docker stop -t 30 "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true
  exit 0
}

trap on_term INT TERM

REMOVE_SCRIPT=/usr/lib/docprinter/remove-container.sh

cleanup_container() {
  if [[ -x "${REMOVE_SCRIPT}" ]]; then
    "${REMOVE_SCRIPT}"
    return
  fi
  docker rm -f "${DOCPRINTER_NAME}" >/dev/null 2>&1 || true
  sleep 1
}

host_port_in_use() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "sport = :${port}" 2>/dev/null | grep -q .
    return $?
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | grep -q ":${port} "
    return $?
  fi
  return 1
}

show_port_listeners() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -E ":${port} |:${port}$" || true
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltnp 2>/dev/null | grep -E ":${port} |:${port}$" || true
  fi
  docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null \
    | grep -E ":${port}->|0\.0\.0\.0:${port}:|127\.0\.0\.1:${port}:" || true
}

publish_failed() {
  local err=$1
  grep -qiE 'external connectivity|address already in use|bind.*failed|iptables|nftables|DNAT' <<<"${err}"
}

persist_network_host() {
  if [[ ! -f "${DEFAULT}" ]]; then
    return
  fi
  if grep -q '^DOCPRINTER_NETWORK=' "${DEFAULT}" 2>/dev/null; then
    sed -i 's/^DOCPRINTER_NETWORK=.*/DOCPRINTER_NETWORK=host/' "${DEFAULT}"
  else
    echo 'DOCPRINTER_NETWORK=host' >>"${DEFAULT}"
  fi
  echo "docprinter: saved DOCPRINTER_NETWORK=host in ${DEFAULT}" >&2
}

docker_run() {
  local mode=$1
  local listen_port publish_args=() network_args=()

  if [[ "${mode}" == "host" ]]; then
    listen_port="${DOCPRINTER_CONTAINER_PORT}"
    network_args=(--network host)
    echo "docprinter: network=host, listening on ${DOCPRINTER_BIND}:${listen_port}" >&2
  else
    listen_port="${DOCPRINTER_HOST_PORT}"
    publish_args=(-p "${PUBLISH_SPEC}")
    echo "docprinter: publishing host ${DOCPRINTER_BIND}:${DOCPRINTER_HOST_PORT} -> container ${DOCPRINTER_CONTAINER_PORT}" >&2
  fi

  if host_port_in_use "${listen_port}"; then
    echo "docprinter: host port ${listen_port} is already in use" >&2
    show_port_listeners "${listen_port}" >&2
    RUN_LAST_ERR="port ${listen_port} in use"
    return 1
  fi

  set +e
  local app_host="0.0.0.0"
  if [[ "${mode}" == "host" ]]; then
    app_host="${DOCPRINTER_BIND}"
  fi
  RUN_LAST_ERR=$(
    docker run -d --name "${DOCPRINTER_NAME}" \
      --user "${uid}:${gid}" \
      -e HOME=/tmp \
      "${publish_args[@]}" \
      "${network_args[@]}" \
      -v /etc/docprinter:/app/config:ro \
      -v /var/log/docprinter:/app/logs:rw \
      -v "${CACHE_DIR}:/app/runtime:rw" \
      "${extra_args[@]}" \
      -w /app \
      "${DOCPRINTER_IMAGE}" \
      python -m docprinter run -c config/conf.json --host "${app_host}" --port "${DOCPRINTER_CONTAINER_PORT}" \
      2>&1
  )
  local rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]]; then
    echo "${RUN_LAST_ERR}" >&2
    return 1
  fi
  RUN_LAST_ERR=""
  return 0
}

RUN_LAST_ERR=""
cleanup_container

if [[ "${DOCPRINTER_NETWORK}" == "host" ]]; then
  ACTIVE_NETWORK=host
  docker_run host || exit 125
else
  ACTIVE_NETWORK=bridge
  if ! docker_run bridge; then
    if publish_failed "${RUN_LAST_ERR}"; then
      cleanup_container
      echo "docprinter: bridge port publish failed; retrying with network=host" >&2
      ACTIVE_NETWORK=host
      docker_run host || exit 125
      persist_network_host
    else
      cleanup_container
      exit 125
    fi
  fi
fi

wait_container_running || exit 125

touch "${LOG_FILE}"

docker logs -f --tail 0 "${DOCPRINTER_NAME}" >>"${LOG_FILE}" 2>&1 &
logfollow_pid=$!

set +e
docker wait "${DOCPRINTER_NAME}" >/dev/null
rc=$?
set -e

stop_sidecars
if [[ "${rc}" -ne 0 ]]; then
  dump_container_logs
  echo "docprinter: container stopped with exit code ${rc}" >&2
fi
exit "${rc}"

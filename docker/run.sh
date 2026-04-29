#!/usr/bin/env bash
# Run DocPrinter in Docker: remove existing container, bind uid/gid, publish TCP
# port (default 9001 on host and inside the container), mount config/logs/runtime,
# inject Docker-related lines from host /etc/hosts as --add-host.
#
# Does not build the image. From repository root, build then run:
#   ./docker/build.sh && ./docker/run.sh
#
# Optional: DOCPRINTER_IMAGE, DOCPRINTER_NAME, DOCPRINTER_PORT (host and container).
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export DOCPRINTER_IMAGE="${DOCPRINTER_IMAGE:-docprinter:latest}"
IMAGE="${DOCPRINTER_IMAGE}"
NAME="${DOCPRINTER_NAME:-docprinter}"
PORT="${DOCPRINTER_PORT:-9001}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found in PATH" >&2
  exit 1
fi

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "Docker image not found: ${IMAGE}" >&2
  echo "Build it first (does not run from this script): ./docker/build.sh" >&2
  exit 1
fi

mkdir -p \
  "${ROOT}/config" \
  "${ROOT}/logs" \
  "${ROOT}/runtime/output" \
  "${ROOT}/runtime/work" \
  "${ROOT}/runtime/uploads"

if [[ ! -f "${ROOT}/config/docker.json" ]]; then
  echo "Missing ${ROOT}/config/docker.json" >&2
  exit 1
fi

declare -A SEEN_HOST

while IFS= read -r line; do
  [[ -z "${line// }" ]] && continue
  read -r ip rest <<<"${line}" || true
  [[ -z "${ip:-}" ]] && continue
  [[ "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || continue
  [[ "${ip}" == 127.* ]] && continue
  for h in ${rest}; do
    [[ -z "${h}" ]] && continue
    [[ "${h}" == *"#"* ]] && break
    SEEN_HOST["${h}"]="${ip}"
  done
done < <(
  awk '
    /^[[:space:]]*#/ { next }
    NF < 2 { next }
    $1 ~ /^127\./ { next }
    $1 ~ /^172\.(1[6-9]|2[0-9]|3[0-1])\./ { print; next }
    $1 ~ /^192\.168\.65\./ { print; next }
    tolower($0) ~ /docker/ { print; next }
    $0 ~ /host\.docker\.internal/ { print; next }
  ' /etc/hosts 2>/dev/null || true
)

if docker run --rm --help 2>&1 | grep -q host-gateway; then
  SEEN_HOST["host.docker.internal"]="host-gateway"
fi

declare -a ADD_HOSTS=()
for h in "${!SEEN_HOST[@]}"; do
  ADD_HOSTS+=(--add-host="${h}:${SEEN_HOST[${h}]}")
done

if docker ps -a --format '{{.Names}}' | grep -qx "${NAME}"; then
  echo "Stopping and removing existing container: ${NAME}"
  docker rm -f "${NAME}" >/dev/null
fi

echo "Starting ${NAME} (image ${IMAGE}, port ${PORT} host and container) as $(id -un) ($(id -u):$(id -g))"

docker run -d \
  --name "${NAME}" \
  --restart unless-stopped \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -p "${PORT}:${PORT}" \
  -v "${ROOT}/config:/app/config:rw" \
  -v "${ROOT}/logs:/app/logs:rw" \
  -v "${ROOT}/runtime/output:/app/runtime/output:rw" \
  -v "${ROOT}/runtime/work:/app/runtime/work:rw" \
  -v "${ROOT}/runtime/uploads:/app/runtime/uploads:rw" \
  "${ADD_HOSTS[@]}" \
  -w /app \
  "${IMAGE}" \
  python -m docprinter run -c config/docker.json --host 0.0.0.0 --port "${PORT}"

echo "Container ${NAME} is up. HTTP: http://127.0.0.1:${PORT}/"
echo "Logs: docker logs -f ${NAME}"

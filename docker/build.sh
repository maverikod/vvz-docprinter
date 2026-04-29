#!/usr/bin/env bash
# Build DocPrinter Docker image for this service. Run from repository root:
#   ./docker/build.sh
#
# Optional: DOCPRINTER_IMAGE (default docprinter:latest), DOCKER_BUILD_FLAGS.
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${DOCPRINTER_IMAGE:-docprinter:latest}"
# shellcheck disable=SC2086
docker build ${DOCKER_BUILD_FLAGS:-} -f "${ROOT}/docker/Dockerfile" -t "${IMAGE}" "${ROOT}"
echo "Image ${IMAGE} OK. Start container: ./docker/run.sh"

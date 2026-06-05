#!/usr/bin/env bash
# Build DocPrinter image and push to Docker Hub. Run from repository root:
#   ./docker/push.sh
#
# Optional: DOCPRINTER_HUB_IMAGE (default vasilyvz/docprinter:latest),
#           DOCPRINTER_VERSION_TAG (default package version from debian/changelog).
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUB_IMAGE="${DOCPRINTER_HUB_IMAGE:-vasilyvz/docprinter:latest}"

version_tag=""
if [[ -f "${ROOT}/debian/changelog" ]]; then
  version_tag="$(sed -n '1s/docprinter (\([^)]*\)).*/\1/p' "${ROOT}/debian/changelog")"
fi
VERSION_TAG="${DOCPRINTER_VERSION_TAG:-${version_tag:-latest}}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found in PATH" >&2
  exit 1
fi

echo "Building ${HUB_IMAGE} ..."
DOCPRINTER_IMAGE="${HUB_IMAGE}" "${ROOT}/docker/build.sh"

if [[ "${VERSION_TAG}" != "latest" ]] && [[ "${HUB_IMAGE}" == *:latest ]]; then
  repo="${HUB_IMAGE%:latest}"
  version_image="${repo}:${VERSION_TAG}"
  echo "Tagging ${version_image} ..."
  docker tag "${HUB_IMAGE}" "${version_image}"
  echo "Pushing ${version_image} ..."
  docker push "${version_image}"
fi

echo "Pushing ${HUB_IMAGE} ..."
docker push "${HUB_IMAGE}"

echo "Published ${HUB_IMAGE} (version tag: ${VERSION_TAG})."

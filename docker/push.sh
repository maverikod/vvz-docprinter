#!/usr/bin/env bash
# Build DocPrinter image and push to Docker Hub.
# Primary tag always equals Debian package version from debian/changelog
# (e.g. package 0.2.0-12 -> vasilyvz/docprinter:0.2.0-12).
#
# Optional: DOCPRINTER_HUB_REPO (default vasilyvz/docprinter),
#           DOCPRINTER_VERSION_TAG (default: first line of debian/changelog).
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${DOCPRINTER_HUB_REPO:-vasilyvz/docprinter}"

version_tag=""
if [[ -f "${ROOT}/debian/changelog" ]]; then
  version_tag="$(sed -n '1s/docprinter (\([^)]*\)).*/\1/p' "${ROOT}/debian/changelog")"
fi
VERSION_TAG="${DOCPRINTER_VERSION_TAG:-${version_tag:-}}"
if [[ -z "${VERSION_TAG}" ]]; then
  echo "push.sh: cannot determine package version from debian/changelog" >&2
  exit 1
fi

PRIMARY_IMAGE="${REPO}:${VERSION_TAG}"

if ! command -v docker >/dev/null 2>&1; then
  echo "push.sh: docker not found in PATH" >&2
  exit 1
fi

echo "push.sh: building ${PRIMARY_IMAGE} (package version ${VERSION_TAG}) ..."
DOCPRINTER_IMAGE="${PRIMARY_IMAGE}" "${ROOT}/docker/build.sh"

echo "push.sh: pushing ${PRIMARY_IMAGE} ..."
docker push "${PRIMARY_IMAGE}"

echo "push.sh: updating ${REPO}:latest alias ..."
docker tag "${PRIMARY_IMAGE}" "${REPO}:latest"
docker push "${REPO}:latest"

echo "push.sh: published ${PRIMARY_IMAGE} (matches package docprinter ${VERSION_TAG})."

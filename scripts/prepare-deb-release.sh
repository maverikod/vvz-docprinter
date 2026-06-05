#!/usr/bin/env bash
# Sync Debian docker-image refs from debian/changelog and publish image to Docker Hub.
# Always runs before .deb assembly (build-deb.sh, assemble-deb.sh, debian/rules).
# Requires Docker CLI and Hub login (docker login).
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

version="$(sed -n '1s/docprinter (\([^)]*\)).*/\1/p' debian/changelog)"
if [[ -z "${version}" ]]; then
  echo "prepare-deb-release.sh: cannot read version from debian/changelog" >&2
  exit 1
fi

image="vasilyvz/docprinter:${version}"

cat > debian/docker-image.env <<EOF
# Image tag equals Debian package Version (debian/changelog). Do not edit by hand.
DOCPRINTER_IMAGE=${image}
EOF

if [[ -f debian/docprinter.default ]]; then
  sed -i "s|^DOCPRINTER_IMAGE=.*|DOCPRINTER_IMAGE=${image}|" debian/docprinter.default
fi

echo "prepare-deb-release.sh: DOCPRINTER_IMAGE=${image}"

if ! command -v docker >/dev/null 2>&1; then
  echo "prepare-deb-release.sh: docker not found; install Docker and run: docker login" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "prepare-deb-release.sh: Docker daemon is not running; start it: systemctl start docker" >&2
  exit 1
fi

echo "prepare-deb-release.sh: building and pushing ${image} (package ${version}) ..."
DOCPRINTER_VERSION_TAG="${version}" DOCPRINTER_HUB_REPO="vasilyvz/docprinter" "${ROOT}/docker/push.sh"

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  echo "prepare-deb-release.sh: ${image} missing locally after push" >&2
  exit 1
fi
echo "prepare-deb-release.sh: verified ${image} (tag matches package ${version})"

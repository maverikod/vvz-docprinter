#!/usr/bin/env bash
# Build the docprinter Debian binary package after checking build dependencies.
# Always runs scripts/prepare-deb-release.sh first (build + push to Docker Hub).
# Requires Docker CLI, running daemon, and docker login (vasilyvz/docprinter).
#
# As non-root: verifies tools and dpkg-checkbuilddeps; if something is missing,
# prints how to fix and exits 1 (re-run with root/sudo to auto-install).
# As root: installs required packages via apt-get, then runs dpkg-buildpackage.
#
# Optional: BUILD_DEB_APT_UPDATE=yes — run apt-get update before install.
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ ! -f debian/control ]] || [[ ! -x debian/rules ]]; then
  echo "build-deb.sh: нет debian/control или debian/rules не исполняемый; ожидается корень репозитория docprinter." >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "build-deb.sh: нужен apt-get (Debian/Ubuntu). Установите зависимости сборки вручную и выполните: dpkg-buildpackage -us -uc -b" >&2
  exit 1
fi

BINARIES_OK=true
for cmd in dpkg-buildpackage dpkg-checkbuilddeps fakeroot dh; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    BINARIES_OK=false
    break
  fi
done

dep_out=""
DEPS_OK=true
if [[ "${BINARIES_OK}" == true ]]; then
  if ! dep_out="$(dpkg-checkbuilddeps 2>&1)"; then
    DEPS_OK=false
  fi
else
  DEPS_OK=false
fi

if [[ "${BINARIES_OK}" == true ]] && [[ "${DEPS_OK}" == true ]]; then
  "${ROOT}/scripts/prepare-deb-release.sh"
  exec dpkg-buildpackage -us -uc -b
fi

if [[ "${BINARIES_OK}" != true ]] && command -v fakeroot >/dev/null 2>&1 && command -v dpkg-deb >/dev/null 2>&1; then
  echo "build-deb.sh: debhelper/dh not found; assembling .deb via scripts/assemble-deb.sh" >&2
  exec "${ROOT}/scripts/assemble-deb.sh"
fi

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Для сборки .deb не хватает пакетов или утилит." >&2
  echo >&2
  if [[ "${BINARIES_OK}" != true ]]; then
    echo "Не найдены в PATH: dpkg-buildpackage, dpkg-checkbuilddeps, fakeroot и/или dh (пакет debhelper)." >&2
  fi
  if [[ "${BINARIES_OK}" == true ]] && [[ "${DEPS_OK}" != true ]]; then
    echo "dpkg-checkbuilddeps:" >&2
    echo "${dep_out}" >&2
  fi
  echo >&2
  echo "Установите зависимости вручную или запустите этот же скрипт от root:" >&2
  echo "  sudo ${ROOT}/scripts/build-deb.sh" >&2
  exit 1
fi

# root: install build dependencies
if [[ "${BUILD_DEB_APT_UPDATE:-}" == "1" ]] || [[ "${BUILD_DEB_APT_UPDATE:-}" == "yes" ]]; then
  apt-get update
fi

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends \
  debhelper \
  dpkg-dev \
  fakeroot \
  build-essential

if ! dpkg-checkbuilddeps 2>&1; then
  echo "build-deb.sh: после apt-get install зависимости из debian/control всё ещё не выполнены (см. выше)." >&2
  exit 1
fi

"${ROOT}/scripts/prepare-deb-release.sh"
exec dpkg-buildpackage -us -uc -b

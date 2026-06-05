#!/usr/bin/env bash
# Assemble docprinter .deb without debhelper (when dh is unavailable).
# Output: ../docprinter_<version>_all.deb relative to repo root.
#
# By default runs scripts/prepare-deb-release.sh first (sync refs + mandatory docker push).
# Pass --deb-only only when prepare-deb-release.sh already ran in this build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

deb_only=false
if [[ "${1:-}" == "--deb-only" ]]; then
  deb_only=true
fi

if [[ "${deb_only}" != true ]]; then
  "${ROOT}/scripts/prepare-deb-release.sh"
fi

version="$(sed -n '1s/docprinter (\([^)]*\)).*/\1/p' debian/changelog)"
if [[ -z "${version}" ]]; then
  echo "assemble-deb.sh: cannot read version from debian/changelog" >&2
  exit 1
fi

build_dir="$(mktemp -d)"
trap 'rm -rf "${build_dir}"' EXIT

pkg="${build_dir}/docprinter"
mkdir -p "${pkg}/DEBIAN" \
  "${pkg}/usr/lib/docprinter" \
  "${pkg}/usr/lib/systemd/system" \
  "${pkg}/usr/share/docprinter" \
  "${pkg}/usr/share/doc/docprinter" \
  "${pkg}/etc/default"

install -m 0755 debian/run-container.sh "${pkg}/usr/lib/docprinter/run-container.sh"
install -m 0755 debian/remove-container.sh "${pkg}/usr/lib/docprinter/remove-container.sh"
install -m 0644 debian/docprinter.service "${pkg}/usr/lib/systemd/system/docprinter.service"
install -m 0644 debian/conf.json.example "${pkg}/usr/share/docprinter/conf.json.example"
install -m 0644 debian/docker-image.env "${pkg}/usr/share/docprinter/docker-image.env"
install -m 0644 debian/docprinter.default "${pkg}/etc/default/docprinter"
install -m 0644 debian/copyright "${pkg}/usr/share/doc/docprinter/copyright"
gzip -c debian/changelog > "${pkg}/usr/share/doc/docprinter/changelog.Debian.gz"

cat > "${pkg}/DEBIAN/control" <<EOF
Package: docprinter
Version: ${version}
Architecture: all
Maintainer: Vasiliy Zdanovskiy <vasilyvz@gmail.com>
Installed-Size: 32
Depends: adduser, systemd, docker.io | docker-ce
Section: net
Priority: optional
Description: DocPrinter HTTP service (Docker + systemd)
 Runs the DocPrinter container under systemd on Ubuntu 22.04 LTS and 26.04 LTS.
 On configure: verifies docker.io (or docker-ce), the docker group, host
 directories, and pulls the pinned image from Docker Hub on install/upgrade
 (see /usr/share/docprinter/docker-image.env; factory /etc/default sync).
 Host mounts: /etc/docprinter (config), /var/log/docprinter (logs),
 /var/docprinter (runtime cache: output, work, uploads). Service user docprinter
 must belong to group docker.
EOF

SYSTEMD_POSTINST=$'if [ "$1" = "configure" ] || [ "$1" = "abort-upgrade" ] || [ "$1" = "abort-deconfigure" ] || [ "$1" = "abort-remove" ] ; then\n\tdeb-systemd-helper unmask '"'"'docprinter.service'"'"' >/dev/null 2>&1 || true\n\tif deb-systemd-helper --quiet was-enabled '"'"'docprinter.service'"'"'; then\n\t\tdeb-systemd-helper enable '"'"'docprinter.service'"'"' >/dev/null 2>&1 || true\n\telse\n\t\tdeb-systemd-helper update-state '"'"'docprinter.service'"'"' >/dev/null 2>&1 || true\n\tfi\nfi\nif [ "$1" = "configure" ] || [ "$1" = "abort-upgrade" ] || [ "$1" = "abort-deconfigure" ] || [ "$1" = "abort-remove" ] ; then\n\tif [ -d /run/systemd/system ]; then\n\t\tsystemctl --system daemon-reload >/dev/null 2>&1 || true\n\tfi\nfi'

SYSTEMD_PRERM=$'if [ -z "${DPKG_ROOT:-}" ] && [ "$1" = remove ] && [ -d /run/systemd/system ] ; then\n\tdeb-systemd-invoke stop '"'"'docprinter.service'"'"' >/dev/null || true\nfi'

SYSTEMD_POSTRM=$'if [ "$1" = remove ] && [ -d /run/systemd/system ] ; then\n\tsystemctl --system daemon-reload >/dev/null || true\nfi\nif [ "$1" = "purge" ]; then\n\tif [ -x "/usr/bin/deb-systemd-helper" ]; then\n\t\tdeb-systemd-helper purge '"'"'docprinter.service'"'"' >/dev/null || true\n\tfi\nfi'

inject_hook() {
  local src=$1 dst=$2 inject=$3
  awk -v block="${inject}" '
    /#DEBHELPER#/ { print block; next }
    { print }
  ' "${src}" > "${dst}"
  chmod 0755 "${dst}"
}

inject_hook debian/postinst "${pkg}/DEBIAN/postinst" "${SYSTEMD_POSTINST}"
inject_hook debian/prerm "${pkg}/DEBIAN/prerm" "${SYSTEMD_PRERM}"
inject_hook debian/postrm "${pkg}/DEBIAN/postrm" "${SYSTEMD_POSTRM}"

echo "/etc/default/docprinter" > "${pkg}/DEBIAN/conffiles"

out="${ROOT}/../docprinter_${version}_all.deb"
fakeroot dpkg-deb --build "${pkg}" "${out}"
echo "Built ${out}"

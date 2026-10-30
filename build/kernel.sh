#!/usr/bin/env bash
# kernel.sh - fetch, verify and build the Grintion-OS Linux kernel
#
# Pinned source: Linux 6.12.114 (longterm)
# The SHA-256 in config/linux-6.12.114.tar.xz.sha256 was taken from the
# kernel.org signed sha256sums.asc list on 2026-10-30. The build is offline
# after the first successful fetch; delete build/cache to re-fetch.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Prefer the pinned build tools (notably bc) over the host PATH.
export PATH="$REPO_ROOT/tools/bin:$PATH"
CACHE="$REPO_ROOT/build/cache"
WORK="$REPO_ROOT/build/work"
SOURCE="$WORK/linux-6.12.114"
MODROOT="$WORK/kernel-modules"
OUTPUT="$REPO_ROOT/output"

KERNEL_VERSION="6.12.114"
KERNEL_LOCALVERSION="-grintion"
KERNEL_RELEASE="${KERNEL_VERSION}${KERNEL_LOCALVERSION}"
TARBALL="$CACHE/linux-${KERNEL_VERSION}.tar.xz"
CHECKSUM="$REPO_ROOT/config/linux-${KERNEL_VERSION}.tar.xz.sha256"
FRAGMENT="$REPO_ROOT/config/kernel-hardened.config"
SOURCE_URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-${KERNEL_VERSION}.tar.xz"

# Fixed timestamp for reproducible kernel metadata. Override only for a
# deliberate rebuild of a released artifact.
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1767225600}"
export SOURCE_DATE_EPOCH
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-grintion}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-build}"
export KBUILD_BUILD_VERSION="${KBUILD_BUILD_VERSION:-1}"
export KBUILD_BUILD_TIMESTAMP
KBUILD_BUILD_TIMESTAMP="$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%Y-%m-%d %H:%M:%S')"
export LC_ALL=C

log() { printf '[*] %s\n' "$*"; }
die() { printf '[-] %s\n' "$*" >&2; exit 1; }

mkdir -p "$CACHE" "$WORK" "$MODROOT" "$OUTPUT"

command -v make >/dev/null || die "make is required"
command -v gcc  >/dev/null || die "gcc is required"
command -v bc   >/dev/null || die "bc is required (tools/bin/bc is provided)"
command -v flex >/dev/null || die "flex is required"
command -v bison >/dev/null || die "bison is required"
command -v depmod >/dev/null || die "kmod/depmod is required"

if [ ! -f "$TARBALL" ]; then
    log "Downloading Linux ${KERNEL_VERSION} from kernel.org..."
    curl -fL --retry 5 --retry-delay 2 -o "$TARBALL.part" "$SOURCE_URL"
    mv "$TARBALL.part" "$TARBALL"
fi

log "Verifying the pinned kernel tarball checksum..."
(cd "$CACHE" && sha256sum -c "$CHECKSUM") || die "kernel tarball checksum mismatch"

if [ ! -f "$SOURCE/Makefile" ]; then
    log "Extracting Linux ${KERNEL_VERSION}..."
    rm -rf "$SOURCE"
    tar -C "$WORK" -xf "$TARBALL"
    [ -f "$SOURCE/Makefile" ] || die "kernel source extraction failed"
fi

cd "$SOURCE"

log "Generating x86_64 defconfig..."
make x86_64_defconfig

log "Merging the hardened configuration fragment..."
scripts/kconfig/merge_config.sh -m .config "$FRAGMENT"
make olddefconfig

log "Validating the kernel configuration contract..."
"$REPO_ROOT/build/check-kernel-config.sh" .config "$FRAGMENT"

CONFIG_HASH=$(sha256sum .config | cut -d' ' -f1)
log "Building bzImage and modules (config ${CONFIG_HASH:0:12})..."
make -j"$(nproc)" bzImage modules

log "Installing modules into the staging tree..."
rm -rf "$MODROOT/lib/modules/$KERNEL_RELEASE"
make INSTALL_MOD_PATH="$MODROOT" INSTALL_MOD_STRIP=1 modules_install

log "Generating module dependency metadata..."
depmod -b "$MODROOT" "$KERNEL_RELEASE"

install -D -m 0644 arch/x86/boot/bzImage "$OUTPUT/vmlinuz-grintion"
install -D -m 0644 System.map "$OUTPUT/System.map-grintion"
install -D -m 0644 .config "$OUTPUT/config-grintion"
install -D -m 0644 COPYING "$OUTPUT/licenses/linux/COPYING"

KERNEL_SHA=$(sha256sum "$OUTPUT/vmlinuz-grintion" | cut -d' ' -f1)
{
    printf 'name=linux\n'
    printf 'version=%s\n' "$KERNEL_VERSION"
    printf 'release=%s\n' "$KERNEL_RELEASE"
    printf 'source=%s\n' "$SOURCE_URL"
    printf 'source_sha256=%s\n' "$(cut -d' ' -f1 "$CHECKSUM")"
    printf 'config_sha256=%s\n' "$CONFIG_HASH"
    printf 'bzimage_sha256=%s\n' "$KERNEL_SHA"
    printf 'compiler=%s\n' "$(gcc --version | head -n 1)"
    printf 'source_date_epoch=%s\n' "$SOURCE_DATE_EPOCH"
    printf 'build_timestamp=%s\n' "$KBUILD_BUILD_TIMESTAMP"
} > "$OUTPUT/kernel-BUILD-INFO"

log "Kernel built: $OUTPUT/vmlinuz-grintion"
log "Release:      $KERNEL_RELEASE"
log "SHA-256:      $KERNEL_SHA"
log "Modules:      $MODROOT/lib/modules/$KERNEL_RELEASE"

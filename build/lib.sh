#!/usr/bin/env bash
# build/lib.sh - shared helpers for the Grintion-OS build system.
#
# Every build script sources this file. It enables strict mode, pins the
# environment used for reproducible metadata, and provides logging helpers.

set -Eeuo pipefail

GRINTION_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRINTION_REPO_ROOT="$(cd "$GRINTION_LIB_DIR/.." && pwd)"
export GRINTION_REPO_ROOT

# Fixed epoch used by every artifact that embeds a timestamp. Bump only for a
# deliberate release rebuild.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1767225600}"
export LC_ALL=C
export TZ=UTC
umask 022

# Prefer the pinned tools built by `make tools` over host versions. This also
# makes kernel.sh find tools/bin/bc on a host without GNU bc installed.
export PATH="$GRINTION_REPO_ROOT/tools/bin:$PATH"

GRINTION_VERSION="$(cat "$GRINTION_REPO_ROOT/VERSION")"
export GRINTION_VERSION
GRINTION_ARCH="${GRINTION_ARCH:-x86_64}"
export GRINTION_ARCH

log()  { printf '\033[1;32m[*]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[-]\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required host command not found: $1"
}

epoch_date() {
    date -u -d "@${SOURCE_DATE_EPOCH}" '+%Y-%m-%dT%H:%M:%SZ'
}

build_info() {
    local out="$1"
    {
        printf 'name=Grintion-OS\n'
        printf 'version=%s\n' "$GRINTION_VERSION"
        printf 'arch=%s\n' "$GRINTION_ARCH"
        printf 'source_date_epoch=%s\n' "$SOURCE_DATE_EPOCH"
        printf 'build_date=%s\n' "$(epoch_date)"
        printf 'builder=%s\n' "${USER:-unknown}"
        printf 'host=%s\n' "$(uname -srm)"
        printf 'host_distro=%s\n' "$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release 2>/dev/null | tr -d '"')"
        printf 'gcc=%s\n' "$(gcc --version 2>/dev/null | head -n 1)"
        printf 'python=%s\n' "$(python3 --version 2>/dev/null)"
    } > "$out"
}

# The kernel release that build/kernel.sh installs. Kept in one place so the
# rootfs, installer and tests cannot disagree.
kernel_release() {
    local info="$GRINTION_REPO_ROOT/build/work/kernel-release"
    if [ -f "$info" ]; then
        cat "$info"
    else
        printf '6.12.114-grintion\n'
    fi
}

# Copy a host file into the staging rootfs, preserving the destination path
# relative to /. Used for configuration trees and data files.
install_into_root() {
    local root="$1" src="$2"
    local rel="${src#/}"
    install -D -m 0644 "$src" "$root/$rel"
}

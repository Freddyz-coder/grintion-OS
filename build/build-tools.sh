#!/usr/bin/env bash
# build-tools.sh - fetch, verify and build the pinned tools Grintion-OS needs.
#
# The live image must not depend on whatever versions happen to be installed on
# the build host for its init, device manager or applets. These four projects
# are downloaded from their upstream release URLs, checked against
# config/tools.sha256 and built locally.
#
# Outputs:
#   tools/bin/busybox
#   tools/bin/{runit,runsv,runsvdir,sv,chpst}
#   tools/bin/bc
#   tools/src/dhcpcd-10.5.2/   (compiled by make-rootfs)

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SRC="$GRINTION_REPO_ROOT/tools/src"
BIN="$GRINTION_REPO_ROOT/tools/bin"
CACHE="$GRINTION_REPO_ROOT/build/cache/tools"
CHECKSUMS="$GRINTION_REPO_ROOT/config/tools.sha256"

mkdir -p "$SRC" "$BIN" "$CACHE"

need_cmd make
need_cmd gcc
need_cmd curl
need_cmd sha256sum
need_cmd tar

# fetch <filename> <url>
fetch() {
    local name="$1" url="$2"
    if [ ! -f "$CACHE/$name" ]; then
        log "downloading $name"
        curl -fL --retry 5 --retry-delay 2 -o "$CACHE/$name.part" "$url"
        mv "$CACHE/$name.part" "$CACHE/$name"
    fi
    ( cd "$CACHE" && grep "  $name\$" "$CHECKSUMS" | sha256sum -c - ) \
        || die "checksum mismatch for $name"
}

# extract <filename> <directory-name>
extract() {
    local archive="$CACHE/$1" dir="$2"
    if [ -d "$SRC/$dir" ]; then
        return
    fi
    log "extracting $dir"
    tar -C "$SRC" -xf "$archive"
    if [ ! -d "$SRC/$dir" ]; then
        # Some upstream archives wrap the tree in an extra directory
        # (runit ships as admin/runit-2.1.2/). Normalise the location.
        found="$(find "$SRC" -maxdepth 3 -type d -name "$dir" | head -n 1)"
        [ -n "$found" ] || die "archive $1 did not contain $dir"
        mv "$found" "$SRC/$dir"
        rmdir "$SRC/admin" 2>/dev/null || true
    fi
}

fetch busybox-1.37.0.tar.bz2 https://busybox.net/downloads/busybox-1.37.0.tar.bz2
fetch runit-2.1.2.tar.gz http://smarden.org/runit/runit-2.1.2.tar.gz
fetch bc-1.07.1.tar.gz https://ftp.gnu.org/gnu/bc/bc-1.07.1.tar.gz
fetch dhcpcd-10.5.2.tar.xz https://github.com/NetworkConfiguration/dhcpcd/releases/download/v10.5.2/dhcpcd-10.5.2.tar.xz

extract busybox-1.37.0.tar.bz2 busybox-1.37.0
extract runit-2.1.2.tar.gz runit-2.1.2
extract bc-1.07.1.tar.gz bc-1.07.1
extract dhcpcd-10.5.2.tar.xz dhcpcd-10.5.2

# ---------------------------------------------------------------- busybox
# A static busybox is both the installed-system initramfs and the source of
# syslogd, mdev, hostname and the rescue shell applets.
if [ ! -x "$BIN/busybox" ]; then
    log "building busybox 1.37.0 (static)"
    make -C "$SRC/busybox-1.37.0" defconfig >/dev/null
    sed -i 's/^# CONFIG_STATIC is not set$/CONFIG_STATIC=y/' "$SRC/busybox-1.37.0/.config"
    make -C "$SRC/busybox-1.37.0" -j"$(nproc)" >/dev/null
    install -D -m 0755 "$SRC/busybox-1.37.0/busybox" "$BIN/busybox"
fi

# ---------------------------------------------------------------- runit
if [ ! -x "$BIN/runsvdir" ]; then
    log "building runit 2.1.2"
    make -C "$SRC/runit-2.1.2" >/dev/null
    for tool in runit runsv runsvdir sv chpst; do
        install -D -m 0755 "$SRC/runit-2.1.2/$tool" "$BIN/$tool"
    done
fi

# ---------------------------------------------------------------- bc
if [ ! -x "$BIN/bc" ]; then
    log "building bc 1.07.1"
    ( cd "$SRC/bc-1.07.1" && ./configure --prefix=/usr >/dev/null && make -j"$(nproc)" >/dev/null )
    install -D -m 0755 "$SRC/bc-1.07.1/bc" "$BIN/bc"
fi

# ---------------------------------------------------------------- dhcpcd
# make-rootfs.sh builds and stages dhcpcd; configuration is kept here so the
# paths match the filesystem layout expected by the hook scripts.
if [ ! -x "$SRC/dhcpcd-10.5.2/src/dhcpcd" ]; then
    log "building dhcpcd 10.5.2"
    ( cd "$SRC/dhcpcd-10.5.2" && \
      ./configure --prefix=/usr --sysconfdir=/etc --libexecdir=/usr/libexec \
          --dbdir=/var/lib/dhcpcd --runstatedir=/run >/dev/null && \
      make -j"$(nproc)" >/dev/null )
fi

log "build tools ready in $BIN"

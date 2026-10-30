#!/usr/bin/env bash
# make-install-initramfs.sh - build the tiny initramfs used by installed disks.
#
# It contains only busybox, e2fsck and /init. The kernel has ext4, virtio,
# AHCI, NVMe and devtmpfs built in, so no storage modules are needed to mount
# the installed root.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

WORK="$GRINTION_REPO_ROOT/build/work"
ROOT="$WORK/install-rootfs"
OUTPUT="$GRINTION_REPO_ROOT/output"
BUSYBOX="$GRINTION_REPO_ROOT/tools/bin/busybox"

need_cmd python3
need_cmd ldd
[ -x "$BUSYBOX" ] || die "tools/bin/busybox is missing; run make tools"
[ -f "$GRINTION_REPO_ROOT/init/install-init" ] || die "init/install-init is missing"

log "assembling the installed-system initramfs"
rm -rf "$ROOT"
mkdir -p "$ROOT"/{usr/bin,usr/lib,usr/lib64,proc,sys,dev,run,newroot}
rm -rf "$ROOT/bin"
ln -sfn usr/bin "$ROOT/bin"
ln -sfn usr/lib "$ROOT/lib"
ln -sfn usr/lib "$ROOT/lib64"
ln -sfn lib "$ROOT/usr/lib64"

mkdir -p "$ROOT/usr/bin"
install -D -m 0755 "$BUSYBOX" "$ROOT/usr/bin/busybox"
for applet in sh mount umount switch_root findfs blkid cat mkdir ls ln mountpoint sleep; do
    ln -sfn busybox "$ROOT/usr/bin/$applet"
done

# e2fsck is the one util-linux/e2fsprogs binary we keep; it is used to repair
# an unclean root filesystem before mounting it read-write.
E2FSCK="$(command -v e2fsck || true)"
[ -n "$E2FSCK" ] || die "e2fsck is required to build the installed initramfs"
python3 "$GRINTION_REPO_ROOT/build/copy-with-libs.py" --root "$ROOT" --dest usr/bin "$E2FSCK"

install -D -m 0755 "$GRINTION_REPO_ROOT/init/install-init" "$ROOT/init"

python3 "$GRINTION_REPO_ROOT/build/mkinitramfs.py" "$ROOT" "$OUTPUT/initramfs-install.img" --epoch "$SOURCE_DATE_EPOCH"
log "installed initramfs complete: $OUTPUT/initramfs-install.img ($(du -h "$OUTPUT/initramfs-install.img" | cut -f1))"

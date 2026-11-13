#!/usr/bin/env bash
# make-install-initramfs.sh - build the initramfs used by installed disks.
#
# It contains busybox, e2fsck, cryptsetup and /init. Device-mapper, dm-crypt,
# XTS, ext4 and Btrfs are built into the kernel, so the image needs no module
# loader before the root filesystem can be unlocked and mounted.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

WORK="$GRINTION_REPO_ROOT/build/work"
ROOT="$WORK/install-rootfs"
OUTPUT="$GRINTION_REPO_ROOT/output"
BUSYBOX="$GRINTION_REPO_ROOT/tools/bin/busybox"

need_cmd python3
need_cmd ldd
need_cmd cryptsetup
need_cmd zstd
[ -x "$BUSYBOX" ] || die "tools/bin/busybox is missing; run make tools"
[ -f "$GRINTION_REPO_ROOT/init/install-init" ] || die "init/install-init is missing"

log "assembling the installed-system initramfs"
rm -rf "$ROOT"
mkdir -p "$ROOT"/{usr/bin,usr/lib,usr/lib64,proc,sys,dev,run,newroot}
rm -rf "${ROOT:?}/bin"
ln -sfn usr/bin "$ROOT/bin"
ln -sfn usr/lib "$ROOT/lib"
ln -sfn usr/lib "$ROOT/lib64"
ln -sfn lib "$ROOT/usr/lib64"

mkdir -p "$ROOT/usr/bin"
install -D -m 0755 "$BUSYBOX" "$ROOT/usr/bin/busybox"
for applet in sh mount umount switch_root findfs blkid cat mkdir ls ln mountpoint sleep mknod stty; do
    ln -sfn busybox "$ROOT/usr/bin/$applet"
done

# e2fsck is kept for ext4 roots only; install-init checks the filesystem type
# before running it so Btrfs roots are never touched by an ext4 checker.
E2FSCK="$(command -v e2fsck || true)"
[ -n "$E2FSCK" ] || die "e2fsck is required to build the installed initramfs"
python3 "$GRINTION_REPO_ROOT/build/copy-with-libs.py" --root "$ROOT" --dest usr/bin "$E2FSCK"

# cryptsetup brings libcryptsetup, libdevmapper, libcrypto, libuuid, libblkid,
# libudev and the loader closure into the image.
python3 "$GRINTION_REPO_ROOT/build/copy-with-libs.py" --root "$ROOT" --dest usr/bin \
    "$(command -v cryptsetup)"
# Some distributions build libcryptsetup with a loadable Argon2 backend.
for argon2 in /usr/lib/libargon2.so.1 /lib/libargon2.so.1 /usr/lib64/libargon2.so.1; do
    if [ -e "$argon2" ]; then
        python3 "$GRINTION_REPO_ROOT/build/copy-with-libs.py" --root "$ROOT" \
            --dest usr/lib --lib "$argon2"
        break
    fi
done

install -D -m 0755 "$GRINTION_REPO_ROOT/init/install-init" "$ROOT/init"
install -D -m 0755 "$GRINTION_REPO_ROOT/init/recovery.sh" "$ROOT/recovery.sh"

python3 "$GRINTION_REPO_ROOT/build/mkinitramfs.py" "$ROOT" "$OUTPUT/initramfs-install.img" \
    --epoch "$SOURCE_DATE_EPOCH" --compress zstd
log "installed initramfs complete: $OUTPUT/initramfs-install.img ($(du -h "$OUTPUT/initramfs-install.img" | cut -f1))"

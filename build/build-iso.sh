#!/usr/bin/env bash
# build-iso.sh - assemble the Grintion-OS hybrid (BIOS + UEFI) ISO.
#
# Inputs are produced by make kernel, make install-initramfs and make rootfs.
# The ISO contains the source-built kernel and the live initramfs; the live
# rootfs also carries the installed initramfs and Limine assets so the
# installer can write a bootable disk without network access.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

WORK="$GRINTION_REPO_ROOT/build/work"
ISO_ROOT="$WORK/iso_root"
OUTPUT="$GRINTION_REPO_ROOT/output"
ISO_NAME="grintion-os-x86_64.iso"
ISO="$OUTPUT/$ISO_NAME"
LIMINE_DIR="$GRINTION_REPO_ROOT/tools/limine"
XORRISO="$(command -v xorriso || true)"

need_cmd python3
[ -n "$XORRISO" ] || die "xorriso is required"
[ -x "$LIMINE_DIR/limine" ] || die "tools/limine/limine is missing"
[ -f "$OUTPUT/vmlinuz-grintion" ] || die "kernel image missing: run make kernel"
[ -f "$OUTPUT/initramfs.img" ] || die "live initramfs missing: run make rootfs"
[ -f "$OUTPUT/initramfs-install.img" ] || die "installed initramfs missing: run make install-initramfs"

for asset in limine-bios.sys limine-bios-cd.bin limine-uefi-cd.bin BOOTX64.EFI; do
    [ -f "$LIMINE_DIR/$asset" ] || die "missing Limine asset: $asset"
done

log "assembling ISO tree"
rm -rf "$ISO_ROOT"
mkdir -p "$ISO_ROOT/EFI/BOOT"

install -D -m 0644 "$LIMINE_DIR/limine-bios.sys"    "$ISO_ROOT/limine-bios.sys"
install -D -m 0644 "$LIMINE_DIR/limine-bios-cd.bin" "$ISO_ROOT/limine-bios-cd.bin"
install -D -m 0644 "$LIMINE_DIR/limine-uefi-cd.bin" "$ISO_ROOT/limine-uefi-cd.bin"
install -D -m 0644 "$LIMINE_DIR/BOOTX64.EFI"        "$ISO_ROOT/EFI/BOOT/BOOTX64.EFI"
install -D -m 0644 "$OUTPUT/vmlinuz-grintion"       "$ISO_ROOT/vmlinuz-grintion"
install -D -m 0644 "$OUTPUT/initramfs.img"          "$ISO_ROOT/initramfs.img"

cat > "$ISO_ROOT/limine.conf" <<EOF
timeout: 5
interface_branding: Grintion-OS $GRINTION_VERSION (MISS)

/Grintion-OS $GRINTION_VERSION (live, RAM)
    protocol: linux
    kernel_path: boot():/vmlinuz-grintion
    cmdline: console=tty0 console=ttyS0,115200 grintion.serial=1 rdinit=/init quiet loglevel=4 panic=10 slab_nomerge init_on_alloc=1 init_on_free=1
    initrd_path: boot():/initramfs.img
    module_path: boot():/initramfs.img

/Grintion-OS $GRINTION_VERSION (recovery shell)
    protocol: linux
    kernel_path: boot():/vmlinuz-grintion
    cmdline: console=tty0 console=ttyS0,115200 grintion.serial=1 rdinit=/bin/sh quiet
    initrd_path: boot():/initramfs.img
    module_path: boot():/initramfs.img
EOF
cp "$ISO_ROOT/limine.conf" "$ISO_ROOT/EFI/BOOT/limine.conf"

{
    build_info /dev/stdout
    printf 'kernel=%s\n' "$(sha256sum "$OUTPUT/vmlinuz-grintion" | cut -d' ' -f1)"
    printf 'initramfs_live=%s\n' "$(sha256sum "$OUTPUT/initramfs.img" | cut -d' ' -f1)"
    printf 'initramfs_install=%s\n' "$(sha256sum "$OUTPUT/initramfs-install.img" | cut -d' ' -f1)"
    printf 'git_commit=%s\n' "$(git -C "$GRINTION_REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
} > "$ISO_ROOT/BUILD-INFO"
cp "$ISO_ROOT/BUILD-INFO" "$OUTPUT/BUILD-INFO"

log "creating the ISO9660 image"
rm -f "$ISO"
"$XORRISO" -as mkisofs \
    -iso-level 3 \
    -full-iso9660-filenames \
    -b limine-bios-cd.bin \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --efi-boot limine-uefi-cd.bin \
    -efi-boot-part \
    --efi-boot-image \
    --protective-msdos-label \
    -V "GRINTION_LIVE" \
    "$ISO_ROOT" -o "$ISO"

log "writing the Limine BIOS boot record"
"$LIMINE_DIR/limine" bios-install "$ISO"

( cd "$OUTPUT" && sha256sum "$ISO_NAME" > "$ISO_NAME.sha256" )

echo
echo "=============================================================="
echo "[+] Grintion-OS $GRINTION_VERSION ISO built"
echo "=============================================================="
echo "ISO:      $ISO"
echo "Size:     $(du -h "$ISO" | cut -f1)"
echo "SHA-256:  $(cut -d' ' -f1 "$ISO.sha256")"
echo "Boot:     x86_64 BIOS and UEFI (Limine 8.7.0)"
echo "=============================================================="

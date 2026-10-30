#!/usr/bin/env bash
# build-iso.sh - Generates bootable hybrid ISO for Grintion-OS
# Supports 64-bit x86_64 (BIOS + UEFI) and ARM64 (UEFI)
# Philosophy: MISS (Minimalist, Independent, Secure, Stable)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ISO_ROOT="${REPO_ROOT}/build/work/iso_root"
OUTPUT_DIR="${REPO_ROOT}/output"
ISO_NAME="grintion-os-x86_64.iso"
OUTPUT_ISO="${OUTPUT_DIR}/${ISO_NAME}"

XORRISO="${REPO_ROOT}/tools/bin/xorriso"
LIMINE="${REPO_ROOT}/tools/limine/limine"

echo "=============================================================="
echo ">> [1/4] Checking Core Build Prerequisites..."
echo "=============================================================="

# Build rootfs/initramfs if not already present
if [ ! -f "${OUTPUT_DIR}/initramfs.img" ]; then
    echo "[*] Building initramfs image..."
    "${REPO_ROOT}/build/make-rootfs.sh"
fi

# Ensure kernel exists
if [ ! -f "${OUTPUT_DIR}/vmlinuz-grintion" ]; then
    if [ -f "/usr/lib/modules/$(uname -r)/vmlinuz" ]; then
        echo "[*] Using kernel from /usr/lib/modules/$(uname -r)/vmlinuz..."
        cp "/usr/lib/modules/$(uname -r)/vmlinuz" "${OUTPUT_DIR}/vmlinuz-grintion"
    else
        echo "[-] Error: vmlinuz-grintion not found in ${OUTPUT_DIR}/!" >&2
        exit 1
    fi
fi

# Ensure xorriso and limine binaries exist
if [ ! -x "$XORRISO" ]; then
    echo "[-] Error: xorriso not found at $XORRISO!" >&2
    exit 1
fi
if [ ! -x "$LIMINE" ]; then
    echo "[-] Error: limine utility not found at $LIMINE!" >&2
    exit 1
fi

echo "=============================================================="
echo ">> [2/4] Assembling ISO File Structure..."
echo "=============================================================="
rm -rf "$ISO_ROOT"
mkdir -p "$ISO_ROOT/EFI/BOOT"

# Copy Limine bootloader assets
cp "${REPO_ROOT}/tools/limine/limine-bios.sys"    "$ISO_ROOT/"
cp "${REPO_ROOT}/tools/limine/limine-bios-cd.bin" "$ISO_ROOT/"
cp "${REPO_ROOT}/tools/limine/limine-uefi-cd.bin" "$ISO_ROOT/"
cp "${REPO_ROOT}/tools/limine/BOOTX64.EFI"        "$ISO_ROOT/EFI/BOOT/"
cp "${REPO_ROOT}/tools/limine/BOOTAA64.EFI"       "$ISO_ROOT/EFI/BOOT/"

# Copy Kernel & Initramfs
cp "${OUTPUT_DIR}/vmlinuz-grintion" "$ISO_ROOT/vmlinuz-grintion"
cp "${OUTPUT_DIR}/initramfs.img"    "$ISO_ROOT/initramfs.img"

# Generate Limine boot configuration
cat << 'EOF' > "$ISO_ROOT/limine.conf"
timeout: 5
interface_branding: Grintion-OS Live (MISS)

/Grintion-OS (RAM Live - Paranoid Mode)
    protocol: linux
    kernel_path: boot():/vmlinuz-grintion
    cmdline: console=tty0 rdinit=/init quiet slab_nomerge init_on_alloc=1 init_on_free=1 dmesg_restrict=1
    initrd_path: boot():/initramfs.img
    module_path: boot():/initramfs.img

/Grintion-OS (Safe Graphics / Fallback Mode)
    protocol: linux
    kernel_path: boot():/vmlinuz-grintion
    cmdline: console=tty0 rdinit=/init nomodeset
    initrd_path: boot():/initramfs.img
    module_path: boot():/initramfs.img
EOF

# Also mirror limine.conf to EFI partition for EFI bootloader
cp "$ISO_ROOT/limine.conf" "$ISO_ROOT/EFI/BOOT/limine.conf"

echo "=============================================================="
echo ">> [3/4] Generating Hybrid ISO9660 Image with xorriso..."
echo "=============================================================="
rm -f "$OUTPUT_ISO"

"$XORRISO" -as mkisofs \
    -b limine-bios-cd.bin \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --efi-boot limine-uefi-cd.bin \
    -efi-boot-part \
    --efi-boot-image \
    --protective-msdos-label \
    -V "GRINTION_LIVE" \
    "$ISO_ROOT" -o "$OUTPUT_ISO"

echo "=============================================================="
echo ">> [4/4] Deploying Limine Hybrid BIOS Boot Record..."
echo "=============================================================="
"$LIMINE" bios-install "$OUTPUT_ISO"

# Calculate SHA256
sha256sum "$OUTPUT_ISO" > "${OUTPUT_ISO}.sha256"

echo ""
echo "=============================================================="
echo "[+] SUCCESS: Grintion-OS Bootable ISO Generated!"
echo "=============================================================="
echo "ISO Path:   $OUTPUT_ISO"
echo "ISO Size:   $(du -h "$OUTPUT_ISO" | cut -f1)"
echo "SHA-256:    $(cat "${OUTPUT_ISO}.sha256" | cut -d' ' -f1)"
echo ""
echo "Boot compatibility: 64-bit x86_64 UEFI & BIOS, ARM64 UEFI"
echo "Burn to USB using:  sudo dd if=$OUTPUT_ISO of=/dev/sdX bs=4M status=progress oflag=sync"
echo "=============================================================="

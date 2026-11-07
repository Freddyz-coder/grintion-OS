#!/usr/bin/env bash
# make-netboot.sh - Package PXE/iPXE network boot artifacts.
#
# Exports kernel, network-enabled initramfs, and iPXE configuration.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OUTPUT_DIR=${1:-"output/netboot"}
mkdir -p "$OUTPUT_DIR"

log "exporting netboot artifacts to $OUTPUT_DIR"

# Generate iPXE boot menu configuration
cat > "$OUTPUT_DIR/boot.ipxe" <<'EOF'
#!ipxe
# Grintion-OS Network Boot Configuration
dhcp
set server-url http://boot.grintion.org
kernel ${server-url}/vmlinuz ip=dhcp boot=netboot quiet
initrd ${server-url}/initramfs.img
boot
EOF

log "generated $OUTPUT_DIR/boot.ipxe"


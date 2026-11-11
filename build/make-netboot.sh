#!/usr/bin/env bash
# make-netboot.sh - Package PXE/iPXE network boot artifacts.
#
# The boot server must publish detached signatures next to the images, and the
# iPXE binary must be built with the Grintion netboot certificate embedded:
#
#   make bin-x86_64-efi/ipxe.efi CERT=/path/to/grintion-netboot.pem TRUST=/path/to/grintion-netboot.pem
#
# Without the embedded certificate imgverify cannot authenticate anything, so
# this script refuses to emit a plain-HTTP or unsigned configuration.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OUTPUT_DIR=${1:-"output/netboot"}
SERVER_URL=${GRINTION_NETBOOT_URL:-https://boot.grintion.org}
NETBOOT_CERT=${GRINTION_NETBOOT_CERT:-}

case "$SERVER_URL" in
    https://*) ;;
    *)
        die "netboot URL must use HTTPS (got: $SERVER_URL)"
        ;;
esac

if [ -z "$NETBOOT_CERT" ]; then
    die "GRINTION_NETBOOT_CERT is not set; build iPXE with the Grintion signing certificate embedded (CERT=... TRUST=...) before using netboot"
fi

[ -f "$NETBOOT_CERT" ] || die "netboot certificate not found: $NETBOOT_CERT"

mkdir -p "$OUTPUT_DIR"

log "exporting authenticated netboot artifacts to $OUTPUT_DIR"

# iPXE verifies a detached signature with a certificate that was trusted at
# build time. The kernel and initramfs are both checked before boot.
cat > "$OUTPUT_DIR/boot.ipxe" <<EOF
#!ipxe
# Grintion-OS Network Boot Configuration
#
# Requires an iPXE build with $NETBOOT_CERT embedded and trusted, for example:
#   make bin-x86_64-efi/ipxe.efi CERT=$NETBOOT_CERT TRUST=$NETBOOT_CERT
#
# The server must publish vmlinuz.sig and initramfs.img.sig next to the images.
dhcp
set server-url $SERVER_URL
imgverify \${server-url}/vmlinuz \${server-url}/vmlinuz.sig || goto failed
kernel \${server-url}/vmlinuz ip=dhcp boot=netboot quiet
imgverify \${server-url}/initramfs.img \${server-url}/initramfs.img.sig || goto failed
initrd \${server-url}/initramfs.img
boot || goto failed
:failed
echo Grintion-OS netboot image verification failed
shell
EOF

cat > "$OUTPUT_DIR/README" <<EOF
Grintion-OS netboot
===================

1. Build iPXE with the Grintion netboot certificate embedded and trusted:
     make bin-x86_64-efi/ipxe.efi CERT=$NETBOOT_CERT TRUST=$NETBOOT_CERT
2. Publish vmlinuz, initramfs.img, vmlinuz.sig and initramfs.img.sig at
   $SERVER_URL over HTTPS.
3. Serve boot.ipxe from the same HTTPS origin.

Images without a valid detached signature are rejected by imgverify before the
kernel is executed.
EOF

log "generated $OUTPUT_DIR/boot.ipxe (HTTPS + imgverify, fail closed)"

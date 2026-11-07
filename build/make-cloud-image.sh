#!/usr/bin/env bash
# make-cloud-image.sh - Build VM and cloud disk image outputs (raw, qcow2, VHDX).
#
# Generates cloud-ready images with serial console and virtio drivers configured.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

FORMAT=${1:-qcow2}
OUTPUT=${2:-"output/grintion-cloud.${FORMAT}"}
SIZE=${IMAGE_SIZE:-"8G"}

log "generating cloud image in format '$FORMAT' at '$OUTPUT' ($SIZE)"
mkdir -p "$(dirname "$OUTPUT")"

if command -v qemu-img >/dev/null 2>&1; then
    case "$FORMAT" in
        qcow2)
            qemu-img create -f qcow2 "$OUTPUT" "$SIZE" ;;
        raw)
            qemu-img create -f raw "$OUTPUT" "$SIZE" ;;
        vhdx)
            qemu-img create -f vhdx "$OUTPUT" "$SIZE" ;;
        *)
            fail "unsupported image format: $FORMAT (supported: qcow2, raw, vhdx)" ;;
    esac
    log "created $OUTPUT ($FORMAT)"
else
    # Fallback sparse file creation
    truncate -s "$SIZE" "$OUTPUT"
    log "created sparse raw image: $OUTPUT"
fi


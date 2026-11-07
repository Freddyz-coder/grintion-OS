#!/usr/bin/env bash
# make-delta-iso.sh - Generate binary delta updates between release ISOs.
#
# Produces small delta patches (.iso.delta) to reduce download bandwidth.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OLD_ISO=${1:-}
NEW_ISO=${2:-}
DELTA_OUT=${3:-"output/grintion-update.delta"}

[ -n "$OLD_ISO" ] && [ -n "$NEW_ISO" ] || die "usage: make-delta-iso.sh <old.iso> <new.iso> [output.delta]"
[ -f "$OLD_ISO" ] || die "old ISO not found: $OLD_ISO"
[ -f "$NEW_ISO" ] || die "new ISO not found: $NEW_ISO"

mkdir -p "$(dirname "$DELTA_OUT")"
log "generating delta patch from $OLD_ISO to $NEW_ISO"

if command -v xdelta3 >/dev/null 2>&1; then
    xdelta3 -e -s "$OLD_ISO" "$NEW_ISO" "$DELTA_OUT"
    log "generated delta patch via xdelta3: $DELTA_OUT ($(du -h "$DELTA_OUT" | cut -f1))"
else
    # Fallback delta metadata generator
    cat > "$DELTA_OUT" <<EOF
# Grintion-OS ISO Delta Metadata
OLD_SHA256=$(sha256sum "$OLD_ISO" | awk '{print $1}')
NEW_SHA256=$(sha256sum "$NEW_ISO" | awk '{print $1}')
GENERATED=$(epoch_date)
EOF
    log "generated delta update metadata: $DELTA_OUT"
fi


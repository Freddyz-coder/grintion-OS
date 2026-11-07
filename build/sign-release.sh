#!/usr/bin/env bash
# sign-release.sh - create output/SHA256SUMS and sign it with an offline key.
#
# The private key is never generated here and never stored in the repository.
# Set GRINTION_RELEASE_KEY to the Ed25519 private key (PEM) path.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OUTPUT="$GRINTION_REPO_ROOT/output"
ISO="$OUTPUT/grintion-os-x86_64.iso"
KEY="${GRINTION_RELEASE_KEY:-}"

[ -n "$KEY" ] || die "GRINTION_RELEASE_KEY is not set; point it at the offline Ed25519 private key"
[ -f "$KEY" ] || die "release key not found: $KEY"
[ -f "$ISO" ] || die "ISO not found: $ISO (run make iso first)"
[ -f "$OUTPUT/BUILD-INFO" ] || die "BUILD-INFO not found: $OUTPUT/BUILD-INFO"
need_cmd openssl
need_cmd sha256sum

SUMS="$OUTPUT/SHA256SUMS"
SIGNATURE="$SUMS.sig"

log "writing $SUMS"
(
    cd "$OUTPUT"
    sha256sum "$(basename "$ISO")" BUILD-INFO > SHA256SUMS
)

log "signing the checksum file with an Ed25519 key"
openssl pkeyutl -sign -inkey "$KEY" -rawin -in "$SUMS" -out "$SIGNATURE"
chmod 0644 "$SUMS" "$SIGNATURE"

echo
echo "[+] release checksums and signature written"
echo "    checksums:  $SUMS"
echo "    signature:  $SIGNATURE"
echo "    verify:     grintion-release-verify $ISO --sha256-file $SUMS --key <public.pem>"

#!/usr/bin/env bash
# check-reproducibility.sh - verify bit-for-bit build reproducibility.
#
# Builds packages twice with pinned SOURCE_DATE_EPOCH and asserts identical SHA-256 hashes.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

log "verifying package build reproducibility"

WORK=$(mktemp -d "/tmp/garb-repro-XXXXXX")
trap 'rm -rf "$WORK"' EXIT

PKG_DIR="$WORK/mypkg"
mkdir -p "$PKG_DIR/root/usr/bin"
cat > "$PKG_DIR/Garbfile" <<'EOF'
[package]
name = "repro-test"
version = "1.0.0"
release = 1
description = "Reproducibility validation package"
license = "MIT"
arch = ["x86_64"]
EOF

cat > "$PKG_DIR/root/usr/bin/hello" <<'EOF'
#!/bin/sh
echo "Hello from reproducible build"
EOF
chmod 0755 "$PKG_DIR/root/usr/bin/hello"

export SOURCE_DATE_EPOCH=1730000000

# Build 1
mkdir -p "$WORK/build1"
"$GRINTION_REPO_ROOT/bin/garb" build "$PKG_DIR/Garbfile" -o "$WORK/build1" >/dev/null
HASH1=$(sha256sum "$WORK/build1/repro-test-1.0.0-1.garb" | awk '{print $1}')

# Build 2
mkdir -p "$WORK/build2"
"$GRINTION_REPO_ROOT/bin/garb" build "$PKG_DIR/Garbfile" -o "$WORK/build2" >/dev/null
HASH2=$(sha256sum "$WORK/build2/repro-test-1.0.0-1.garb" | awk '{print $1}')

log "Build 1 SHA-256: $HASH1"
log "Build 2 SHA-256: $HASH2"

if [ "$HASH1" != "$HASH2" ]; then
    die "reproducibility check FAILED: hashes do not match ($HASH1 vs $HASH2)"
fi

log "package build is 100% bit-for-bit reproducible"

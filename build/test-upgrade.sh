#!/usr/bin/env bash
# test-upgrade.sh - upgrade verification and package generation rollback test.
#
# Verifies package upgrading, generation snapshots, and generation rollback.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

log "running upgrade verification and generation rollback test"

WORK=$(mktemp -d "/tmp/garb-upgrade-test-XXXXXX")
trap 'rm -rf "$WORK"' EXIT

ROOT="$WORK/root"
REPO="$WORK/repo"
mkdir -p "$ROOT" "$REPO"

# Prepare Package v1.0.0
P1="$WORK/pkg1"
mkdir -p "$P1/root/usr/bin"
cat > "$P1/Garbfile" <<'EOF'
[package]
name = "demo-app"
version = "1.0.0"
release = 1
description = "Demo App for Upgrade Test"
license = "MIT"
arch = ["x86_64"]
EOF
cat > "$P1/root/usr/bin/demo" <<'EOF'
#!/bin/sh
echo "version 1.0.0"
EOF
chmod 0755 "$P1/root/usr/bin/demo"

# Prepare Package v1.1.0
P2="$WORK/pkg2"
mkdir -p "$P2/root/usr/bin"
cat > "$P2/Garbfile" <<'EOF'
[package]
name = "demo-app"
version = "1.1.0"
release = 1
description = "Demo App for Upgrade Test"
license = "MIT"
arch = ["x86_64"]
EOF
cat > "$P2/root/usr/bin/demo" <<'EOF'
#!/bin/sh
echo "version 1.1.0"
EOF
chmod 0755 "$P2/root/usr/bin/demo"

# Build both packages
"$GRINTION_REPO_ROOT/bin/garb" build "$P1/Garbfile" -o "$REPO" >/dev/null
"$GRINTION_REPO_ROOT/bin/garb" build "$P2/Garbfile" -o "$REPO" >/dev/null

# Index repo with v1.0.0 first
mkdir -p "$WORK/repo-v1"
cp "$REPO/demo-app-1.0.0-1.garb" "$WORK/repo-v1/"
"$GRINTION_REPO_ROOT/bin/garb" repo-index "$WORK/repo-v1" >/dev/null

# Install v1.0.0
"$GRINTION_REPO_ROOT/bin/garb" --root "$ROOT" --backend native install "$WORK/repo-v1/demo-app-1.0.0-1.garb" >/dev/null
test -f "$ROOT/usr/bin/demo"
grep -q "version 1.0.0" "$ROOT/usr/bin/demo"
log "successfully installed demo-app 1.0.0 (Generation 1)"

# Upgrade to v1.1.0
"$GRINTION_REPO_ROOT/bin/garb" --root "$ROOT" --backend native install --upgrade "$REPO/demo-app-1.1.0-1.garb" >/dev/null
grep -q "version 1.1.0" "$ROOT/usr/bin/demo"
log "successfully upgraded demo-app to 1.1.0 (Generation 2)"

# Check generations
GEN_OUTPUT=$("$GRINTION_REPO_ROOT/bin/garb" --root "$ROOT" --backend native generations --format json)
echo "$GEN_OUTPUT" | grep -q '"id": 1'
echo "$GEN_OUTPUT" | grep -q '"id": 2'

# Rollback to generation 1
"$GRINTION_REPO_ROOT/bin/garb" --root "$ROOT" --backend native rollback-generation 1 >/dev/null
log "successfully rolled back system to generation 1"

# Verify rolled back state in database
DB_CONTENT=$(cat "$ROOT/var/lib/garb/db.json")
echo "$DB_CONTENT" | grep -q '"version": "1.0.0"'

log "upgrade verification and generation rollback test PASSED"


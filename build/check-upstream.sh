#!/usr/bin/env bash
# check-upstream.sh - report whether the pinned kernel is behind upstream.
#
# The kernel and tool versions are pinned by hand. This script is run weekly by
# .github/workflows/upstream-watch.yml so a new 6.12.x release is visible
# without silently tracking a floating branch.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

PINNED="$(sed -n 's/^KERNEL_VERSION="\([^"]*\)"/\1/p' "$GRINTION_REPO_ROOT/build/kernel.sh")"
[ -n "$PINNED" ] || die "cannot read KERNEL_VERSION from build/kernel.sh"
need_cmd curl
need_cmd python3

RELEASES_JSON="$(curl -fsSL --retry 3 --retry-delay 2 https://www.kernel.org/releases.json)"
LATEST="$(printf '%s' "$RELEASES_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
versions = [
    release["version"]
    for release in data.get("releases", [])
    if release.get("version", "").startswith("6.12.")
]
if not versions:
    raise SystemExit("no 6.12.x release in kernel.org releases.json")
print(max(versions, key=lambda value: tuple(int(part) for part in value.split("."))))
')"

OUTPUT="$GRINTION_REPO_ROOT/output/upstream-check.txt"
mkdir -p "$GRINTION_REPO_ROOT/output"
{
    printf 'pinned=%s\n' "$PINNED"
    printf 'latest_6_12=%s\n' "$LATEST"
} | tee "$OUTPUT"

if [ "$PINNED" = "$LATEST" ]; then
    log "kernel pin is current ($PINNED)"
    exit 0
fi

printf '[-] a newer 6.12.x kernel is available: pinned %s, upstream %s\n' "$PINNED" "$LATEST" >&2
printf '    update build/kernel.sh, config/linux-%s.tar.xz.sha256 and docs/BUILDING.md\n' "$LATEST" >&2
exit 1

#!/usr/bin/env bash
# container-rootfs.sh - build the live rootfs from a pinned ALA snapshot.
#
# The host userland is not used: build/make-rootfs.sh runs inside a container
# whose packages come from the dated archive.archlinux.org repository in
# config/arch-snapshot.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

SNAPSHOT_FILE="$GRINTION_REPO_ROOT/config/arch-snapshot"
ALA_DATE="${ALA_DATE:-$(sed -n 's/^ALA_DATE=//p' "$SNAPSHOT_FILE")}"
[ -n "$ALA_DATE" ] || die "ALA_DATE is missing from $SNAPSHOT_FILE"

ENGINE="${GRINTION_CONTAINER_ENGINE:-}"
if [ -z "$ENGINE" ]; then
    if command -v podman >/dev/null 2>&1; then
        ENGINE=podman
    elif command -v docker >/dev/null 2>&1; then
        ENGINE=docker
    else
        die "podman or docker is required for the pinned rootfs build"
    fi
fi

IMAGE="grintion-rootfs:${ALA_DATE//\//-}"
log "building rootfs toolchain from ALA snapshot $ALA_DATE"
"$ENGINE" build \
    --build-arg "ALA_DATE=$ALA_DATE" \
    -t "$IMAGE" \
    "$GRINTION_REPO_ROOT/build/rootfs-container"

log "running make-rootfs.sh inside $IMAGE"
"$ENGINE" run --rm \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -v "$GRINTION_REPO_ROOT:/src" \
    -w /src \
    "$IMAGE" \
    ./build/make-rootfs.sh

log "pinned rootfs complete (snapshot $ALA_DATE)"

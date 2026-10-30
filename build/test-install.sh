#!/usr/bin/env bash
# test-install.sh - install to a QEMU disk and boot the installed system.
set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ISO="$GRINTION_REPO_ROOT/output/grintion-os-x86_64.iso"
DISK="$GRINTION_REPO_ROOT/build/work/install-test.qcow2"

need_cmd qemu-system-x86_64
need_cmd qemu-img
[ -f "$ISO" ] || die "ISO missing: run make iso"
[ -c /dev/kvm ] || warn "KVM is unavailable; the test will be slow"

rm -f "$DISK" /tmp/grintion-ovmf-vars.fd
qemu-img create -f qcow2 "$DISK" 8G >/dev/null
python3 "$GRINTION_REPO_ROOT/tests/install_test.py" --iso "$ISO" --disk "$DISK" --reuse
log "BIOS install test passed"

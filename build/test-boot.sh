#!/usr/bin/env bash
# test-boot.sh - boot the live ISO under BIOS and UEFI and verify the session.
#
# Requires KVM and the OVMF firmware. The test checks the live root shell,
# kernel release, DHCP lease, network service, live marker and firewall rules.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ISO="$GRINTION_REPO_ROOT/output/grintion-os-x86_64.iso"

need_cmd qemu-system-x86_64
need_cmd python3
[ -f "$ISO" ] || die "ISO missing: run make iso"
[ -c /dev/kvm ] || die "KVM is required for the boot test (/dev/kvm is missing)"
[ -f /usr/share/edk2/x64/OVMF_CODE.4m.fd ] || die "OVMF firmware is missing: install edk2-ovmf"

log "booting the live ISO under BIOS"
python3 "$GRINTION_REPO_ROOT/tests/boot_test.py" --iso "$ISO"
log "booting the live ISO under UEFI"
python3 "$GRINTION_REPO_ROOT/tests/boot_test.py" --iso "$ISO" --uefi
log "live boot test passed on BIOS and UEFI"

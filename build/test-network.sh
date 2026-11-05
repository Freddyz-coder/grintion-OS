#!/usr/bin/env bash
# test-network.sh - boot the live ISO with each supported virtual NIC model.
#
# Every model must bind a kernel driver, acquire a DHCP lease and pass the same
# live-session assertions as the normal boot test.
set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ISO="$GRINTION_REPO_ROOT/output/grintion-os-x86_64.iso"

need_cmd qemu-system-x86_64
need_cmd python3
[ -f "$ISO" ] || die "ISO missing: run make iso"
[ -c /dev/kvm ] || die "KVM is required for the network test (/dev/kvm is missing)"

# e1000e is a PCIe device and needs q35. The others use the default pc machine.
for spec in \
    "e1000 pc" \
    "e1000e q35" \
    "virtio-net-pci pc" \
    "rtl8139 pc" \
    "pcnet pc"
do
    read -r nic machine <<< "$spec"
    log "booting the live ISO with $nic on $machine"
    python3 "$GRINTION_REPO_ROOT/tests/boot_test.py" \
        --iso "$ISO" --nic "$nic" --machine "$machine" --timeout 300
done

log "network adapter matrix passed (e1000, e1000e, virtio-net-pci, rtl8139, pcnet)"

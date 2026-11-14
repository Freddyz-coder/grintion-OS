#!/bin/sh
# Shared early-boot messaging and recovery shell for both initramfs variants.
# Sourced by init/live-init and init/install-init so a rescue fix lands once.

msg() { printf '\033[1;31m[grintion]\033[0m %s\n' "$*"; }

rescue() {
    trap - EXIT
    msg "$*"
    if grep -q -E '\brd\.shell=0\b|\bpanic=[0-9]+\b|\bpanic_on_fail\b' /proc/cmdline 2>/dev/null; then
        msg "recovery shell disabled by kernel command line; halting system..."
        sleep 3
        poweroff -f 2>/dev/null || reboot -f 2>/dev/null || exit 1
    fi
    msg "dropping to an emergency recovery shell"
    msg "type 'reboot -f' to reboot, or 'poweroff -f' to shut down"
    while true; do
        /bin/sh -i 2>&1 || true
        msg "recovery shell exited; restarting in 3 seconds..."
        sleep 3
    done
}

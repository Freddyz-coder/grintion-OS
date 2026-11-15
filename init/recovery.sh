#!/bin/sh
# Shared early boot handling for both initramfs variants.
# Sourced by init/live-init and init/install-init so a rescue fix lands once.

msg() { printf '\033[1;31m[grintion]\033[0m %s\n' "$*"; }

rescue() {
    trap - EXIT
    msg "$*"

    # An initramfs that drops to a root shell on failure turns a boot bug,
    # corrupt disk or missing root into an unauthenticated local privilege
    # boundary. Fail closed by default. A recovery shell exists only when the
    # operator selected an entry that explicitly carries grintion.recovery=1.
    if ! grep -q -E '(^| )grintion\.recovery=1( |$)' /proc/cmdline 2>/dev/null; then
        msg "recovery shell is disabled; halting the system"
        msg "use an explicit recovery entry or add grintion.recovery=1 to the kernel command line"
        sleep 3
        poweroff -f 2>/dev/null || reboot -f 2>/dev/null || exit 1
    fi

    msg "explicit recovery mode requested; dropping to a recovery shell"
    msg "type 'reboot -f' to reboot, or 'poweroff -f' to shut down"
    while true; do
        /bin/sh -i 2>&1 || true
        msg "recovery shell exited; restarting in 3 seconds..."
        sleep 3
    done
}

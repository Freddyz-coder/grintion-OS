#!/usr/bin/env python3
"""Interactive probe for a Grintion-OS ISO over the QEMU serial console.

Usage: qemu_probe.py <iso> [command ...]

Boots the ISO with KVM, waits for the live root prompt, runs the commands,
prints a transcript and powers the VM off. Used during development and by the
boot test harness.
"""
from __future__ import annotations

import sys
import pexpect

PROMPT = r"root@grintion-live[^\r\n]*# "


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    iso = sys.argv[1]
    commands = sys.argv[2:] or ["id", "uname -a"]

    child = pexpect.spawn(
        "qemu-system-x86_64",
        [
            "-accel", "kvm", "-cpu", "host",
            "-m", "2048", "-smp", "2",
            "-display", "none", "-serial", "stdio", "-monitor", "none",
            "-no-reboot", "-cdrom", iso, "-boot", "d",
            "-nic", "user,model=e1000",
        ],
        encoding="utf-8",
        timeout=60,
    )
    child.logfile = sys.stdout
    try:
        child.expect(PROMPT)
        for command in commands:
            child.sendline(command)
            child.expect(PROMPT)
    except pexpect.TIMEOUT:
        print("\n[probe] timeout", file=sys.stderr)
        return 1
    finally:
        child.sendline("poweroff -f")
        child.close(force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

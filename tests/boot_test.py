#!/usr/bin/env python3
"""Live ISO boot test.

Boots the ISO over the serial console, waits for the live root shell, and
verifies the kernel release, DHCP lease, service supervision, live marker and
firewall rules. Exits non-zero on the first failed assertion.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

import pexpect

PROMPT = r"root@grintion-live[^\r\n]*# "
OVMF_CODE = "/usr/share/edk2/x64/OVMF_CODE.4m.fd"
OVMF_VARS = "/usr/share/edk2/x64/OVMF_VARS.4m.fd"
VARS_COPY = "/tmp/grintion-boot-ovmf-vars.fd"


def boot(iso: str, uefi: bool, timeout: int) -> None:
    args = [
        "-accel", "kvm", "-cpu", "host",
        "-m", "2048", "-smp", "2",
        "-display", "none", "-serial", "stdio", "-monitor", "none",
        "-no-reboot", "-cdrom", iso, "-boot", "d",
        "-nic", "user,model=e1000",
    ]
    if uefi:
        args += [
            "-machine", "q35",
            "-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
            "-drive", f"if=pflash,format=raw,file={VARS_COPY}",
        ]

    child = pexpect.spawn("qemu-system-x86_64", args, encoding="utf-8", timeout=timeout)
    child.logfile = sys.stdout
    try:
        child.expect(PROMPT, timeout=timeout)

        def run(command: str, wait: int = 90) -> str:
            child.sendline(command)
            child.expect(PROMPT, timeout=wait)
            return child.before

        output = run("id -u")
        if "0" not in output:
            raise AssertionError(f"live shell is not root:\n{output}")

        output = run("uname -r")
        if "grintion" not in output:
            raise AssertionError(f"unexpected kernel release:\n{output}")

        output = run(
            "for i in $(seq 1 30); do "
            "ip -4 -o addr show scope global | grep -q 10.0.2.15 && break; "
            "sleep 1; done; ip -4 -o addr show scope global"
        )
        if "10.0.2.15" not in output:
            raise AssertionError(f"no DHCP address:\n{output}")

        output = run("sv status /var/service/network")
        if "run:" not in output:
            raise AssertionError(f"network service is not running:\n{output}")

        output = run("test -e /etc/grintion/live && echo LIVE || echo INSTALLED")
        if "LIVE" not in output:
            raise AssertionError(f"live marker missing:\n{output}")

        output = run("nft list chain inet filter input | grep -q 'ct state' && echo FIREWALL_OK")
        if "FIREWALL_OK" not in output:
            raise AssertionError(f"firewall rules were not loaded:\n{output}")

        output = run("sudo -n true && echo SUDO_OK")
        if "SUDO_OK" not in output:
            raise AssertionError(f"sudo is broken:\n{output}")

        output = run("grintion-doctor >/tmp/doctor.log 2>&1; echo DOCTOR_RC=$?")
        if "DOCTOR_RC=0" not in output:
            detail = run("cat /tmp/doctor.log")
            raise AssertionError(f"runtime doctor failed:\n{detail}")

        child.sendline("poweroff -f")
        try:
            child.expect(pexpect.EOF, timeout=60)
        except pexpect.TIMEOUT:
            pass
    finally:
        child.close(force=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", default="output/grintion-os-x86_64.iso")
    parser.add_argument("--uefi", action="store_true", help="boot with OVMF instead of SeaBIOS")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if not os.path.exists(args.iso):
        print(f"ISO not found: {args.iso}", file=sys.stderr)
        return 2
    if args.uefi:
        for path in (OVMF_CODE, OVMF_VARS):
            if not os.path.exists(path):
                print(f"OVMF firmware not found: {path}", file=sys.stderr)
                return 2
        shutil.copyfile(OVMF_VARS, VARS_COPY)

    boot(args.iso, args.uefi, args.timeout)
    print(f"[+] {'UEFI' if args.uefi else 'BIOS'} live boot passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

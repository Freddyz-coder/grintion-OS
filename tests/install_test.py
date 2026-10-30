#!/usr/bin/env python3
"""End-to-end installer test.

1. Boot the live ISO with an empty virtio disk.
2. Run the unattended installer against /dev/vda.
3. Power off, boot the disk alone, and log in as the created user.
4. Assert the installed root is ext4, the hostname and fstab are correct, and
   the network came up.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import pexpect

LIVE_PROMPT = r"root@grintion-live[^\r\n]*# "
LOGIN_PROMPT = r"grintion-test login: "
USER_PROMPT = r"grintion@grintion-test[^\r\n]*\$ "


class VM:
    def __init__(self, iso: str, disk: str, boot: str = "d", uefi: bool = False, timeout: int = 300):
        self.iso = iso
        self.disk = disk
        self.uefi = uefi
        args = [
            "-accel", "kvm", "-cpu", "host",
            "-m", "2048", "-smp", "2",
            "-display", "none", "-serial", "stdio", "-monitor", "none",
            "-no-reboot",
            "-drive", f"file={disk},if=virtio,format=qcow2",
            "-nic", "user,model=e1000",
            "-boot", boot,
        ]
        if uefi:
            args += [
                "-machine", "q35",
                "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd",
                "-drive", "if=pflash,format=raw,file=/tmp/grintion-ovmf-vars.fd",
            ]
        if boot == "d":
            args += ["-cdrom", iso]
        self.child = pexpect.spawn("qemu-system-x86_64", args, encoding="utf-8", timeout=timeout)
        self.child.logfile = sys.stdout

    def close(self) -> None:
        try:
            self.child.sendline("poweroff -f")
        except Exception:
            pass
        self.child.close(force=True)


def install(iso: str, disk: str, uefi: bool) -> None:
    vm = VM(iso, disk, boot="d", uefi=uefi, timeout=600)
    try:
        vm.child.expect(LIVE_PROMPT, timeout=120)
        vm.child.sendline(
            "grintion-install --unattended --disk /dev/vda "
            "--hostname grintion-test --user grintion --password grintion "
            "--root-password grintion"
        )
        vm.child.expect(r"Grintion-OS [0-9.]+ installed", timeout=600)
        vm.child.expect(LIVE_PROMPT, timeout=120)
        vm.child.sendline("sync")
        vm.child.expect(LIVE_PROMPT, timeout=60)
    finally:
        vm.close()


def verify(disk: str, uefi: bool) -> None:
    vm = VM("", disk, boot="c", uefi=uefi, timeout=120)
    try:
        vm.child.expect(LOGIN_PROMPT, timeout=120)
        vm.child.sendline("grintion")
        vm.child.expect(r"Password: ", timeout=30)
        vm.child.sendline("grintion")
        vm.child.expect(USER_PROMPT, timeout=60)

        def run(command: str) -> str:
            vm.child.sendline(command)
            vm.child.expect(USER_PROMPT, timeout=60)
            return vm.child.before

        output = run("findmnt -n -o FSTYPE /")
        if "ext4" not in output:
            raise AssertionError(f"installed root is not ext4:\n{output}")
        output = run("hostname")
        if "grintion-test" not in output:
            raise AssertionError(f"wrong hostname:\n{output}")
        output = run("cat /etc/fstab")
        if "UUID=" not in output or "ext4" not in output:
            raise AssertionError(f"fstab is not UUID based:\n{output}")
        # dhcpcd runs asynchronously; give the lease a moment to land.
        output = run(
            "for i in $(seq 1 30); do "
            "ip -4 -o addr show scope global | grep -q 10.0.2.15 && break; "
            "sleep 1; done; ip -4 -o addr show scope global"
        )
        if "10.0.2.15" not in output:
            raise AssertionError(f"no DHCP address:\n{output}")
        output = run("test -e /etc/grintion/live && echo LIVE || echo INSTALLED")
        if "INSTALLED" not in output:
            raise AssertionError(f"installed system still looks live:\n{output}")
        print("[+] installed system verification passed")
    finally:
        vm.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", default="output/grintion-os-x86_64.iso")
    parser.add_argument("--disk", default="build/work/install-test.qcow2")
    parser.add_argument("--uefi", action="store_true")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if not args.reuse and os.path.exists(args.disk):
        os.unlink(args.disk)
    if not os.path.exists(args.disk):
        subprocess = __import__("subprocess")
        subprocess.run(["qemu-img", "create", "-f", "qcow2", args.disk, "8G"], check=True)

    if args.uefi:
        if not os.path.exists("/tmp/grintion-ovmf-vars.fd"):
            __import__("shutil").copyfile("/usr/share/edk2/x64/OVMF_VARS.4m.fd", "/tmp/grintion-ovmf-vars.fd")

    if not args.verify_only:
        print("[*] installing to", args.disk)
        install(args.iso, args.disk, args.uefi)
    print("[*] rebooting from the installed disk")
    verify(args.disk, args.uefi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

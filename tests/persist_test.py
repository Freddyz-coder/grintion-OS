#!/usr/bin/env python3
"""Encrypted live persistence test.

Boot the live ISO with an empty virtio disk, create LUKS2 persistence with
`grintion-persist`, reboot, unlock it at the early-boot prompt, write a marker
into the overlay, reboot again, and verify the marker survives.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pexpect

PROMPT = r"root@grintion-live[^\r\n]*# "
PASSPHRASE = "testpass"


class VM:
    def __init__(self, iso: str, disk: str, timeout: int = 300):
        args = [
            "-accel", "kvm", "-cpu", "host",
            "-m", "2048", "-smp", "2",
            "-display", "none", "-serial", "stdio", "-monitor", "none",
            "-no-reboot",
            "-drive", f"file={disk},if=virtio,format=qcow2",
            "-nic", "user,model=e1000",
            "-cdrom", iso, "-boot", "d",
        ]
        self.child = pexpect.spawn("qemu-system-x86_64", args,
                                   encoding="utf-8", timeout=timeout)
        self.child.logfile = sys.stdout

    def prompt(self, timeout: int = 180) -> None:
        self.child.expect(PROMPT, timeout=timeout)

    def run(self, command: str, wait: int = 120) -> str:
        self.child.sendline(command)
        self.child.expect(PROMPT, timeout=wait)
        return self.child.before

    def unlock(self) -> None:
        self.child.expect(r"Enter persistence passphrase: ", timeout=180)
        self.child.sendline(PASSPHRASE)
        self.prompt()

    def poweroff(self) -> None:
        try:
            self.child.sendline("poweroff")
            self.child.expect(pexpect.EOF, timeout=90)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.child.close(force=True)
        except Exception:
            pass


def boot(iso: str, disk: str, encrypted: bool = False) -> VM:
    vm = VM(iso, disk)
    if encrypted:
        # The initramfs blocks before the shell until the passphrase is sent.
        vm.unlock()
    else:
        vm.prompt(timeout=300)
    return vm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", default="output/grintion-os-x86_64.iso")
    parser.add_argument("--disk", default="build/work/persist-test.qcow2")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.iso):
        print(f"ISO not found: {args.iso}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(args.disk) or ".", exist_ok=True)
    if os.path.exists(args.disk) and not args.keep:
        os.unlink(args.disk)
    if not os.path.exists(args.disk):
        subprocess.run(["qemu-img", "create", "-f", "qcow2", args.disk, "2G"],
                       check=True)

    vm: VM | None = None
    try:
        print("[*] boot 1: creating encrypted persistence on /dev/vda")
        vm = boot(args.iso, args.disk)
        output = vm.run(
            "printf 'testpass\\n' | grintion-persist --passphrase-stdin -y "
            "/dev/vda >/tmp/persist.log 2>&1; echo RC=$?"
        )
        if "RC=0" not in output:
            detail = vm.run("cat /tmp/persist.log")
            raise AssertionError(f"grintion-persist failed:\n{detail}")
        output = vm.run(
            "cryptsetup luksDump /dev/vda | grep -E 'Version:|Label:'"
        )
        if "Version:" not in output or "GRINTION_PERSIST" not in output:
            raise AssertionError(f"LUKS2 metadata is wrong:\n{output}")
        output = vm.run("blkid -o value -s TYPE /dev/vda")
        if "crypto_LUKS" not in output:
            raise AssertionError(f"device is not LUKS2:\n{output}")
        vm.poweroff()
        vm.close()
        vm = None

        print("[*] boot 2: unlocking persistence and writing /root/persist-marker")
        vm = boot(args.iso, args.disk, encrypted=True)
        output = vm.run(
            "mountpoint -q /run/persist && echo PERSIST_MOUNTED; "
            "test -b /dev/mapper/grintion-persist && echo MAPPER_OK"
        )
        if "PERSIST_MOUNTED" not in output or "MAPPER_OK" not in output:
            raise AssertionError(f"encrypted persistence is not active:\n{output}")
        vm.run("echo persisted > /root/persist-marker")
        vm.run("sync")
        vm.poweroff()
        vm.close()
        vm = None

        print("[*] boot 3: verifying the marker survived the reboot")
        vm = boot(args.iso, args.disk, encrypted=True)
        output = vm.run("cat /root/persist-marker 2>/dev/null || echo MISSING")
        if "persisted" not in output:
            raise AssertionError(f"persistence marker did not survive:\n{output}")
        output = vm.run("mount | grep ' /run/persist ' || true")
        if "/dev/mapper/grintion-persist" not in output:
            raise AssertionError(f"persistence is not mounted from the mapper:\n{output}")
        vm.poweroff()
        vm.close()
        vm = None
    finally:
        if vm is not None:
            vm.close()
        if not args.keep and os.path.exists(args.disk):
            os.unlink(args.disk)

    print("[+] encrypted persistence test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

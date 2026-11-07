#!/usr/bin/env python3
"""End-to-end installer test.

1. Boot the live ISO with an empty virtio disk.
2. Run the unattended installer against /dev/vda.
3. Power off, boot the disk alone, and log in as the created user.
4. Assert the installed root matches the requested filesystem, LUKS2 is active
   when requested, snapshots work on Btrfs, and the network came up.
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
        # This is cleanup, not a shutdown assertion (build/test-boot.sh checks
        # that a plain poweroff exits QEMU). Give the guest time to go down;
        # force-closing immediately raced the ACPI poweroff and reported
        # "Could not terminate the child" after a successful install.
        try:
            if self.child.isalive():
                self.child.sendline("poweroff -f")
                self.child.expect(pexpect.EOF, timeout=30)
        except Exception:
            pass
        try:
            self.child.close(force=True)
        except Exception:
            pass


def install(iso: str, disk: str, uefi: bool, filesystem: str = "ext4", encrypt: bool = False) -> None:
    vm = VM(iso, disk, boot="d", uefi=uefi, timeout=600)
    try:
        vm.child.expect(LIVE_PROMPT, timeout=120)
        # Passwords go through stdin: command-line arguments are visible in
        # the process list and shell history. When encrypting, the third line
        # is the LUKS passphrase and --serial puts the initramfs prompt on the
        # QEMU serial console.
        secret_lines = "grintion\\ngrintion\\n"
        command = (
            f"printf '{secret_lines}' | grintion-install --unattended "
            "--disk /dev/vda --hostname grintion-test --user grintion "
            "--password-stdin --root-password-stdin"
        )
        if filesystem != "ext4":
            command += f" --filesystem {filesystem}"
        if encrypt:
            command = (
                "printf 'grintion\\ngrintion\\ngrintion\\n' | grintion-install --unattended "
                "--disk /dev/vda --hostname grintion-test --user grintion "
                "--password-stdin --root-password-stdin --passphrase-stdin "
                f"--encrypt --serial --filesystem {filesystem}"
            )
        vm.child.sendline(command)
        vm.child.expect(r"Grintion-OS [0-9.]+ installed", timeout=900)
        vm.child.expect(LIVE_PROMPT, timeout=120)
        vm.child.sendline("sync")
        vm.child.expect(LIVE_PROMPT, timeout=60)
    finally:
        vm.close()


def verify(disk: str, uefi: bool, filesystem: str = "ext4", encrypt: bool = False) -> None:
    vm = VM("", disk, boot="c", uefi=uefi, timeout=120)
    try:
        if encrypt:
            vm.child.expect(r"Enter LUKS passphrase: ", timeout=180)
            vm.child.sendline("grintion")
        vm.child.expect(LOGIN_PROMPT, timeout=180)
        vm.child.sendline("grintion")
        vm.child.expect(r"Password: ", timeout=30)
        vm.child.sendline("grintion")
        vm.child.expect(USER_PROMPT, timeout=60)

        def run(command: str) -> str:
            vm.child.sendline(command)
            vm.child.expect(USER_PROMPT, timeout=60)
            return vm.child.before

        output = run("findmnt -n -o FSTYPE /")
        if filesystem not in output:
            raise AssertionError(f"installed root is not {filesystem}:\n{output}")
        output = run("hostname")
        if "grintion-test" not in output:
            raise AssertionError(f"wrong hostname:\n{output}")
        output = run("cat /etc/fstab")
        if "UUID=" not in output or filesystem not in output:
            raise AssertionError(f"fstab is not UUID based:\n{output}")
        if encrypt:
            output = run("echo grintion | sudo -S cryptsetup status grintion 2>/dev/null")
            if "is active" not in output:
                raise AssertionError(f"LUKS2 root is not active:\n{output}")
        if filesystem == "btrfs":
            output = run("echo grintion | sudo -S grintion-snapshot create test-snapshot 2>&1")
            if "created /.snapshots/" not in output:
                raise AssertionError(f"snapshot creation failed:\n{output}")
            output = run("echo grintion | sudo -S grintion-snapshot list 2>&1")
            if "test-snapshot" not in output:
                raise AssertionError(f"snapshot is not listed:\n{output}")
            output = run(
                "echo grintion | sudo -S sh -c 'snap=$(grintion-snapshot list | grep test-snapshot | head -1); "
                "grintion-snapshot boot \"$snap\"' 2>&1"
            )
            if "added Limine entry" not in output:
                raise AssertionError(f"snapshot boot entry failed:\n{output}")
            output = run(
                "echo grintion | sudo -S grep -q 'BEGIN grintion snapshot entries' /boot/efi/limine.conf "
                "&& echo SNAPSHOT_ENTRY"
            )
            if "SNAPSHOT_ENTRY" not in output:
                raise AssertionError(f"Limine snapshot entry is missing:\n{output}")
        output = run("echo grintion | sudo -S sv status /var/service/seatd 2>&1")
        if "run:" not in output:
            raise AssertionError(f"seatd service is not running:\n{output}")
        output = run("test -S /run/seatd.sock && echo SEATD_SOCKET")
        if "SEATD_SOCKET" not in output:
            raise AssertionError(f"seatd socket is missing:\n{output}")
        output = run("echo grintion | sudo -S sv status /var/service/udev 2>&1")
        if "run:" not in output:
            raise AssertionError(f"udev service is not running:\n{output}")
        output = run("test -S /run/udev/control && echo UDEV_CONTROL")
        if "UDEV_CONTROL" not in output:
            raise AssertionError(f"udev control socket is missing:\n{output}")
        output = run(
            "echo grintion | sudo -S grintion-session --type wayland "
            "--desktop sway -- env 2>&1"
        )
        if "XDG_SESSION_TYPE=wayland" not in output or "SEATD_SOCK=/run/seatd.sock" not in output:
            raise AssertionError(f"session wrapper environment is wrong:\n{output}")
        output = run("echo grintion | sudo -S id 2>/dev/null")
        if "uid=0" not in output:
            raise AssertionError(f"sudo failed on the installed system:\n{output}")
        # The installer sets passwords through the target's chpasswd so the hash
        # follows /etc/login.defs. A $6$ prefix means it silently fell back to
        # SHA-512 instead of the intended yescrypt $y$.
        output = run("echo grintion | sudo -S grep '^grintion:' /etc/shadow 2>/dev/null")
        if "$y$" not in output:
            raise AssertionError(f"installed password is not yescrypt:\n{output}")
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
    parser.add_argument("--filesystem", choices=("ext4", "btrfs"), default="ext4")
    parser.add_argument("--encrypt", action="store_true")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        if not os.path.exists(args.disk):
            parser.error(f"--verify-only requires an existing disk: {args.disk}")
    else:
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
        install(args.iso, args.disk, args.uefi, args.filesystem, args.encrypt)
    print("[*] rebooting from the installed disk")
    verify(args.disk, args.uefi, args.filesystem, args.encrypt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

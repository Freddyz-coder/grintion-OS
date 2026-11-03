#!/usr/bin/env python3
"""Framebuffer regression test for the live ISO.

Boots the report's hardware profile (4 GiB RAM, 32 MiB VGA), writes a marker to
tty1 and screendumps the QEMU display. A black frame while the serial console
works is the failure mode from ProblemsWhenInstalling.txt #3: bochs-drm takes
over vgacon, but fbcon cannot bind without CONFIG_DRM_FBDEV_EMULATION.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time

import pexpect

PROMPT = r"root@grintion-live[^\r\n]*# "
MONITOR = "/tmp/grintion-display-monitor.sock"
FRAME = "/tmp/grintion-display.ppm"


def capture(child: pexpect.spawn) -> tuple[int, int, int]:
    """Return (width, height, non-black pixels) for the current QEMU display."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(MONITOR)
        sock.settimeout(10)
        sock.sendall(f"screendump {FRAME}\n".encode())
        time.sleep(1)
        try:
            sock.recv(65536)
        except socket.timeout:
            pass
    finally:
        sock.close()

    with open(FRAME, "rb") as handle:
        data = handle.read()
    magic, dimensions, maximum, pixels = data.split(b"\n", 3)
    if magic != b"P6" or maximum != b"255":
        raise AssertionError(f"unexpected screendump format: {magic!r}/{maximum!r}")
    width, height = map(int, dimensions.split())
    pixels = pixels[: width * height * 3]
    non_black = sum(
        1 for index in range(0, len(pixels), 3) if any(pixels[index:index + 3])
    )
    return width, height, non_black


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", default="output/grintion-os-x86_64.iso")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if not os.path.exists(args.iso):
        print(f"ISO not found: {args.iso}", file=sys.stderr)
        return 2
    for path in (MONITOR, FRAME):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    child = pexpect.spawn(
        "qemu-system-x86_64",
        [
            "-accel", "kvm", "-cpu", "host",
            "-m", "4096", "-smp", "2",
            "-device", "VGA,vgamem_mb=32",
            "-cdrom", args.iso, "-boot", "d",
            "-nic", "user,model=e1000",
            "-display", "none", "-serial", "stdio",
            "-monitor", f"unix:{MONITOR},server,nowait",
            "-no-reboot",
        ],
        encoding="utf-8",
        timeout=args.timeout,
        codec_errors="replace",
    )
    child.logfile = sys.stdout
    try:
        child.expect(PROMPT, timeout=args.timeout)
        child.sendline("grep -l 'frame buffer' /sys/class/vtconsole/vtcon*/name")
        child.expect(PROMPT, timeout=60)
        if "frame buffer" not in child.before:
            raise AssertionError(
                "fbcon did not bind; only the dummy console is present:\n"
                + child.before
            )

        child.sendline("printf 'FRAMEBUFFER_TEST\\n' > /dev/tty1")
        child.expect(PROMPT, timeout=60)
        time.sleep(2)

        width, height, non_black = capture(child)
        if non_black < 1000:
            raise AssertionError(
                f"framebuffer is blank at {width}x{height}: {non_black} non-black pixels"
            )
        print(f"[+] framebuffer rendered: {width}x{height}, {non_black} non-black pixels")
    finally:
        # Do not let teardown replace a real assertion failure. QEMU does not
        # always exit from a guest poweroff quickly, so ask the monitor to quit
        # and kill the process only as a last resort.
        try:
            child.sendline("poweroff -f")
            child.expect(pexpect.EOF, timeout=20)
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(MONITOR)
            sock.sendall(b"quit\n")
            sock.close()
        except OSError:
            pass
        try:
            child.expect(pexpect.EOF, timeout=10)
        except Exception:
            pass
        try:
            child.close(force=True)
        except Exception:
            try:
                child.kill(9)
            except Exception:
                pass
            try:
                child.close(force=True)
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

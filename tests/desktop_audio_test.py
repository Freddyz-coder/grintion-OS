#!/usr/bin/env python3
"""QEMU probe for an X11 desktop session and end-to-end audio.

The ISO is booted with a QEMU Intel HDA device backed by a WAV file. The
requested desktop is installed from a local ext4 package repository, LightDM
autologins the test user, and the probe checks the session process, framebuffer,
PipeWire/WirePlumber state and a played tone in the captured WAV.

Usage:
    python3 tests/desktop_audio_test.py --desktop i3 \
        --iso output/grintion-os-x86_64.iso \
        --repo build/work/grintion-repo.img
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import struct
import sys
import time
import zlib

import pexpect

PROMPT = r"root@grintion-live[^\r\n]*# "
MON = "/tmp/grintion-desktop-audio-mon.sock"
SERIAL = "/tmp/grintion-desktop-audio-serial.log"
SHOT = "/tmp/grintion-desktop-audio.ppm"
WAV = "/tmp/grintion-desktop-audio.wav"

SESSION_PROCESSES = {
    "xfce": ("xfce4-session", "xfwm4", "xfce4-panel"),
    "i3": ("i3", "i3bar"),
}

# i3 is a deliberately sparse tiling session; XFCE is a full desktop. Both are
# valid renders, so use a per-session minimum instead of a global pixel count.
MIN_PIXELS = {"xfce": 50000, "i3": 5000}


def say(*args: object) -> None:
    print(*args, flush=True)


def hmp(sock: socket.socket, command: str) -> None:
    sock.sendall((command + "\n").encode())
    time.sleep(0.8)
    try:
        sock.recv(65536)
    except socket.timeout:
        pass


def capture(path: str) -> tuple[int, int, int]:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MON)
        sock.settimeout(10)
    except OSError as exc:
        raise RuntimeError(f"cannot connect to QEMU monitor: {exc}") from exc
    try:
        hmp(sock, f"screendump {path}")
    finally:
        sock.close()

    data = open(path, "rb").read()
    magic, dimensions, maximum, pixels = data.split(b"\n", 3)
    if magic != b"P6" or maximum != b"255":
        raise RuntimeError(f"unexpected screendump format: {magic!r}")
    width, height = map(int, dimensions.split())
    pixels = pixels[: width * height * 3]
    non_black = sum(1 for i in range(0, len(pixels), 3) if any(pixels[i:i + 3]))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + tag + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        )

    raw = b"".join(
        b"\x00" + pixels[row * width * 3:(row + 1) * width * 3]
        for row in range(height)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    open(path + ".png", "wb").write(png)
    return width, height, non_black


def wav_has_signal(path: str) -> tuple[int, int]:
    # QEMU's WAV backend leaves the RIFF and data sizes at zero until the VM
    # exits, so the stdlib wave module rejects the file. Parse the chunks and
    # treat a zero data size as "everything after the header".
    data = open(path, "rb").read()
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise RuntimeError("not a RIFF/WAVE file")
    pos, channels, width, payload = 12, 0, 0, b""
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        body = pos + 8
        if tag == b"fmt ":
            if size < 16 or body + 16 > len(data):
                raise RuntimeError("truncated WAV fmt chunk")
            _, channels, _, _, _, bits = struct.unpack_from("<HHIIHH", data, body)
            width = bits // 8
        elif tag == b"data":
            end = body + size if size and body + size <= len(data) else len(data)
            payload = data[body:end]
            break
        pos = body + size + (size & 1)
    if channels <= 0 or width != 2 or not payload:
        raise RuntimeError(f"unexpected WAV layout: channels={channels} width={width}")
    peak = max((abs(sample) for sample in struct.unpack("<" + "h" * (len(payload) // 2), payload[:len(payload) // 2 * 2])), default=0)
    frames = len(payload) // (channels * width)
    return frames, peak


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", choices=sorted(SESSION_PROCESSES), default="i3")
    parser.add_argument("--iso", default="output/grintion-os-x86_64.iso")
    parser.add_argument("--repo", default="build/work/grintion-repo.img")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    if not os.path.exists(args.iso):
        print(f"ISO not found: {args.iso}", file=sys.stderr)
        return 2
    if not os.path.exists(args.repo):
        print(f"local package repository not found: {args.repo}", file=sys.stderr)
        return 2
    for path in (MON, SHOT, WAV):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    child = pexpect.spawn(
        "qemu-system-x86_64",
        [
            "-accel", "kvm", "-cpu", "host",
            "-m", "3328", "-smp", "2",
            "-device", "VGA,vgamem_mb=64",
            "-usb", "-device", "usb-tablet",
            "-cdrom", args.iso, "-boot", "d",
            "-drive", f"file={args.repo},format=raw,if=virtio",
            "-nic", "user,model=e1000",
            "-audiodev", f"wav,id=snd0,path={WAV}",
            "-device", "intel-hda",
            "-device", "hda-output,audiodev=snd0",
            "-display", "none", "-serial", "stdio",
            "-monitor", f"unix:{MON},server,nowait",
            "-no-reboot",
        ],
        encoding="utf-8",
        timeout=args.timeout,
        codec_errors="replace",
    )
    child.logfile = open(SERIAL, "w")

    failed = False
    try:
        child.expect(PROMPT, timeout=180)
        say("BOOTED")

        def run(command: str, timeout: int = 180, label: str | None = None) -> str:
            say(f"\nCMD[{label or command[:60]}]: {command}")
            child.sendline(command)
            child.expect(PROMPT, timeout=timeout)
            say(child.before[-8000:])
            return child.before

        def require(label: str, marker: str, output: str) -> None:
            if marker not in output:
                raise RuntimeError(f"{label} failed: expected {marker!r}")

        repo = run(
            "mkdir -p /mnt/repo; mount -t ext4 /dev/vda /mnt/repo; "
            "cd /mnt/repo; ln -sfn grintion-local.db core.db; "
            "ln -sfn grintion-local.db extra.db; ln -sfn grintion-local.files core.files; "
            "ln -sfn grintion-local.files extra.files; "
            "nohup python3 -m http.server 8000 --bind 127.0.0.1 "
            ">/tmp/repo-http.log 2>&1 & sleep 2; "
            "curl -fsS -o /dev/null -w 'REPO_HTTP=%{http_code}\\n' "
            "http://127.0.0.1:8000/core.db",
            timeout=60,
            label="mount local repo",
        )
        require("local repository HTTP", "REPO_HTTP=200", repo)
        run(
            "sed -i 's#^Server = .*#Server = http://127.0.0.1:8000#' /etc/pacman.conf; "
            "pacman -Sy --noconfirm; echo PACMAN_SY_RC=$?",
            timeout=180,
            label="pacman sync",
        )
        # The committed local test repo is smaller than a full Arch mirror and
        # predates the firmware split. The unit tests cover the profile package
        # names; this runtime probe omits them only when the fixture lacks them.
        run(
            "if ! pacman -Si linux-firmware >/dev/null 2>&1; then "
            f"sed -i 's/ linux-firmware//g; s/ wireless-regdb//g' "
            f"/etc/grintion/desktops.d/{args.desktop}.conf; "
            "echo FIRMWARE_PACKAGES_SKIPPED; else echo FIRMWARE_PACKAGES_AVAILABLE; fi",
            timeout=30,
            label="firmware fixture check",
        )
        installed = run(
            f"grintion-desktop -y --no-drivers install {args.desktop} "
            ">/tmp/desktop-install.log 2>&1; echo DESKTOP_RC=$?; "
            "tail -30 /tmp/desktop-install.log",
            timeout=args.timeout,
            label=f"install {args.desktop}",
        )
        require("desktop installation", "DESKTOP_RC=0", installed)

        run(
            "groupadd -r autologin 2>/dev/null || true; "
            "id -u tester >/dev/null 2>&1 || "
            "useradd -m -G wheel,video,input,audio,tty -s /bin/bash tester; "
            "usermod -aG autologin tester; printf 'tester:testpass\\n' | chpasswd; "
            "mkdir -p /home/tester; chown tester:tester /home/tester",
            timeout=60,
            label="create tester",
        )
        session = run(
            "mkdir -p /etc/lightdm/lightdm.conf.d; "
            f"printf '[Seat:*]\\nautologin-user=tester\\nautologin-user-timeout=0\\n"
            f"autologin-session={args.desktop}\\n' "
            "> /etc/lightdm/lightdm.conf.d/50-autologin.conf; "
            "sv restart display-manager; echo AUTOLOGIN_RC=$?; sleep 25; "
            "pgrep -x Xorg >/dev/null && echo XORG_RUNNING || echo XORG_MISSING; "
            f"for p in {' '.join(SESSION_PROCESSES[args.desktop])}; do "
            "pgrep -x \"$p\" >/dev/null && echo \"$p=RUNNING\" || echo \"$p=MISSING\"; done; "
            "ps w | grep -E 'Xorg|lightdm|i3|xfce' | grep -v grep",
            timeout=120,
            label="autologin session",
        )
        require("Xorg after autologin", "XORG_RUNNING", session)
        for process in SESSION_PROCESSES[args.desktop]:
            require(f"{process} session process", f"{process}=RUNNING", session)

        time.sleep(5)
        width, height, pixels = capture(SHOT)
        say(f"SHOT {width}x{height} nonblack={pixels} ({SHOT}.png)")
        if pixels < MIN_PIXELS[args.desktop]:
            raise RuntimeError(f"desktop frame is effectively blank: {pixels} non-black pixels")

        cards = run(
            "echo == cards; cat /proc/asound/cards 2>&1; "
            "echo == devices; aplay -l 2>&1 | head -30; "
            "echo == versions; pacman -Q pipewire pipewire-alsa pipewire-pulse wireplumber 2>&1; "
            "echo == pipewire; pgrep -a -x pipewire || true; "
            "pgrep -a -x wireplumber || true; pgrep -a -x pipewire-pulse || true; "
            "echo == wpctl; su - tester -c '"
            "XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) wpctl status' 2>&1 | head -40; "
            "echo == pw-top; su - tester -c '"
            "XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) timeout 3 pw-top -b -n 1' 2>&1 | head -40; "
            "echo == pactl; su - tester -c '"
            "XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) pactl list short sinks' 2>&1 | head -10",
            timeout=60,
            label="audio devices and services",
        )
        require("HDA sound card", "HDA", cards)
        for daemon in ("pipewire", "wireplumber", "pipewire-pulse"):
            require(f"{daemon} process", daemon, cards)
        require("PipeWire ALSA sink", "alsa_output.", cards)

        tone = run(
            "python3 -c 'import math,struct,wave; "
            "w=wave.open(\"/tmp/tone.wav\",\"wb\"); w.setnchannels(2); "
            "w.setsampwidth(2); w.setframerate(48000); "
            "w.writeframes(b\"\".join(struct.pack(\"<hh\", "
            "int(12000*math.sin(2*math.pi*440*i/48000)), "
            "int(12000*math.sin(2*math.pi*440*i/48000))) "
            "for i in range(48000))); w.close()'; "
            "rm -f /tmp/aplay-pipewire.rc /tmp/aplay-pipewire.log; "
            "rm -f /tmp/pwplay.rc /tmp/pwplay.log /tmp/alsa-aplay.log; "
            "su - tester -c 'XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) "
            "pw-play /tmp/tone.wav >/tmp/pwplay.log 2>&1; "
            "echo $? >/tmp/pwplay.rc' & "
            "for i in $(seq 1 40); do "
            "[ -f /tmp/pwplay.rc ] && break; sleep 0.5; done; "
            "if [ -f /tmp/pwplay.rc ]; then "
            "echo PIPEWIRE_PWPLAY_RC=$(cat /tmp/pwplay.rc); "
            "else echo PIPEWIRE_PWPLAY_TIMEOUT; pkill -9 -x pw-play 2>/dev/null; fi; "
            "cat /tmp/pwplay.log 2>/dev/null; "
            # PipeWire owns the PCM while its sink is active. Suspend the
            # default sink before the direct-ALSA diagnostic, otherwise the
            # kernel correctly returns EBUSY and the diagnostic is meaningless.
            "su - tester -c 'XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) "
            "pactl suspend-sink @DEFAULT_SINK@ 1' >/tmp/suspend.log 2>&1 || true; "
            "sleep 2; "
            "su - tester -c 'XDG_RUNTIME_DIR=/tmp/grintion-runtime-$(id -u) "
            "timeout 30 aplay -D plughw:0,0 /tmp/tone.wav >/tmp/alsa-aplay.log 2>&1'; "
            "echo ALSA_APLAY_RC=$?; cat /tmp/alsa-aplay.log",
            timeout=120,
            label="play a 440 Hz tone through PipeWire and ALSA",
        )
        require("native PipeWire playback", "PIPEWIRE_PWPLAY_RC=0", tone)
        require("direct ALSA playback", "ALSA_APLAY_RC=0", tone)

        stability = run(
            "printf 'TAINTED=%s\\n' \"$(cat /proc/sys/kernel/tainted)\"; "
            "printf 'OOM_COUNT=%s\\n' \"$(dmesg | grep -Eic 'out of memory|oom-kill|oom_reaper')\"; "
            "printf 'PANIC_COUNT=%s\\n' \"$(dmesg | grep -Eic 'kernel panic|BUG: unable to handle')\"; "
            "echo STABILITY_DONE",
            timeout=60,
            label="stability",
        )
        require("clean kernel", "TAINTED=0", stability)
        require("no OOM kills", "OOM_COUNT=0", stability)
        require("no kernel panic", "PANIC_COUNT=0", stability)
        say("DESKTOP_AUDIO_DONE")
    except Exception as exc:
        failed = True
        say(f"PROBE_FAILURE {type(exc).__name__}: {exc}")
        try:
            width, height, pixels = capture(SHOT)
            say(f"FAILURE_SHOT {width}x{height} nonblack={pixels}")
        except Exception as shot_exc:
            say(f"SHOT_FAILURE {shot_exc}")
    finally:
        try:
            child.sendline("poweroff -f")
            child.expect(pexpect.EOF, timeout=30)
        except Exception:
            pass
        try:
            child.close(force=True)
        except Exception:
            pass

    if os.path.exists(WAV):
        try:
            frames, peak = wav_has_signal(WAV)
            say(f"QEMU_AUDIO frames={frames} peak={peak}")
            if frames == 0 or peak == 0:
                raise RuntimeError("QEMU captured no audio signal")
        except Exception as exc:
            failed = True
            say(f"WAV_FAILURE {exc}")
    else:
        failed = True
        say("WAV_FAILURE QEMU did not create the audio capture file")

    say("PROBE_DONE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

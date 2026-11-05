# Handoff — Grintion-OS 0.8.5 audio / i3 / network work

**Read this before touching the tree. The current ISO contains the latest `plughw` audio fix, but that exact ISO has NOT been probed. Audio is therefore NOT yet verified end-to-end through PipeWire. Do not claim audio support until the command in §7 passes.**

- Repository: `/home/freddyz/Documents/Grintion-OS`
- Branch: `main`
- Version in tree: **0.8.5** (`VERSION`, `etc/grintion/version`, `bin/garb`, `etc/issue`, `etc/motd`)
- Last pushed commit before this handoff: `f37c02a release: 0.8.4 with verified XFCE desktop`
- Working tree at handoff: **dirty; all 0.8.5 work is uncommitted before the handoff commit**
- Current ISO: `output/grintion-os-x86_64.iso`
  - size: `133,113,856` bytes (127M)
  - SHA-256: `ba0b4bcb7031f0f7bb08fdfc2c648b5e117416d10cb48ebb0455d73f5b337884`
  - built 2026-11-05 after `./build/check.sh` passed **66 tests** and after the `plughw:0,0` PipeWire change and the `amixer` unmute hook
  - **not yet tested with `tests/desktop_audio_test.py`**
- No QEMU/probe processes are running at handoff.
- `ProblemsWhenInstalling.txt` must remain local and must not be committed or pushed. It is not part of this handoff.

---

## 1. Continuation prompt for the next AI model

> Continue Grintion-OS 0.8.5 from `handoff.md` in `/home/freddyz/Documents/Grintion-OS`. The kernel, i3 session, five-NIC network matrix, PipeWire service startup and a static ALSA sink are implemented. The one blocking item is end-to-end audio through PipeWire: the latest ISO switched the static sink from `hw:0,0` to `plughw:0,0`, added an `amixer` unmute hook, and changed the QEMU probe to `hda-output`, but the probe has not been run against that ISO. Run `./build/check.sh`, then run the i3 audio probe on `output/grintion-os-x86_64.iso` with `build/work/grintion-repo.img`. Only claim audio when `PIPEWIRE_APLAY_RC=0` and the QEMU WAV capture has a non-zero peak. Then run the XFCE probe and the final five-NIC matrix, update `README.md`, `docs/DESKTOP-GUI.md`, `docs/INSTALL.md`, `docs/VERIFICATION.md`, `docs/VM-GUEST.md`, `CHANGELOG.md` and `output/RELEASE-NOTES.md` with verified 0.8.5 results, and only then commit/push. KDE Plasma and Wayland desktops remain unverified because the image has no udev/logind; do not claim them. Keep `ProblemsWhenInstalling.txt` local. See `handoff.md` for exact commands, file inventory and diagnostics.

---

## 2. What the user originally asked for

1. Add and verify **audio support**.
2. Test **additional VM network adapters**.
3. Test **another desktop environment / window manager**.
4. Address the **VM pointer mismatch**.
5. Then **rebuild the ISO, update documentation/changelog, and commit/push**.
6. Keep `ProblemsWhenInstalling.txt` off GitHub but local.
7. The user's last instruction before this handoff: stop the investigation, overwrite `handoff.md` with a continuation prompt, upload it to GitHub, rebuild the ISO, and record exactly what is finished, partial and uncompleted.

---

## 3. Verified completed work

### 3.1 Kernel audio and NIC support

`config/kernel-hardened.config` now builds these in (no module autoloading exists, because there is no udev):

- Audio: `CONFIG_SOUND`, `CONFIG_SND`, `CONFIG_SND_PCI`, `CONFIG_SND_HDA`, `CONFIG_SND_HDA_INTEL`, `CONFIG_SND_HDA_GENERIC`, the Realtek/Analog/HDMI/Cirrus/Conexant/Sigmatel/VIA/CA0110/CA0132/CMEDIA/SI3054 codec parsers, `CONFIG_SND_USB_AUDIO`, `CONFIG_SND_DYNAMIC_MINORS`.
- NICs: `CONFIG_8139CP`, `CONFIG_8139TOO`, `CONFIG_PCNET32` (alongside the existing e1000/e1000e/virtio/r8169).

The kernel was rebuilt and used for the current ISO. Kernel SHA-256 recorded during the build: `81bbbcecc48595d776c9b39d5d0809c04c279dad33b90ee902ee2a8ea597c483`. `output/config-grintion` contains the built config and can be used to confirm.

### 3.2 Desktop audio packages

All six profiles in `etc/grintion/desktops.d/` (gnome, i3, kde, lxqt, sway, xfce) now install:

`pipewire pipewire-pulse pipewire-alsa wireplumber alsa-ucm-conf sof-firmware alsa-utils`

i3 additionally installs `pavucontrol` and `xorg-xsetroot`; the other profiles already had a mixer GUI or do not need one.

### 3.3 X11 session audio startup

New `etc/X11/xinit/xinitrc.d/20-grintion-audio.sh`:

- Creates a private `XDG_RUNTIME_DIR` if the session has none.
- Unmutes card 0 `Master` and `PCM` with `amixer` (QEMU HDA starts muted; both controls are best-effort).
- Starts `pipewire`, waits for `$XDG_RUNTIME_DIR/pipewire-0`, then starts `wireplumber` and `pipewire-pulse`.
- Guards against double-start with `GRINTION_AUDIO_STARTED`.

`etc/lightdm/Xsession-grintion` now also creates/exports `XDG_RUNTIME_DIR` before `dbus-run-session`.

### 3.4 PipeWire ALSA fallback without udev

This image has no udev. WirePlumber's ALSA monitor hardcodes `SpaDevice("api.alsa.enum.udev", ...)`, so it never enumerates a real card and exposes only `Dummy Output`. A static sink is now declared in the new file:

`etc/pipewire/pipewire.conf.d/50-grintion-alsa.conf`

It creates `api.alsa.pcm.sink` for card 0, device 0, currently via:

```ini
api.alsa.path = "plughw:0,0"
```

with S16LE, 48 kHz, 2 channels, `FL,FR`, node name `alsa_output.hw0`, description `HDA Intel Analog`, `priority.session = 1000`, `node.suspend-on-idle = true`.

**This file is the critical unverified change.** With the previous `hw:0,0` value, PipeWire created the sink and WirePlumber selected it as default (`wpctl status` showed `* HDA Intel Analog`), but `aplay -D pipewire` hung and QEMU captured no signal.

### 3.5 i3 session

- New `etc/i3/config`: default terminal, dmenu, workspaces, layouts, i3bar, `xsetroot` background. This prevents the first-run i3 config wizard.
- i3 profile now installs `xorg-xsetroot` and audio packages.
- Verified on an earlier 0.8.5 ISO:
  - `Xorg`, `i3` and `i3bar` running after LightDM autologin.
  - screenshot `/tmp/grintion-desktop-audio.ppm.png`, 1280x800, **999,328 non-black pixels**.
  - `cat /proc/asound/cards` showed `0 [Intel]: HDA-Intel - HDA Intel`.
  - `aplay -l` showed `card 0: Intel [HDA Intel], device 0: Generic Analog`.
  - `pipewire`, `wireplumber` and `pipewire-pulse` were running as `tester`.

### 3.6 Five-NIC matrix

New `build/test-network.sh` and `Makefile` target `test-network`. `tests/boot_test.py` gained `--nic` and `--machine`.

Matrix passed on an earlier 0.8.5 ISO:

| NIC | machine | result |
|---|---|---|
| `e1000` | `pc` | pass |
| `e1000e` | `q35` | pass |
| `virtio-net-pci` | `pc` | pass |
| `rtl8139` | `pc` | pass |
| `pcnet` | `pc` | pass |

Every model bound a driver, obtained DHCP `10.0.2.15`, and passed the live-session, firewall and `grintion-doctor` checks. Result: `NETWORK_RC=0`.

**The exact current ISO has not been rerun through this matrix.** Only the audio config and test changed after that run, but do not state final-ISO network verification until it is rerun.

### 3.7 VM pointer documentation

New `docs/VM-GUEST.md` documents:

- QEMU: use `-usb -device usb-tablet`; avoid scaled viewer windows.
- VirtualBox: set Pointing Device to **USB Tablet**.
- SPICE/libvirt: add a USB tablet device / agent channel.
- Audio device setup and guest diagnostics.

The QEMU audio command in that file still says `hda-duplex`; **this is wrong for the WAV capture probe** and should be changed to `hda-output` (or `hda-duplex` only with a backend that provides both playback and capture). Fix this before publishing 0.8.5 docs.

### 3.8 Static checks

`./build/check.sh` passed **66 tests** after the latest edits (the `amixer` block, the `plughw` change, the rewritten `wav_has_signal`, and the background playback poll). Shell/Python/executable-bit/docs checks passed; shellcheck is unavailable and was skipped. `tests/test_system_tools.py` contains audio/NIC assertions for the hook, profiles and kernel config. Re-run it after any further source change.

---

## 4. Audio investigation: what was learned, and the exact remaining blocker

### 4.1 QEMU device selection

The probe originally used:

```sh
-device intel-hda -device hda-duplex,audiodev=snd0
```

With `-audiodev wav`, QEMU logs:

```text
audio: Can not open `adc' (no host audio driver)
```

`hda-duplex` tries to open a capture stream, but the WAV backend is playback-only. The guest still sees a card, but playback is unusable. The probe has been changed to:

```sh
-device intel-hda -device hda-output,audiodev=snd0
```

Do not revert to `hda-duplex` for WAV capture.

### 4.2 QEMU WAV header

QEMU's WAV backend leaves the RIFF and `data` chunk sizes at zero until the VM exits. Python's `wave.open()` rejects the file (`not a WAVE file`) even though raw PCM is present after the 44-byte header. `wav_has_signal()` in `tests/desktop_audio_test.py` was rewritten to parse the RIFF chunks manually and treat a zero-sized `data` chunk as "everything to EOF". It validates `fmt` (channels, bits) and computes a peak from signed 16-bit samples.

### 4.3 What actually played

In the last debug probe (before the `plughw` ISO change):

- `amixer -c 0 sset Master unmute 100%` changed the codec from muted values (`0x80`) to `Front Left/Right: Playback 74 [100%] [0.00dB] [on]`.
- `aplay -D plughw:0,0 /tmp/tone.wav` **completed successfully** (`Done`), status `closed`.
- The QEMU WAV contained real samples after offset 0x30, beginning `ee02 ee02 db05 db05...`.
- `aplay -D hw:0,0` **hung** in the guest and could not be reaped by `timeout`.
- With the static PipeWire sink using `hw:0,0`, `aplay -D pipewire` hung. The sink existed and was default, but no PCM reached QEMU.

**Conclusion:** the kernel, HDA codec, mixer and `plughw` path work. The static PipeWire sink's raw `hw:0,0` access is the failure point. The current ISO changes that sink to `plughw:0,0` and adds the mixer unmute at session start, but the change has not been tested.

### 4.4 Current probe behavior

`tests/desktop_audio_test.py` now:

- Boots the ISO with `hda-output` and WAV capture.
- Installs the requested desktop (`i3` or `xfce`) from `--repo`.
- Creates/autologins `tester`.
- Checks `Xorg`, session processes and a non-black screenshot.
- Checks `/proc/asound/cards`, `aplay -l`, `pipewire`/`wireplumber`/`pipewire-pulse`, `wpctl status`, `pw-top`, `pactl list short sinks`.
- Creates a stereo 48 kHz 440 Hz WAV.
- Runs `aplay -D pipewire /tmp/tone.wav` in the background as `tester`, writes its exit code to `/tmp/aplay-pipewire.rc`, polls for up to 20 seconds, and prints `PIPEWIRE_APLAY_RC=<code>` or `PIPEWIRE_APLAY_TIMEOUT`.
- Requires `PIPEWIRE_APLAY_RC=0`, then requires the captured WAV to have non-zero frames and peak.
- Fails with `PROBE_FAILURE`/`WAV_FAILURE` and returns non-zero on any missing marker.

Known test-file caveat: `run(..., timeout=90)` is passed to `child.expect`, but pexpect's traceback may display the child's original timeout (1800). The effective wait is the explicit argument; do not change it unless diagnosing a real hang.

---

## 5. Files changed / added in this work

### Modified (tracked)

- `Makefile` — added phony `test-network` and help line.
- `VERSION` — `0.8.4` → `0.8.5`.
- `bin/garb` — `VERSION = "0.8.5"`.
- `config/kernel-hardened.config` — built-in HDA/codec/USB audio and 8139/pcnet NIC drivers.
- `etc/grintion/desktops.d/gnome.conf` — audio packages.
- `etc/grintion/desktops.d/i3.conf` — audio packages, `xorg-xsetroot`, `pavucontrol`.
- `etc/grintion/desktops.d/kde.conf` — audio packages.
- `etc/grintion/desktops.d/lxqt.conf` — audio packages.
- `etc/grintion/desktops.d/sway.conf` — audio packages, `pavucontrol`.
- `etc/grintion/desktops.d/xfce.conf` — audio packages.
- `etc/grintion/version` — `0.8.5`.
- `etc/issue` — `0.8.5`.
- `etc/motd` — `0.8.5`.
- `etc/lightdm/Xsession-grintion` — creates/exports `XDG_RUNTIME_DIR` before `dbus-run-session`.
- `tests/boot_test.py` — `--nic` / `--machine`; q35 for UEFI.
- `tests/test_system_tools.py` — PipeWire hook/profile assertions and kernel audio/NIC assertions.

### New (untracked before handoff commit)

- `build/test-network.sh` — five-NIC matrix runner.
- `docs/VM-GUEST.md` — QEMU/VirtualBox pointer and audio guidance (contains the stale `hda-duplex` example noted above).
- `etc/X11/xinit/xinitrc.d/20-grintion-audio.sh` — session audio startup and mixer unmute.
- `etc/i3/config` — default i3 configuration with i3bar and `xsetroot`.
- `etc/pipewire/pipewire.conf.d/50-grintion-alsa.conf` — static non-udev ALSA sink (`plughw:0,0`).
- `tests/desktop_audio_test.py` — QEMU i3/XFCE audio probe.

### Explicitly not modified for 0.8.5

`README.md`, `docs/DESKTOP-GUI.md`, `docs/INSTALL.md`, `docs/VERIFICATION.md`, `CHANGELOG.md`, `output/RELEASE-NOTES.md` still contain pre-0.8.5 statements (including “GNOME, LXQt, Sway and i3 unverified”). They must be updated only with verified results.

`output/` and `build/work/` are ignored/untracked; do not commit them.

---

## 6. Test environment and repository image

Host: Arch Linux x86_64, KVM available, non-root user `freddyz`.

The probe's local package repository is:

- `build/work/grintion-repo.img` — 1.5 GiB ext4 image containing the desktop/audio packages and a local pacman DB.
- `build/work/repo-all/`, `build/work/localrepo-*` — package caches/directories used to build it.

The probe mounts the ext4 image as `/dev/vda`, serves it over `http://127.0.0.1:8000`, and rewrites `/etc/pacman.conf` in the guest.

If the repo image is missing or a package is corrupt, rebuild the local repo/image with the existing project tooling rather than pulling packages independently. The earlier `alsa-utils-...pkg.tar.zst.sig` problem was fixed by copying the cached signature and rebuilding the image.

---

## 7. Exact next commands

Run from `/home/freddyz/Documents/Grintion-OS`.

### 7.1 Static checks

```sh
./build/check.sh
```

Expected: all tests pass. The last run reported **66 passed**; report the actual count, do not assume it.

### 7.2 Probe the current ISO (the blocking check)

```sh
python3 tests/desktop_audio_test.py \
  --desktop i3 \
  --iso output/grintion-os-x86_64.iso \
  --repo build/work/grintion-repo.img \
  > /tmp/i3-audio.log 2>&1
echo PROBE_RC=$?
```

Success requires all of:

- `i3=RUNNING`, `i3bar=RUNNING`, `XORG_RUNNING`.
- HDA card and device present.
- `wpctl status` shows `* HDA Intel Analog` (or another non-dummy default sink).
- `PIPEWIRE_APLAY_RC=0` (not `PIPEWIRE_APLAY_TIMEOUT`).
- `QEMU_AUDIO frames=<nonzero> peak=<nonzero>`.
- `TAINTED=0`, `OOM_COUNT=0`, `PANIC_COUNT=0`.
- `DESKTOP_AUDIO_DONE` and `PROBE_RC=0`.

Useful failure diagnostics:

```sh
grep -nE 'CMD|PIPEWIRE|WAV|PROBE|HDA|pactl|wpctl|pw-top|ERROR|FAIL' /tmp/i3-audio.log
```

Inside a failed guest (if you add a debug run), inspect:

```sh
cat /proc/asound/cards
cat /proc/asound/card0/pcm0p/sub0/status
cat /proc/asound/card0/pcm0p/sub0/hw_params
cat "$XDG_RUNTIME_DIR/pipewire.log"
cat "$XDG_RUNTIME_DIR/wireplumber.log"
pactl list short sinks
pactl list short sink-inputs
pw-top -b -n 2
dmesg | grep -iE 'hda|snd|azx|audio'
```

### 7.3 If PipeWire still hangs

Try, one at a time, keeping notes:

1. Set `api.alsa.disable-mmap = true` in `etc/pipewire/pipewire.conf.d/50-grintion-alsa.conf` while keeping `plughw:0,0`.
2. Try `api.alsa.period-size = 0` or a larger value (e.g. 2048); the QEMU HDA driver may not accept the current 1024/headroom 0 combination through SPA.
3. Confirm the static sink's `pactl list short sinks` state; if it stays `SUSPENDED` after `aplay`, check whether the node is linked as the default sink and whether `pw-top` shows the ALSA node as a driver.
4. Verify `aplay -D plughw:0,0` still exits 0 as `tester` on the same boot (known to work in the last debug run).
5. Only if all else fails, consider a small udev/eudev service or a custom WirePlumber monitor; do not add systemd/logind casually, and document the architecture change if you do.

Do not claim success from `wpctl status` alone. The sink existed with `hw:0,0` while playback hung.

### 7.4 XFCE probe

After i3/audio passes:

```sh
python3 tests/desktop_audio_test.py \
  --desktop xfce \
  --iso output/grintion-os-x86_64.iso \
  --repo build/work/grintion-repo.img \
  > /tmp/xfce-audio.log 2>&1
echo XFCE_RC=$?
```

Require `xfce4-session`, `xfwm4`, `xfce4-panel`, non-black desktop, `PIPEWIRE_APLAY_RC=0`, nonzero WAV peak, clean kernel.

### 7.5 Final five-NIC matrix

```sh
./build/test-network.sh
echo NETWORK_RC=$?
```

Require `NETWORK_RC=0` and the final line `network adapter matrix passed ...`.

### 7.6 Rebuild (only after source changes are final)

`make iso` is safe but reruns phony prerequisites; direct scripts are faster:

```sh
./build/make-rootfs.sh
./build/build-iso.sh
sha256sum output/grintion-os-x86_64.iso
```

Update `output/BUILD-INFO` / release notes with the final hash only after the build exits 0.

### 7.7 Documentation to update with verified 0.8.5 results

- `README.md`
- `docs/DESKTOP-GUI.md` — i3 now verified; KDE/GNOME/LXQt/Sway still unverified.
- `docs/INSTALL.md` — audio packages/session behavior if relevant.
- `docs/VERIFICATION.md` — i3/audio results, NIC matrix, exact ISO/hash.
- `docs/VM-GUEST.md` — fix `hda-duplex` → `hda-output` for WAV; state audio is verified only if it is.
- `CHANGELOG.md` — new 0.8.5 section, no unsupported claims.
- `output/RELEASE-NOTES.md` — match the final verified state.

### 7.8 Commit/push

Before committing:

```sh
git status --short
git diff --check
git diff
```

Do not stage `ProblemsWhenInstalling.txt`, `output/`, or `build/work/`. Then:

```sh
git add Makefile VERSION bin/garb config/kernel-hardened.config \
  etc/grintion/desktops.d etc/grintion/version etc/issue etc/motd \
  etc/lightdm/Xsession-grintion etc/X11/xinit/xinitrc.d/20-grintion-audio.sh \
  etc/i3/config etc/pipewire/pipewire.conf.d/50-grintion-alsa.conf \
  build/test-network.sh docs/VM-GUEST.md tests/boot_test.py \
  tests/test_system_tools.py tests/desktop_audio_test.py handoff.md
git commit -m "wip: 0.8.5 audio, i3 and NIC support; PipeWire audio pending verification"
git push origin main
```

Only tag/release `v0.8.5` after every check above passes. If the repository/user expects no AI attribution, omit the Codebuff footer; otherwise follow the repository's commit convention.

---

## 8. Status summary

| Item | Status |
|---|---|
| Built-in HDA/USB audio in kernel | **Done** |
| Audio packages in all profiles | **Done** |
| PipeWire/WirePlumber/Pulse session startup | **Done** |
| Static non-udev ALSA sink | **Done, but current `plughw` path unverified** |
| End-to-end PipeWire playback | **Blocked / unverified** |
| i3 session + i3bar | **Verified on an earlier ISO** |
| Five-NIC matrix | **Verified on an earlier ISO; final ISO not rerun** |
| VM pointer documentation | **Done; QEMU audio doc example needs correction** |
| `./build/check.sh` after latest edits | **Passed: 66 tests** |
| XFCE audio probe | **Not run for 0.8.5** |
| README/DESKTOP-GUI/INSTALL/VERIFICATION/CHANGELOG/RELEASE-NOTES | **Not updated for 0.8.5** |
| Commit/push | **Not done for 0.8.5 (handoff commit only)** |
| KDE Plasma / GNOME / LXQt / Sway | **Unverified; image lacks udev/logind** |
| Secure Boot | **Unsupported by design; detection/refusal only** |

---

## 9. Important constraints

- Never claim a desktop, audio path, network model, or stress result that was not actually observed in QEMU on the stated ISO.
- KDE Plasma, GNOME, LXQt and Sway remain unverified. The image has no udev or logind; Wayland input/session management is the blocker. Do not imply otherwise in docs.
- `ProblemsWhenInstalling.txt` stays local and off GitHub.
- Keep `output/` and `build/work/` out of git.
- Prefer project-local tools and existing build scripts; do not add dependencies casually.
- If a command fails, inspect the actual output and fix the cause. Do not weaken probes or skip a failing check to make the handoff look green.

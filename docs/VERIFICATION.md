# Verification

This document records what was actually executed for Grintion-OS 0.8.4 and the
earlier work. It does not claim coverage of hardware or configurations that
were not tested.

**Status: 0.8.4 console and XFCE graphical session verified; KDE Plasma and the
other graphical profiles unverified.** The 0.8.4 ISO was rebuilt on 2026-11-05
and passed `./build/check.sh` (65 tests), the BIOS and UEFI live boot tests, the
BIOS and UEFI install tests, and a graphical XFCE probe with keyboard and
pointer input. KDE Plasma is Wayland-only in the current Arch package set and
the image has no udev or logind; it was not rendered. The 0.8.3 and earlier
results are historical. The last published 0.6.1 baseline commit was `18c6695`.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-10-31 |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM |
| Virtualisation | QEMU with `-accel kvm -cpu host` |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2 GiB / 2 |
| Network | QEMU user networking, `e1000` |
| Console | serial, `root@grintion-live` |
| Kernel | `6.12.114-grintion` |
| shellcheck | Not installed; static lint was skipped |

## 0.8.4 results (2026-11-05)

LightDM/Xorg desktop fixes, the first rendered graphical-session probe, and the
final release rebuild.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 132,268,032 bytes (127 MiB) |
| SHA-256 | `f358b52596bd1b4aea144a281c341d23e3a76125b4027679652e569c62cbf127` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM, KVM |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2 GiB / 2 for boot and install |
| Network | QEMU user networking, `e1000` |
| `BUILD-INFO` commit | `6d041c8` (ISO built from the working tree before the release commit) |
| shellcheck | Not installed; static lint was skipped |

| Check | Result | Notes |
| --- | --- | --- |
| `./build/check.sh` | Pass | 65 pytest cases plus shell syntax, Python compilation, executable bits, host inputs, documentation links and the home-path scan |
| Live boot, BIOS | Pass | `FBCON_OK`, DHCP lease, supervised `network` service, firewall `ct state`, `sudo -n true`, `grintion-doctor` exit 0, and a plain `poweroff` exited QEMU |
| Live boot, UEFI | Pass | Same assertions under OVMF |
| Install test (BIOS) | Pass | ext4 root, UUID `/etc/fstab`, yescrypt password, `sudo` from `wheel`, DHCP, `INSTALLED` marker, reboot and login |
| Install test (UEFI) | Pass | Same install and post-boot assertions under OVMF |
| XFCE render | Pass | LightDM greeter and XFCE desktop at 1280x800; 106,737 and 1,023,950 non-black pixels respectively |
| Keyboard and pointer | Pass | `xinput` showed `grintion-event1` (keyboard), `grintion-event2` and `grintion-event3` (pointers); an absolute QMP pointer event moved the cursor to 299,199 |
| Session stress | Pass | CPU, RAM and file-descriptor stress; `garb install jq` and `garb remove jq`; a missing package returned 1 |
| Kernel/PAM health | Pass | `TAINTED=0`, `OOM_COUNT=0`, `PANIC_COUNT=0`, `PAM_ERROR_COUNT=0` |
| Xorg crash recovery | Partial | After `pkill -9 Xorg`, LightDM/Xorg restarted and the greeter returned; the autologin XFCE session did not resume by itself |
| KDE Plasma | Not verified | The Arch Plasma 6.8 set is Wayland-only and the image has no udev or logind; no Plasma session was rendered |

Desktop findings:

- LightDM's packaged `/etc/lightdm/lightdm.conf` sets an uncommented
  `session-wrapper` that overrode the Grintion drop-in, so the XFCE session
  never received a D-Bus session bus. `grintion-desktop` now rewrites the main
  file as well, and `Xsession-grintion` starts the session under
  `dbus-run-session`.
- The image has no udev, so Xorg started without input devices.
  `grintion-xorg-input` now generates evdev `InputDevice` sections from
  `/proc/bus/input/devices` with `AutoServerLayout`, and the display-manager
  service runs it before starting Xorg. `xf86-input-evdev` is part of the X11
  profiles.
- Plasma 6.8 in the Arch package set no longer ships `startplasma-x11` or an
  X11 session file. The KDE profile was corrected to a Wayland session under
  SDDM; it is not claimed working.

KDE is unverified because Plasma is Wayland-only while the image deliberately
has no udev or logind, which Wayland input needs. GNOME, LXQt, Sway and i3 were
not rendered in this pass.

The XFCE probe and its screenshots are local test artifacts, not release
assets. `output/BUILD-INFO` records the last source commit, not a commit that
contains the uncommitted 0.8.4 tree; rebuilding after the release commit will
change the ISO hash.

---

## 0.8.3 results (rebuilt 2026-11-04)

Security hardening pass and the blank-framebuffer fix. The report's VM profile
(4 GiB RAM, 32 MiB VGA) is the display test configuration.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 132,163,584 bytes (126 MiB) |
| SHA-256 | `dc2d2b3b11241785146485171d49019cec309e1530ba547a54737b50df41d8b4` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, KVM |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 4 GiB / 2 for the display test; 2 GiB / 2 for boot and install |
| Network | QEMU user networking, `e1000` |
| `BUILD-INFO` commit | `e92a69b` (ISO built before the release commit) |
| shellcheck | Not installed; static lint was skipped |

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | 53 pytest cases plus shell syntax, Python compilation, executable bits, host inputs, documentation links and the home-path scan |
| `tests/display_test.py` | Pass | fbcon bound; 1280x800 with 41,920 non-black pixels after writing to `/dev/tty1`; no black screen at 4 GiB / 32 MiB VGA |
| Live boot, BIOS | Pass | `FBCON_OK`; plain `poweroff` exits QEMU |
| Live boot, UEFI | Pass | `FBCON_OK` under OVMF |
| Install test (BIOS) | Pass | stdin passwords, login, ext4 root, UUID `/etc/fstab`, `sudo` from `wheel`, DHCP, `INSTALLED` marker |
| Password hash | Pass | `/etc/shadow` contains `$y$j9T$...` (yescrypt), so the target `chpasswd` path is active |
| LightDM account entry | Pass | `lightdm` is present in both `/etc/passwd` and `/etc/shadow` (locked); `grintion-desktop` repairs passwd accounts that lack a shadow entry |

Artifact checks:

- `output/config-grintion` has `CONFIG_DRM_FBDEV_EMULATION=y`,
  `CONFIG_MODULE_SIG=y`, `CONFIG_MODULE_SIG_ALL=y`, `CONFIG_MODULE_SIG_FORCE=y`,
  `CONFIG_MODULE_SIG_SHA512=y` and `# CONFIG_BINFMT_MISC is not set`.
- A built module ends with `~Module signature appended~`.
- `pam_faillock.so` and `pam_wheel.so` are present in the staged rootfs.
- io_uring is disabled at runtime (`kernel.io_uring_disabled=2`), not compiled
  out: `CONFIG_IO_URING` is only selectable with `CONFIG_EXPERT`, which selects
  `CONFIG_DEBUG_KERNEL` and would break the existing no-debug contract.
- pacman uses `SigLevel = Required DatabaseOptional`. `DatabaseRequired` was
  tried and reverted: both configured mirrors return 404 for `core.db.sig` and
  `extra.db.sig`, so `pacman -Sy` (and therefore every delegated install)
  fails. Package signatures and local-file signatures remain `Required`.

### Graphical desktop status

`grintion-desktop install xfce` completes and leaves LightDM, Xorg and XFCE
installed, with the D-Bus accounts and the supervised `display-manager`
service. The greeter then aborted with `Failed to establish PAM credentials:
Critical error - immediate abort`. The base image's `lightdm` account had no
`/etc/shadow` entry; 0.8.3 now ships a locked entry and `grintion-desktop`
repairs that class of account. No post-fix graphical screenshot was captured,
so this document does **not** claim a working graphical session.

Not repeated for this pass:

- UEFI install test. UEFI boot is covered above; the install path is identical.
- Wi-Fi association.
- A rendered graphical desktop session: installation and display-manager wiring
  were exercised, but the greeter did not draw (see above).
- Secure Boot, LUKS, clean-room builds and release signing remain absent
  (see `docs/ROADMAP.md`).

## 0.8.2 results (2026-11-02)

Second pass over the field report in `ProblemsWhenInstalling.txt`.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 132,081,664 bytes (126 MiB) |
| SHA-256 | `5f6ce3ddc38b14d2d0857b36559be44dc978d4c2bffce06991a0aec1ab15a856` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, KVM |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2 GiB / 2 |
| Network | QEMU user networking, `e1000` |
| shellcheck | Not installed; static lint was skipped |

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | 42 pytest cases plus shell syntax, executable bits, host inputs, documentation links and the home-path scan |
| Live boot, BIOS | Pass | Plain `poweroff` exits QEMU |
| Live boot, UEFI | Pass | Same assertion under OVMF |
| `./build/test-install.sh` (BIOS) | Pass | Install, reboot from disk, login, ext4 root, UUID `/etc/fstab`, `sudo`, DHCP; system reports 0.8.2 |
| `./build/test-install.sh --uefi` | Pass | Same install and post-boot checks under OVMF |
| Desktop regression probe (i3) | Pass | Installed disk: package-style `/etc/profile.d` snippet, streamed `grintion-desktop -y install i3`, D-Bus accounts/socket/log/service, display-manager link, `i3` binary; 147 packages / 152 MiB |
| Full XFCE install via installer | Pass | `grintion-install --desktop xfce` in QEMU: 291 packages / 231 MiB downloaded; `xfce4`, `startxfce4`, `lightdm`, `glib2` and the display-manager service present; D-Bus accounts and `network` group created; no unknown-account warnings in `/var/log/dbus.log` |
| Partial desktop failure probe | Pass | `--desktop bogus-profile` leaves a bootable base system, prints `desktop: bogus-profile (NOT installed; ...)`, warns, and exits 1 |

Findings re-tested on the installed disk:

| Symptom | Before | 0.8.2 |
| --- | --- | --- |
| Login shell | `append_path: command not found` for package profile snippets | A synthetic snippet added `/opt/test/bin` to `PATH`; `perlbin.sh` was present after the i3 install and a real re-login printed no errors |
| D-Bus | `Unknown username`/`Unknown group` on the login prompt, accounts absent | `avahi`, `polkitd`, `colord` and group `network` present after both the i3 and XFCE installs; `/var/log/dbus.log` exists with zero unknown-account warnings; system bus socket present; `dbus` reports `run:` and survives a restart |
| Seeded packages | `glib2` listed installed without `libglib-2.0.so.0`; scriptlets failed | 156 packages seeded; `glib2` absent and pulled into the i3 transaction; no `libglib-2.0.so.0` loader error in the probe |
| Desktop install | Blank screen during the 152 MiB transaction | pacman output streamed line by line; `DESKTOP_RC=0` |

Notes:

- The full XFCE profile was installed through `grintion-install --desktop xfce`
  and verified at the binary, service and account level. No graphical session
  was rendered; the probes run headless over the serial console. The smaller
  i3 probe covers the same path separately.
- The XFCE probe's account check line was mangled by a pexpect echo race; a
  separate boot confirmed the users, group, `run:` state, bus socket and a zero
  `Unknown username`/`Unknown group` count in `/var/log/dbus.log`.
- The XFCE transaction succeeded on its first attempt after the retry change;
  the retry path itself was not triggered.
- `output/BUILD-INFO` records `git_commit=a7f0343` because the tested ISO was
  built from the working tree before the release commit. Rebuild after
  committing if the recorded commit must match the release commit.
- Some upstream `.INSTALL` scriptlets still print arithmetic/systemd errors.
  pacman returned 0, the desktop binaries and services were verified
  separately, and `grintion-desktop` reports the scriptlet error count.
- The install harness now waits for QEMU to power down during cleanup. Before
  that, a successful install could fail teardown with
  `Could not terminate the child`.
- Wi-Fi association was not tested.

## 0.8.1 results (2026-11-01)

Field report: `ProblemsWhenInstalling.txt`. Three defects were reproduced on
the 0.8.0 ISO before being fixed, then re-tested on 0.8.1.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 132,249,600 bytes (127 MiB) |
| SHA-256 | `0dd5002519b82fbcb64e8e096a292e6dcb8493d5fc73934d96e9afb2abf65d8b` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, KVM |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2-3 GiB / 2 |
| Network | QEMU user networking, `e1000` |

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | 37 pytest cases plus shell syntax, executable bits, host inputs, documentation links and the home-path scan |
| Live boot, BIOS | Pass | Stricter shutdown assertion: a plain `poweroff` must exit QEMU |
| Live boot, UEFI | Pass | Same assertion under OVMF |
| `./build/test-install.sh` (BIOS) | Pass | Install, reboot from disk, login, DHCP, sudo |

| Check | 0.8.0 (before) | 0.8.1 (after) |
| --- | --- | --- |
| Live boot, DHCP | `network: starting dhcpcd on eth0 sit0`, `sit0: unsupported interface type`, no IPv4 address at the prompt | `network: starting dhcpcd on eth0`, `eth0 inet 10.0.2.15/24`, `ping -c 2 8.8.8.8` exit 0 |
| `poweroff` from the console | Hung; no `Power down` and QEMU never exited | `reboot: Power down`, QEMU exited cleanly |
| `grintion-desktop install` guard | Printed "installed successfully" regardless of the result | Missing commands abort the install with `installation did not provide: ...` |
| `dbus` service | Not present; no system bus | `dbus` account created, `/var/service/dbus` running, `/run/dbus/system_bus_socket` present |

Notes from the field tests:

- A `pacman -Sy` plus `grintion-desktop install` run that hit a mirror timeout
  failed with `package installation failed (exit 1)` instead of a false success.
- The seeded pacman database lists packages whose files were never copied
  (`dbus` among them). `grintion-desktop` no longer passes `--needed`, so those
  packages and their dependencies are installed for real.
- A real LightDM session was **not** exercised: the full desktop stack is a
  110 MiB download and the mirror dropped it mid-transaction inside QEMU user
  networking. The D-Bus wiring, the account creation and the display-manager
  status reporting were verified with a lightweight profile instead.

## 0.8.0 results (2026-11-01)

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 127 MiB |
| SHA-256 | `0d86610c97a73f20b297cf4049ffcbc392a879a5a3846cd5d92fa880ca429158` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, KVM |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2 GiB / 2 |
| Network | QEMU user networking, `e1000` |
| shellcheck | Not installed; static lint was skipped |

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, host inputs, documentation links, home-path scan, and 33 pytest cases |
| `make test-boot` | Pass | BIOS and UEFI; root shell, kernel release, DHCP lease, supervised `network` service, live marker, conntrack firewall rule, `sudo -n true`, `grintion-doctor` exit 0 |
| `./build/test-install.sh` (BIOS) | Pass | `lsblk` partition discovery, ext4 root, UUID `/etc/fstab`, account creation, Limine deployment, reboot and login |
| `./build/test-install.sh --uefi` | Pass | Same install verification under OVMF, rebooting from the installed disk |

`make test-boot` rebuilds the ISO because the `iso` target is phony; the
artifact above is the final build used by both install tests. The ISO exceeds
GitHub's 100 MB git-file limit, so it is published as a Release asset rather
than committed to the tree.

## Baseline results (commit `18c6695`, ISO `b05e...`)

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, required host commands, documentation links, absolute-path scan, `garb` tests |
| `python3 -m pytest -q tests/test_garb.py` | 8 passed | Signed repository, dependencies, install/remove, tamper detection, bad signature, path traversal, archive checksum, upgrade, pacman/apk translation |
| `make test-boot` | Pass | BIOS and UEFI; root shell, kernel release, DHCP lease, network service, live marker, conntrack firewall rule, `sudo -n true`, `grintion-doctor` |
| `make test-install` (BIOS) | Pass | Unattended install to an 8 GiB qcow2 disk, reboot from disk, login, ext4 root, hostname, UUID `/etc/fstab`, DHCP, `sudo id` as the created user |
| UEFI install | Pass recorded earlier in the 1.0.0 cycle | Not repeated on the `b05e...` wrapper build |

The sudo and doctor checks were added because an earlier image copied the
`sudo` binary without `/usr/lib/sudo/sudoers.so`, so every invocation failed
before PAM ran. The conntrack check exists because an earlier kernel enabled
`CONFIG_NF_TABLES` without `CONFIG_NFT_CT`, so `ct state` rules failed.

## Verified pacman & desktop integration (ISO `ecc2...`)

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, required host commands, documentation links, absolute-path scan, `garb` tests |
| `make iso` | Pass | 129 MiB; pacman, Arch keyring, `/etc/mtab`, and fallback DNS included |
| Live serial boot | Pass | Reached the live root prompt in ~4 seconds |
| `/etc/mtab` symlink | Pass | Points to `/proc/self/mounts`; `CheckSpace` filesystem calculations succeed |
| Fallback DNS | Pass | `/etc/resolv.conf` contains `1.1.1.1` and `8.8.8.8` from `etc/resolv.conf.head` |
| DHCPv4 | Pass | Guest successfully received `10.0.2.15/24` from QEMU DHCP server |
| `garb update` | Pass | Synchronized `core.db` and `extra.db` from Arch mirrors |
| `garb install jq` | Pass | Successfully resolved dependencies (`oniguruma`), downloaded, and installed `jq-1.8.2-1` |
| `jq --version` | Pass | Executed `jq-1.8.2` |
| `pacman -Q jq` | Pass | Reported package `jq 1.8.2-1` |
| `garb remove jq` | Pass | Removed `jq` with `--noconfirm` |
| `grintion-desktop` | Pass | Script deployed to `/usr/bin/grintion-desktop` supporting XFCE, GNOME, KDE, Sway, LXQt, and GPU drivers |

The previous mount point failure was resolved by symlinking `/etc/mtab -> /proc/self/mounts` in `build/make-rootfs.sh`. The non-interactive transaction prompt was addressed by translating `install`, `remove`, and `upgrade` to include `--noconfirm`.

## What was not verified

- Secure Boot, signature verification of the boot chain, or measured boot.
- Disk encryption, LVM, or custom partitioning.
- KDE Plasma, GNOME, LXQt, Sway and i3 rendered sessions; only XFCE was
  rendered in 0.8.4.
- udev-backed Wayland input; the image has no udev or logind.
- Wi-Fi association and roaming.
- ARM64 or non-x86_64 architectures.
- Bare-metal hardware validation (tested in QEMU/KVM).
- An independent security audit.

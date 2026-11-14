# Verification

This document records what was actually executed for Grintion-OS 0.14.2,
0.14.1, 0.14.0, 0.13.1, 0.13.0, 0.12.1, 0.12.0 and the earlier work. It does
not claim coverage of hardware or configurations that were not tested.

## 0.14.2 quiet console and fresh-install packages (2026-11-14)

This patch quiets the installed console and fixes package operations on a fresh
`--desktop none` install. The ISO was rebuilt, but live boot, the installer and
an installed reboot were not rerun for 0.14.2. The new behavior is covered by
the static gate and unit tests with a fake pacman; it has not been observed on a
booted guest in this release.

### Release artifact

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 132,149,248 bytes (126 MiB) |
| SHA-256 | `0010c63726d168c511cacd05772e84f3a26cdbc2589b905468eb111f3a0aca27` |
| `BUILD-INFO` source commit | `cf1f3b0` (0.14.2 release commit) |
| Kernel | `6.12.114-grintion`, SHA-256 `cca0f3a402f7cf281a6841663404751dc35b8254f7d4557dd53f4df114e41e91` |

### Checks

| Check | Result |
| --- | --- |
| `make check` | 197 passed |
| `make iso` | Passed; AppArmor profiles validated with the staged Arch package (`GRINTION_APPARMOR_ROOT`) because no system `apparmor_parser` was installed |
| Installed console boot | Not rerun for 0.14.2 |
| BIOS/UEFI live boot | Not rerun for 0.14.2 |
| Fresh-install package install | Unit tests only; not rerun on a booted install |
| Installer / installed reboot | Not rerun for 0.14.2 |
| Bare-metal hardware | Not tested |

## 0.14.1 NetworkManager desktop results (2026-11-13)

This patch fixes the desktop network backend. The full desktop package
transaction was not rerun; the probe installed only `networkmanager`,
`network-manager-applet` and `polkit` into a live QEMU guest, then exercised
the same `enable_network_manager` path used by `grintion-desktop install`.
An earlier probe showed that runsvdir can take more than three seconds to pick
up the new link; `grintion-desktop network` now polls for supervision instead
of printing a false failure. The release image was rebuilt after that fix.

### Release artifact

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 132,165,632 bytes (126 MiB) |
| SHA-256 | `199728dc07aeb3aa49f6956e9b2351d7c9c7a37ecad133dbb0239c6c0c4256c6` |
| `BUILD-INFO` source commit | `17c6de0` (0.14.1 version changes were uncommitted at build time) |

### Checks

| Check | Result |
| --- | --- |
| `make check` | 191 passed |
| BIOS live boot | Passed under QEMU SeaBIOS; 0.14.1, kernel `6.12.114-grintion`, DHCP, nftables and AppArmor enforce mode |
| UEFI live boot | Passed under QEMU OVMF with the same assertions |
| Desktop profiles | All graphical profiles install `networkmanager`; KDE adds `plasma-nm`, GTK profiles add `network-manager-applet` |
| Repair command | `grintion-desktop network` returned 0 and printed `NetworkManager is running` |
| Runit supervision | `sv status NetworkManager` reported `run: NetworkManager: (pid 1259) 0s`; `/var/service/NetworkManager` existed and `/var/service/network` was removed |
| DHCP | `nmcli` reported `connected (site only)`; `eth0` received `10.0.2.15/24` |
| DNS and internet | `getent hosts example.com` returned addresses, `ping -c 2 8.8.8.8` passed with 0% loss, and `wget http://example.com` returned 0 |
| Installer / installed reboot | Not rerun for 0.14.1 |
| Desktop rendering | Not rerun for KDE, XFCE, LXQt, Sway or i3 |
| Bare-metal hardware | Not tested |

**0.14.0 verification status (2026-11-13):** the hardware-support and resilience
release was built from the 0.14.0 worktree; `BUILD-INFO` records source commit
`e1a66b7` because the release version and documentation changes were still
uncommitted at build time. The final ISO boots under QEMU SeaBIOS and OVMF UEFI
and reaches the live root shell as Grintion-OS 0.14.0 with kernel
`6.12.114-grintion`, DHCP, nftables, AppArmor enforce mode, sudo, the
framebuffer console and `grintion-doctor` exit 0. The boot test does not cover
the installer or an installed-system reboot, and no bare-metal or 32-bit
hardware run was made.

## 0.14.0 release results (2026-11-13)

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 132,139,008 bytes (126 MiB) |
| SHA-256 | `e8ec502424a52636848e731c0b5b899bbbf2a1e69f88b5dd11de078cb4bc0428` |
| `BUILD-INFO` source commit | `e1a66b7` (0.14.0 release changes were uncommitted at build time) |

| Check | Result |
| --- | --- |
| `make check` | 189 passed |
| BIOS live boot | Passed under QEMU SeaBIOS; 0.14.0, kernel `6.12.114-grintion`, DHCP, nftables and AppArmor enforce mode |
| UEFI live boot | Passed under QEMU OVMF with the same assertions |
| Live service/session checks | Root shell, network and AppArmor services running, `sudo -n true`, framebuffer console and `grintion-doctor` exit 0 |
| Architecture policy | Covered by `grintion-doctor` and the phase-11 unit tests; no 32-bit-only hardware run |
| auditd | Covered by `grintion-doctor` (userspace and running daemon); fault injection was not performed |
| Driver/firmware selection | Modalias resolution, firmware lookup and package planning covered by unit tests; no physical-device firmware install was performed |
| Installer / installed reboot | Not rerun for 0.14.0 |
| Bare-metal hardware | Not tested |

**0.13.1 verification status (2026-11-12):** the security and stability patch
was built from source release commit `4900b8d`. `make check` passes with 181
tests. The final ISO boots under QEMU SeaBIOS and OVMF UEFI and reaches the live
root shell as Grintion-OS 0.13.1 with kernel `6.12.114-grintion`, DHCP,
nftables, AppArmor enforce mode, sudo, the framebuffer console and
`grintion-doctor` exit 0. These are firmware/VM tests, not a bare-metal run.
The installer and installed-system reboot paths were not rerun for this patch.

## 0.13.1 security and stability results (2026-11-12)

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 164,843,520 bytes (158 MiB) |
| SHA-256 | `0fcc5c57947fc77198fa0b0c2f91f7a3e77bae41676b0539d876f186c3d62edb` |
| `BUILD-INFO` source commit | `4900b8d` |

| Check | Result |
| --- | --- |
| `make check` | 181 passed |
| BIOS live boot | Passed under QEMU SeaBIOS; 0.13.1, kernel `6.12.114-grintion`, DHCP, nftables and AppArmor enforce mode |
| UEFI live boot | Passed under QEMU OVMF with the same assertions |
| Live service/session checks | `sv` network and AppArmor services running, root shell, `sudo -n true`, framebuffer console and `grintion-doctor` exit 0 |
| `garb` bounded inputs | Archive member/size/metadata limits, duplicate and setuid rejection, streamed size/hash verification, index age/replay/cache checks covered by tests |
| Security profile rollback | Fake-tool tests verify apply, post-apply verification, and profile/firewall rollback on failure |
| Integrity privilege detection | Baseline detects a newly added setuid bit with unchanged file content |
| Boot-health auto-revert | Bounded counter parsing, atomic state replacement and validated Limine edit covered by tests |
| Installer / installed reboot | Not rerun for 0.13.1 |
| Bare-metal hardware | Not tested |

**0.13.0 verification status (2026-11-12):** the minor release was rebuilt from
release commit `63e48d3`. `make check` passes with 176 tests, the final ISO
boots under BIOS and UEFI, and both installer paths complete, reboot and reach
a verified installed system. The final image records `libxss` as the owner of
`/usr/lib/libXss.so` and stages the pointer-sync helper. HWE/DKMS boot and a
rendered XFCE/KDE pointer session were not exercised.

## 0.13.0 kernel, pointer and package results (2026-11-12)

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 164,831,232 bytes (157 MiB) |
| SHA-256 | `83a2faa6015a61b7ea107460bfdc9f6a45406f92fb1ad0d7d43fc73b60c32511` |
| `BUILD-INFO` commit | `63e48d3` (built from the release commit) |

| Check | Result |
| --- | --- |
| `make check` | 176 passed |
| BIOS live boot | Passed on the final ISO; 0.13.0, kernel `6.12.114-grintion`, DHCP, nftables and AppArmor enforce mode |
| UEFI live boot | Passed on the final ISO with the same assertions |
| BIOS install / installed boot | Passed; installed login, installed marker, udev/seatd sockets, DHCP and sudo verified |
| UEFI install / installed boot | Passed with the same installed-system assertions |
| Firefox package ownership | Final staged pacman DB has `libxss-1.2.5-1` owning `/usr/lib/libXss.so`, `.so.1` and `.so.1.0.0`; the reported `exists in filesystem` conflict is removed |
| Pointer synchronization | `grintion-pointer-sync` is executable in the image and called by the display-manager service before Xorg/KWin; XFCE, KDE, LXQt and i3 profiles include `xf86-input-libinput` |
| Kernel flavors | The installer exposes `lts`, `hwe` and `dkms`; a mocked HWE install test verifies package staging, initramfs build and a separate Limine entry |
| HWE/DKMS boot | Not verified; no current-kernel package install was booted in this run |
| Rendered VM pointer | Not verified; tablet detection and the evdev fallback guard are covered by unit tests only |

A full Firefox download and installation was not run for this release. The
package ownership check verifies the specific colliding file that caused the
reported failure; it is not a substitute for an end-to-end browser install.

## 0.12.1 install and package fixes (2026-11-12)

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 164,825,088 bytes (158 MiB) |
| SHA-256 | `6123671524e5499678ee8d02469705259344e9522f7ee6316379a43452971163` |
| `BUILD-INFO` commit | `cc3480a` (ISO built from the 0.12.1 working tree before the release commit) |

| Check | Result |
| --- | --- |
| `make check` | 171 passed |
| Pacman repositories | `core` and `extra` point at the `2026/11/01` Arch Linux Archive snapshot; rolling mirrors are not configured |
| Pacman download timeout | `DisableDownloadTimeout` is active in `/etc/pacman.conf`; `grintion-desktop` also passes `--disable-download-timeout` |
| KDE resolution | `pacman -Sp plasma-meta konsole dolphin sddm xorg-server` resolved successfully; `openssl 3.6.5-1` selected instead of OpenSSL 4; no `libcrypto.so=3-64` conflict |
| Base accounts | 28 groups generated, including `colord` and `spice-webdavd`; rootfs build rejects any udev `GROUP=` that is absent |
| Live KDE guard | Passed in a 4 GiB live VM; installation stops before downloading with the 4.8 GiB RAM-overlay explanation and the `grintion-install --desktop kde` path |
| BIOS live boot | Passed; no `Unknown group`, `Failed to resolve group`, `ntpd: bad address`, or default interface-naming line on the console |
| UEFI live boot | Passed; same clean-console assertion |
| Installer / installed boot | Passed on the final ISO; installed login prompt is clean, `udev` and `seatd` are running, DHCP and sudo work |
| KDE target install | Passed; installer summary says `desktop: kde (ready on boot)`; installed disk has `sddm`, `plasmashell`, `plasma-meta 6.8-1`, `openssl 3.6.5-1`, `seatd` running, the display-manager link and SDDM Wayland wrapper, and clean udev/timesync logs |

A graphical KDE session was not captured for 0.12.1. The target-disk package
install and installed-system boot are verified; the earlier 0.11.0 render is
the visual evidence for the session itself.

## 0.12.0 security hardening results (2026-11-11)

Targeted security release. The kernel and ISO were rebuilt from this tree; this
release did not re-run the desktop probes.

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 164,823,040 bytes (157 MiB) |
| SHA-256 | `9c5ec96646002f1f2e550524d26b1951901d6841ee54eba66ddee796b63005c9` |
| `BUILD-INFO` commit | `3fe543c` (built before the release commit) |

| Check | Result |
| --- | --- |
| `make check` | 165 passed |
| Kernel | `6.12.114-grintion`; `CONFIG_SECURITY_APPARMOR=y`, `CONFIG_SECURITYFS=y` |
| Profile parse | `apparmor_parser` 4.1.8 accepted all three profiles; the rootfs build fails closed on syntax errors |
| BIOS live boot | Passed; AppArmor `enabled=Y`; all three profiles loaded `(enforce)`; `apparmor` service running; `grintion-doctor` rc 0 |
| UEFI live boot | Passed; same AppArmor assertions |

X11 configuration was validated statically. A graphical session was not
re-rendered for this release, so no new desktop visual claim is made.

Historical tables record `shellcheck | Not installed; static lint was skipped`
because the gate used to skip lint when the tool was absent. Since 0.10.1,
`build/check.sh` fails closed when shellcheck is missing.

## Evidence artifacts

- Every `make check` writes `output/junit.xml`; the static CI job uploads it.
- The self-hosted KVM job uploads QEMU serial logs and `output/junit.xml` from
  `make test-boot`, `make test-install` and `make test-install-uefi`.
- The bare-metal runs `BM-TEST-001` through `BM-TEST-012` in
  [HARDWARE-LAB.md](HARDWARE-LAB.md) are operator records. Their raw serial and
  JUnit logs are **not** in this repository and have not been attached to a
  release; treat those claims as unverified by CI until the logs are assets.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-11-12 for 0.13.0; 2026-11-09 for the static gate and 0.10.1 follow-up; older QEMU rows are from 0.9.0/0.10.0 |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM |
| Virtualisation | QEMU with `-accel kvm -cpu host` |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd`; both were rerun for the 0.10.1 follow-up |
| Guest RAM / vCPU | 3.25 GiB / 2 for the 0.10.1 XFCE probe; 4 GiB / 4 for older desktop probes; 2 GiB / 2 for boot and network tests |
| Network | QEMU user networking; `e1000` for the desktop probes, plus the five-NIC matrix |
| Console | serial, `root@grintion-live` |
| Kernel | `6.12.114-grintion` |
| shellcheck | 0.11.0; required by `build/check.sh` (historical rows below record skipped lint) |

## 0.11.0 desktop results (2026-11-11)

Targeted desktop follow-up. KDE and LXQt were verified on installed QEMU/KVM
images that already contained the fixes being productized. Sway was verified
twice: first on an installed image with the updated `/usr/bin/grintion-desktop`
and `sway.conf`, then end-to-end from a fresh `--desktop sway` install of the
rebuilt 0.11.0 ISO. BIOS and UEFI live boot pass on the rebuilt ISO
(`build/test-boot.sh`).

| Artifact | Value |
| --- | --- |
| ISO | `output/grintion-os-x86_64.iso`, 163,862,528 bytes (156 MiB) |
| SHA-256 | `fcdbc0d9a1ac7f47540ecbffa36277fc20916a865e90048acc7ba08ee4335194` |
| `BUILD-INFO` commit | `a27cb7b` (built from the release commit) |

| Desktop | Session | Result | Evidence |
| --- | --- | --- | --- |
| KDE Plasma 6.8.2 | SDDM / Wayland | Rendered | `build/work/de-verify/kde-fixes/kde-fixed.png`, 1280x800, 1,023,917 non-black; `kwin_wayland`, `plasmashell`, `ksmserver` running |
| LXQt | LightDM / X11 | Rendered | `build/work/de-verify/lxqt-lightdm/lxqt-lightdm.png`, 1280x800, 1,022,249 non-black; `lxqt-session`, `openbox`, `lxqt-panel`, `pcmanfm-qt` running |
| Sway 1.12 | Direct Wayland | Rendered | `build/work/de-verify/fresh-sway/fresh-sway.png`, 1280x800, 1,023,950 non-black; fresh 0.11.0 `--desktop sway` install; `sway`, `swaybg`, `swaybar` running; `/usr/sbin/grintion-desktop` absent; `~/.config/sway/config` includes `/etc/sway/config.d/*`; `libseat.so.1` present; `pipewire-0` socket created |
| GNOME 51 | — | Refused | `grintion-desktop install gnome` stops before downloading: `gnome-session` needs `org.freedesktop.systemd1` |

Sway needed `WLR_RENDERER=pixman WLR_RENDERER_ALLOW_SOFTWARE=1` under QEMU's
emulated GPU. `libseat` comes from Arch's `seatd` package, which replaces the
former `libseat` package; listing `seatd` in the profile forces pacman to
complete the seeded package install. The fresh install confirmed the image
build change: only `/usr/bin` carries the installer, so nothing shadows an
update. The earlier installed-image run did have a stale
`/usr/sbin/grintion-desktop`; invoking `/usr/bin` explicitly created the user
config there. The PipeWire/WirePlumber stack started with a `pipewire-0`
socket. No playback was attempted in Sway because the probe has no emulated
sound device.

`make check`: **162 passed**, including shellcheck, Python compilation,
tracked-binary provenance, documentation links and the home-path scan.

## 0.10.1 follow-up results (2026-11-09)

These runs use the rebuilt working-tree ISO. They verify the audio and desktop
changes in this tree; they are not a release claim.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 163,983,360 bytes (156 MiB) |
| SHA-256 | `f0b0550933f7b3aa9635609a3fce2267d924e2053cc2a9d0d7a5ab548e8787b8` |
| Kernel | `6.12.114-grintion` |
| `BUILD-INFO` commit | `9171355` (ISO built from the working tree before a commit) |
| Guest RAM / vCPU | 3.25 GiB / 2 for the XFCE probe; 2 GiB / 2 for live boot |

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | 154 pytest cases plus shell syntax, Python compilation, executable bits, documentation links, provenance and the home-path scan |
| Live boot, BIOS | Pass | `FBCON_OK`, DHCP `10.0.2.15`, supervised `network`, `FIREWALL_OK`, `SUDO_OK`, `DOCTOR_RC=0`, and a plain `poweroff` exited QEMU |
| Live boot, UEFI | Pass | Same assertions under OVMF |
| XFCE install | Pass | `grintion-desktop -y --no-drivers install xfce`; Xorg, `xfce4-session`, `xfwm4` and `xfce4-panel` ran and the framebuffer was non-black |
| Audio sink | Pass | WirePlumber enumerated `alsa_output.pci-0000_00_04.0.analog-stereo`; no hard-coded `plughw:0,0` sink |
| PipeWire playback | Pass | `pw-play` of a stereo 48 kHz 440 Hz tone returned 0 |
| Direct ALSA diagnostic | Pass | `aplay -D plughw:0,0` returned 0 after `pactl suspend-sink`; without suspending, PipeWire owns the PCM and `EBUSY` is expected |
| QEMU audio capture | Pass | 105,730 frames, peak 11999 (the generated amplitude) |
| Kernel health | Pass | `TAINTED=0`, `OOM_COUNT=0`, `PANIC_COUNT=0` |
| KDE Plasma, GNOME, Sway | Not verified | Profiles are defined, but the image has no logind-compatible session manager; no SDDM/GDM/Plasma/GNOME/Sway session was rendered |
| LXQt | Not verified | The profile now uses the verified LightDM/X11 path; no LXQt session was rendered in this pass |

The runtime probe's local package fixture predates the firmware split and lacks
some GPU packages. It drops `linux-firmware` and `wireless-regdb` only when the
fixture does not contain them; the unit tests cover the shipped profile package
names. The probe also uses `--no-drivers`, so it does not exercise firmware or
GPU installation from Arch mirrors.

## 0.9.0 results (2026-11-06)

Audio support, a verified i3 session and the five-NIC matrix, on the release
rebuild.

| Item | Value |
| --- | --- |
| Artifact | `output/grintion-os-x86_64.iso` |
| Size | 133,113,856 bytes (127 MiB) |
| SHA-256 | `b46f6851a56cf866da0780417053c47ab9b5b2f59b7d70cab93a4bb85bca737d` |
| Kernel | `6.12.114-grintion` |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM, KVM |
| Firmware | SeaBIOS. UEFI was not rerun for this release. |
| Guest RAM / vCPU | 4 GiB / 4 for the desktop probes; 2 GiB / 2 for the network matrix |
| Network | QEMU user networking |
| `BUILD-INFO` commit | `4910c66` (ISO built from the working tree before the release commit) |
| shellcheck | Not installed; static lint was skipped |

| Check | Result | Notes |
| --- | --- | --- |
| `./build/check.sh` | Pass | 66 pytest cases plus shell syntax, Python compilation, executable bits, host inputs, documentation links and the home-path scan |
| i3 probe | Pass | Xorg, `i3` and `i3bar` running after LightDM autologin; 1280x800 frame with 999,348 non-black pixels |
| XFCE probe | Pass | `xfce4-session`, `xfwm4` and `xfce4-panel` running; 1280x800 frame with 1,023,950 non-black pixels |
| HDA sound card | Pass | `/proc/asound/cards` shows `HDA Intel`; `aplay -l` shows `Generic Analog`; PipeWire 1.6.10 with `pipewire-alsa`, `pipewire-pulse` and WirePlumber 0.5.18 |
| Default sink | Pass | `wpctl status` and `pactl` show `HDA Intel Analog` (`alsa_output.hw0`) selected |
| Native PipeWire playback | Pass | `pw-play` of a stereo 48 kHz 440 Hz tone returned 0 on both sessions |
| Direct ALSA playback | Pass | `aplay -D plughw:0,0` returned 0 on both sessions |
| QEMU audio capture | Pass | WAV peak 11999 (the generated amplitude) on i3 (87,055 frames) and XFCE (87,106 frames) |
| Kernel health | Pass | `TAINTED=0`, `OOM_COUNT=0`, `PANIC_COUNT=0` on both probes |
| Network matrix | Pass | e1000/pc, e1000e/q35, virtio-net-pci/pc, rtl8139/pc and pcnet/pc; all bound a driver, acquired DHCP `10.0.2.15` and passed the live-session, firewall and `grintion-doctor` checks (`NETWORK_RC=0`) |
| KDE Plasma, GNOME, LXQt, Sway | Not verified | No udev/logind; Plasma is Wayland-only |
| UEFI boot and installer | Not repeated | The 0.9.0 source changes are desktop audio, i3, NIC configuration and the version bump; BIOS live boot is covered by the matrix |

Findings:

- The QEMU probe originally used `hda-duplex` with `-audiodev wav`; the WAV
  backend is playback-only, so QEMU logged `Can not open 'adc'` and the guest's
  playback path was unusable. The probe and `docs/VM-GUEST.md` now use
  `hda-output` for capture.
- The static sink moved from `hw:0,0` to `plughw:0,0`. Raw `hw` access left
  PipeWire playback and `aplay` hung; the plug layer delivers samples and
  completes direct ALSA playback.
- `aplay -D pipewire` still does not return on PipeWire 1.6.10 after the file
  has played. This is the upstream ALSA-plugin drain lockup fixed in 1.6.11
  ("Avoid going into XRUN when draining", issue #5544); 1.6.10 is the current
  Arch stable version and 1.6.11 was in `extra-testing` at release time. The
  release probe therefore uses `pw-play` for PipeWire playback and
  `aplay -D plughw:0,0` for direct ALSA.

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

## 0.10.0 results (2026-11-07, historical)

> These are the 0.10.0 records. The bare-metal rows are operator claims; their
> raw logs are not in this repository (see [Evidence artifacts](#evidence-artifacts)).

Grintion-OS 0.10.0 executed and verified all 10 phases covering security hardening,
LUKS2 encryption, user-owned Secure Boot, package generations, disaster recovery,
and physical hardware test lab validation:

| Test Area | Result | Notes |
| --- | --- | --- |
| `./build/check.sh` | Pass | 137 unit and integration tests passing; zero failures |
| Package manager (`tests/test_garb.py`) | Pass | Transactions, locks, journal, fsck, generations, rollback, deltas |
| Installer & disk (`tests/test_system_tools.py`) | Pass | Whole disk, custom partitioning, LUKS2 root/home, encrypted swap |
| Boot & UKI (`tests/test_phase6_boot_security.py`) | Pass | MOK enrollment, UKI assembly, TPM 2.0 PCR attestation, TPM LUKS sealing |
| Hardware & Wi-Fi (`tests/test_phase5_hardware_config.py`) | Pass | Roaming, enterprise 802.1X, MAC randomization, `grintion-doctor --fix` |
| Security hardening (`tests/test_phase8_security_hardening.py`) | Pass | AppArmor profiles, sandbox, auditd logging, file integrity (`grintion-integrity`) |
| Bare-metal fleet (`tests/test_phase9_validation.py`) | Pass | Verified against test lab matrix (`docs/HARDWARE-LAB.md`) |
| Performance tuning (`tests/test_phase10_performance_polish.py`) | Pass | ZRAM service, boot optimizations, tour, and completions |

## What is explicitly not claimed or out of scope

The following items are intentionally outside the scope of Grintion-OS 0.10.0:
- Pre-enrolled Microsoft 3rd-Party UEFI CA shim (Secure Boot uses user-enrolled MOK keys).
- ARM64 or non-x86_64 CPU architectures (build system is x86_64-specific).
- An independent, third-party commercial security audit.
- Bundled desktop environments on the minimal base ISO (available on-demand via `grintion-desktop`).

# Desktop and GUI Support in Grintion-OS

Grintion-OS is designed with a clean separation of concerns:
- **Base Media:** Boots into a lightweight, fast, and secure console prompt for pre-installation, partitioning, system maintenance, and initial setup.
- **GUI & Desktop Environments:** Supported for installation. Users can pre-install their preferred graphical desktop during initial installation (`grintion-install --desktop <env>`), or install and configure desktop environments and GPU drivers anytime using `grintion-desktop`.

---

## Verification status (0.11.0 rendering; 0.13.0 install path)

The rendered-session evidence below is from 0.11.0. Grintion-OS 0.13.0 did not
re-render a graphical session; it carries the 0.12.1 KDE target-disk install
and adds VM pointer synchronization (see [VERIFICATION.md](VERIFICATION.md)).

Verified: `grintion-desktop install xfce` and `... install i3` complete,
LightDM starts, and both sessions render under Xorg in QEMU/KVM. The probes
captured non-black desktops at 1280x800 (1,023,950 non-black pixels for XFCE,
999,348 for i3), with `xfce4-session`/`xfwm4`/`xfce4-panel` and
`i3`/`i3bar` running. i3 no longer shows its first-run configuration wizard.

Audio is verified end-to-end on XFCE. The kernel provides HDA, the HDA codec
parsers and USB audio built in; the profile installs PipeWire, WirePlumber,
`pipewire-pulse`, ALSA tools, `linux-firmware`, `wireless-regdb` and
`sof-firmware`. The shared `grintion-audio` helper is called from the X11
session hook and from `/etc/xdg/autostart/grintion-audio.desktop`, so GNOME,
KDE, LXQt and XFCE sessions all start the same stack without a systemd user
manager. It unmutes every card in `/proc/asound/card*`, not just card 0.

The hard-coded `plughw:0,0` PipeWire sink was removed. That sink selected the
wrong PCM on machines where HDMI is card 0 or the analog codec is card 1, and
it could leave a real laptop silent. WirePlumber now enumerates the actual
sink through udev; the XFCE QEMU probe showed
`alsa_output.pci-0000_00_04.0.analog-stereo`, `pw-play` returned 0, and QEMU
captured the 440 Hz tone (105,730 frames, peak 11999). Direct `aplay` while
PipeWire owns the PCM correctly returns `EBUSY`; suspend the PipeWire sink
before using direct ALSA as a diagnostic.

PipeWire 1.6.11 is the current Arch stable version installed by the desktop
profiles. It includes the upstream fix for the 1.6.10 `pipewire-alsa` drain
lockup; on an older 1.6.10 image, use `pw-play` or upgrade the package.

| Desktop | Session | Result | Evidence |
| --- | --- | --- | --- |
| XFCE | LightDM / X11 | Rendered | 1,023,950 non-black pixels; audio captured |
| i3 | LightDM / X11 | Rendered | 999,348 non-black pixels; audio captured |
| KDE Plasma 6.8 | SDDM / Wayland | Rendered | 1,023,917 non-black pixels; `kwin_wayland`, `plasmashell`, `ksmserver` |
| LXQt | LightDM / X11 | Rendered | 1,022,249 non-black pixels; `lxqt-session`, `openbox`, `lxqt-panel`, `pcmanfm-qt` |
| Sway 1.12 | Direct Wayland | Rendered | 1,023,950 non-black pixels; `sway`, `swaybg`, `swaybar`; `libseat.so.1` |
| GNOME 51 | — | Refused | `gnome-session` requires `org.freedesktop.systemd1` |

KDE and LXQt were rendered on installed QEMU/KVM images. Sway was also
verified from a fresh 0.11.0 ISO install (`--desktop sway`): the installed
disk booted, the user config existed, and the session rendered at 1,023,950
non-black pixels.

### Phase 4 Desktop, Wayland, and Display Manager Matrix

`seatd` is supervised by runit and provides `/run/seatd.sock`. The `seat`
group is shipped in `/etc/group`; installing a profile whose `DISPLAY_SERVER`
contains `wayland` enables `seatd` and adds human users to that group.
`grintion-session --type wayland --desktop sway -- COMMAND` creates a private
`XDG_RUNTIME_DIR`, exports `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP` and
`SEATD_SOCK`, starts a session bus with `dbus-run-session`, and then execs the
command. XDG portal packages are part of each profile.

Display managers (`lightdm`, `sddm`, `gdm`, and `greetd`) are supervised by
`/etc/sv/display-manager/run` and standalone `/etc/sv/greetd/run`. Dedicated PAM
stacks are provided in `/etc/pam.d/` (`lightdm`, `sddm`, `sddm-greeter`,
`sddm-autologin`, `gdm-password`, `gdm-autologin`, `greetd`), and service accounts
are automatically provisioned by `grintion-desktop`. D-Bus session bus startup
in X11 sessions provides automatic fallback to `dbus-daemon --session --fork`
when `dbus-launch` is not installed, eliminating "No session bus running" errors.

KDE Plasma, LXQt and Sway render in QEMU/KVM. Plasma 6.8 is Wayland-only
(`plasma-workspace` ships `startplasma-wayland` and `plasma.desktop`; there is
no `startplasma-x11` or X11 session file). SDDM launches it through
`/etc/sddm/wayland-session-grintion`, which creates the private
`XDG_RUNTIME_DIR` that `pam_systemd` would normally provide; human accounts
are in `video`, `audio`, `input`, `render` and `seat` so KWin can open
`/dev/dri/card0`. LXQt ships no upstream session entry, so the tracked
`lxqt.desktop` is installed and LightDM launches `startlxqt`. Sway obtains
DRM/input access through `seatd` and the `libseat` library shipped by that
package, reads `~/.config/sway/config` with the Grintion drop-in, and starts
`swaybg` plus `swaybar`. GNOME remains unsupported: `gnome-session` 51 starts
its units through `org.freedesktop.systemd1` and exits before drawing, so
`grintion-desktop install gnome` refuses before downloading anything.

If the greeter does not appear:

```sh
getent shadow lightdm
tail -n 40 /var/log/lightdm/lightdm.log
tail -n 40 /var/log/lightdm/seat0-greeter.log
tail -n 40 /var/log/display-manager.log
```

---

## 1. Quick Start

### Option A: Pre-install during disk installation

When running `grintion-install`:

```sh
# Unattended or scripted
grintion-install --disk /dev/vda --user myuser --desktop xfce

# Interactive: the installer will prompt you to select a desktop
grintion-install --disk /dev/vda
```

### Option B: Install on a running or live system

```sh
# 1. Update package databases
garb update

# 2. Install your chosen desktop environment
grintion-desktop install xfce       # Fast, lightweight traditional desktop (Recommended)
grintion-desktop install gnome      # Modern, gesture-rich Wayland desktop
grintion-desktop install kde        # KDE Plasma - customizable and feature-rich
grintion-desktop install sway       # Modern tiling Wayland compositor
grintion-desktop install lxqt       # Ultra-lightweight Qt desktop
grintion-desktop install i3         # Classic X11 tiling window manager
```

---

## 2. The `grintion-desktop` Tool

`grintion-desktop` is Grintion-OS's built-in tool for managing desktop environments, display managers, and hardware acceleration drivers.

### Commands

| Command | Description |
| --- | --- |
| `grintion-desktop list [--json]` | Display available desktop profiles; `--json` emits machine-readable profile data. |
| `grintion-desktop install <name>` | Install desktop packages, install recommended GPU drivers, and configure the display manager. |
| `grintion-desktop uninstall <name>` | Remove the profile's packages and display-manager service. |
| `grintion-desktop drivers` | Automatically detect GPU hardware and install packages from `/etc/grintion/drivers.conf`. |
| `grintion-desktop status` | Show current display server, installed desktops, and active display manager services. |

### Options

- `--dm, --display-manager <sddm|lightdm|gdm>`: Override the default display manager.
- `--root <path>`: Install into a specific root filesystem (e.g. `/mnt` for disk installation).
- `--no-drivers`: Skip automatic GPU driver detection and installation.
- `-y, --noconfirm`: Run non-interactively without prompting for confirmation.

### Profiles

Desktop definitions live in `/etc/grintion/desktops.d/<name>.conf`:

```sh
NAME=xfce
DESCRIPTION="XFCE 4 (X11)"
PACKAGES="xorg-server ... xfce4 xfce4-goodies pavucontrol"
DM="lightdm lightdm-gtk-greeter"
DM_BIN="/usr/bin/lightdm"
XINITRC="exec startxfce4"
DISPLAY_SERVER=x11
```

The CLI discovers every `*.conf` in that directory, so a local profile can be
added without editing the script. `list --json` returns the same fields for
provisioning tools. `uninstall <name>` removes the profile's packages, the
`/var/service/display-manager` link and `/etc/grintion/display-manager`;
`--root <path>` operates on a mounted target instead of the running system.

Wayland-only profiles leave `XINITRC` empty. Sway also leaves `DM` empty and is
started with `sway`; KDE keeps SDDM, which starts the Wayland session.
`grintion-desktop` never writes `exec sway` into `.xinitrc`.

### GPU driver matrix

`/etc/grintion/drivers.conf` is a tab-separated list of an extended regular
expression and the packages to install; the first match wins and `default` is
the fallback:

```text
Intel	xf86-video-intel vulkan-intel
NVIDIA	xf86-video-nouveau
default	xf86-video-vesa xf86-video-fbdev
```

---

## 3. Supported Desktop Environments

### XFCE 4 (`xfce`)
- **Display Server:** X11
- **Default Display Manager:** LightDM
- **Characteristics:** Fast, lightweight, mature, low memory footprint.
- **Packages:** `xfce4`, `xfce4-goodies`, `pavucontrol`, `lightdm`, `lightdm-gtk-greeter`
- **Verification:** rendered with working audio in 0.9.0; see the status above.

### GNOME (`gnome`)
- **Display Server:** Wayland (with X11 fallback)
- **Default Display Manager:** GDM
- **Characteristics:** Polished modern design, comprehensive application ecosystem, smooth touch gestures.
- **Packages:** `gnome`, `gnome-terminal`, `nautilus`, `gdm`
- **Verification:** not supported. `gnome-session` 51 requires the systemd user session manager; the installer refuses this profile before downloading packages.

### KDE Plasma (`kde` / `plasma`)
- **Display Server:** Wayland (the 6.8 Arch package set no longer ships an X11 session)
- **Default Display Manager:** SDDM
- **Characteristics:** Highly customizable, modern Qt design, widget system, powerful settings.
- **Packages:** `plasma-meta`, `konsole`, `dolphin`, `sddm`
- **Verification:** rendered on Wayland through SDDM in 0.11.0; see the status above.

### LXQt (`lxqt`)
- **Display Server:** X11
- **Default Display Manager:** LightDM
- **Characteristics:** Extremely low resource consumption, clean Qt interface.
- **Packages:** `lxqt`, `pavucontrol-qt`, `qterminal`, `pcmanfm-qt`, `lightdm`, `lightdm-gtk-greeter`
- **Verification:** rendered through LightDM/X11 in 0.11.0; see the status above.

### Sway (`sway`)
- **Display Server:** Wayland native
- **Default Display Manager:** Direct login or LightDM
- **Characteristics:** Ultra-fast, keyboard-driven i3-compatible Wayland tiling compositor.
- **Packages:** `sway`, `swaybg`, `swaylock`, `swayidle`, `waybar`, `foot`, `wofi`, `polkit`, `seatd`
- **Verification:** rendered with `swaybg` and `swaybar` in QEMU/KVM in 0.11.0; see the status above.

### i3 (`i3`)
- **Display Server:** X11
- **Default Display Manager:** LightDM
- **Characteristics:** Classic, rock-solid keyboard-driven tiling window manager.
- **Packages:** `i3-wm`, `i3status`, `i3lock`, `dmenu`, `rxvt-unicode`, `pavucontrol`
- **Verification:** rendered with i3bar and working audio in 0.9.0; see the status above.

---

## 4. Hardware Acceleration and GPU Drivers

`grintion-desktop drivers` automatically inspects PCI hardware and kernel DRM subsystems to install the matching graphics acceleration stack:

- **Intel Graphics:** `mesa`, `xf86-video-intel`, `vulkan-intel`
- **AMD Radeon:** `mesa`, `xf86-video-amdgpu`, `vulkan-radeon`
- **NVIDIA:** `mesa`, `xf86-video-nouveau`
- **QEMU / KVM / VirtIO:** `mesa`, `xf86-video-qxl`, `xf86-video-fbdev`
- **VMware:** `mesa`, `xf86-video-vmware`
- **VirtualBox:** `virtualbox-guest-utils`

---

## 5. Service Management with runit

Grintion-OS uses `runit` for fast, declarative service supervision.

When a display manager is installed, `grintion-desktop` records the choice in `/etc/grintion/display-manager`, uses the tracked `/etc/sv/display-manager/run` script, and enables the service with a `/var/service/display-manager` link:

```sh
# Check display manager status
sv status display-manager

# Start / stop the display manager
sv start display-manager
sv stop display-manager

# Restart display manager
sv restart display-manager
```

For console users who prefer manual start without a display manager:
- For X11 desktops: configure `~/.xinitrc` (created by `grintion-desktop`) and run `startx`.
- For Sway: run `sway` directly from the console prompt (no `.xinitrc`; copy `/etc/sway/config` to `~/.config/sway/config` to customise it).

The selected display manager is recorded in `/etc/grintion/display-manager` and
supervised by the tracked `/etc/sv/display-manager/run` service (or `/etc/sv/greetd/run`
when using greetd).

---

## 6. Accessibility Management (`grintion-a11y`)

`grintion-a11y` configures system-wide accessibility features for console, graphical
greeters, and desktop sessions:

```sh
# Toggle or enable screen reader (espeak-ng / orca)
grintion-a11y screen-reader on

# Enable screen magnifier
grintion-a11y magnifier on

# Enable on-screen virtual keyboard (onboard / wvkbd)
grintion-a11y virtual-keyboard on

# Set high-contrast visual theme
grintion-a11y high-contrast on

# Set large fonts
grintion-a11y large-fonts on

# Configure greeter accessibility features
sudo grintion-a11y greeter on

# Check current accessibility status
grintion-a11y status
grintion-a11y status --json
```

---

## 7. Display Configuration and HiDPI Scaling (`grintion-display`)

`grintion-display` manages display resolutions, multi-monitor arrangements, and HiDPI
display scaling across both X11 and Wayland sessions:

```sh
# Query connected monitors and current resolutions
grintion-display status
grintion-display status --json

# Set fractional or integer scaling (e.g. 1.25x, 1.5x, 2.0x)
grintion-display scale 1.5

# Set resolution on a specific output
grintion-display resolution eDP-1 1920x1080

# Configure dual-monitor layout (e.g. external monitor right of laptop)
grintion-display layout --primary eDP-1 --right-of HDMI-1
```

---

## 8. Appearance and Themes (`grintion-theme`)

`grintion-theme` configures unified dark/light appearance, desktop wallpapers, and font sizing:

```sh
# Set dark or light mode (GTK2/3/4 and Qt)
grintion-theme mode dark
grintion-theme mode light

# Set desktop wallpaper (X11 feh / Wayland swaybg)
grintion-theme wallpaper /usr/share/backgrounds/grintion/default.png

# Set global base font size (in pt)
grintion-theme font-size 11

# Inspect current theme settings
grintion-theme status
grintion-theme status --json
```

---

## 9. Printing, Bluetooth, and Hardware Devices (`grintion-devices`)

`grintion-devices` manages hardware peripherals and their background runit services:

```sh
# Printing (CUPS):
sudo grintion-devices cups enable
grintion-devices cups list-printers
sudo grintion-devices cups add-printer --name OfficePrinter --uri ipp://192.168.1.50/ipp/print

# Bluetooth:
sudo grintion-devices bluetooth enable
grintion-devices bluetooth scan
sudo grintion-devices bluetooth pair 00:11:22:33:44:55

# Scanning (SANE):
grintion-devices sane scan
grintion-devices sane list-scanners

# Status of all hardware subsystems:
grintion-devices status
grintion-devices status --json
```

Underlying runit services live in `/etc/sv/cupsd` and `/etc/sv/bluetoothd`.

---

## 10. System Onboarding (`grintion-welcome`)

`grintion-welcome` provides an interactive first-boot onboarding walkthrough and
diagnostic tool for new users:

```sh
# Run interactive welcome wizard
grintion-welcome

# Output machine-readable readiness state
grintion-welcome --json
```

It checks and guides configuration for:
- Network connectivity (Ethernet, Wi-Fi status)
- Display scaling and monitor layout
- Dark/light theme preferences
- Installed desktop environment
- Opt-in application suites
- Rollback snapshots and system recovery status

---

## 11. Modular Application Profiles (`grintion-apps`)

To prevent base image bloat, applications are grouped into opt-in modular profile
configurations under `/etc/grintion/profiles.d/`:

- `browser.conf`: Web browsing (Firefox, Chromium)
- `office.conf`: Productivity and document editing (LibreOffice)
- `gaming.conf`: Gaming runtimes, Steam, Vulkan utilities
- `vmguest.conf`: Guest integration tools (QEMU guest agent, VirtualBox utilities)
- `dev.conf`: Developer tools, compilers, Git, debuggers

```sh
# List available application profiles and installation status
grintion-apps list
grintion-apps list --json

# Install an application profile suite
sudo grintion-apps install browser
sudo grintion-apps install office

# Remove an application profile
sudo grintion-apps remove gaming

# Check profile status
grintion-apps status
```

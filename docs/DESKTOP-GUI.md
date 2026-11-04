# Desktop and GUI Support in Grintion-OS

Grintion-OS is designed with a clean separation of concerns:
- **Base Media:** Boots into a lightweight, fast, and secure console prompt for pre-installation, partitioning, system maintenance, and initial setup.
- **GUI & Desktop Environments:** Supported for installation. Users can pre-install their preferred graphical desktop during initial installation (`grintion-install --desktop <env>`), or install and configure desktop environments and GPU drivers anytime using `grintion-desktop`.

---

## Verification status (0.8.3)

What is verified: `grintion-desktop install <profile>` completes, the desktop
packages and display manager are present, the D-Bus system bus and service
accounts are created, and `/var/service/display-manager` is enabled. The
console and framebuffer are covered by `make test-display` and the boot tests.

What is **not** verified: a rendered graphical greeter or desktop session. The
last full XFCE install reached LightDM, but the greeter exited before drawing
with `Failed to establish PAM credentials: Critical error - immediate abort`
in `/var/log/lightdm/seat0-greeter.log`. 0.8.3 fixes a missing `lightdm`
shadow entry that can cause that abort, but no post-fix graphical screenshot
has been captured. Treat the profiles below as installation recipes, not as
proof of a working session.

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

Wayland-only profiles (Sway) leave `DM` and `XINITRC` empty and are started with
`sway`; `grintion-desktop` never writes `exec sway` into `.xinitrc`.

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

### GNOME (`gnome`)
- **Display Server:** Wayland (with X11 fallback)
- **Default Display Manager:** GDM
- **Characteristics:** Polished modern design, comprehensive application ecosystem, smooth touch gestures.
- **Packages:** `gnome`, `gnome-terminal`, `nautilus`, `gdm`

### KDE Plasma (`kde` / `plasma`)
- **Display Server:** Wayland / X11
- **Default Display Manager:** SDDM
- **Characteristics:** Highly customizable, modern Qt design, widget system, powerful settings.
- **Packages:** `plasma-meta`, `konsole`, `dolphin`, `sddm`

### LXQt (`lxqt`)
- **Display Server:** X11
- **Default Display Manager:** SDDM
- **Characteristics:** Extremely low resource consumption, clean Qt interface.
- **Packages:** `lxqt`, `pavucontrol-qt`, `qterminal`, `pcmanfm-qt`, `sddm`

### Sway (`sway`)
- **Display Server:** Wayland native
- **Default Display Manager:** Direct login or LightDM
- **Characteristics:** Ultra-fast, keyboard-driven i3-compatible Wayland tiling compositor.
- **Packages:** `sway`, `swaylock`, `swayidle`, `waybar`, `foot`, `wofi`, `polkit`

### i3 (`i3`)
- **Display Server:** X11
- **Default Display Manager:** LightDM
- **Characteristics:** Classic, rock-solid keyboard-driven tiling window manager.
- **Packages:** `i3-wm`, `i3status`, `i3lock`, `dmenu`, `rxvt-unicode`

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
supervised by the tracked `/etc/sv/display-manager/run` service.

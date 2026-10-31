# Desktop and GUI Support in Grintion-OS

Grintion-OS is designed with a clean separation of concerns:
- **Base Media:** Boots into a lightweight, fast, and secure console prompt for pre-installation, partitioning, system maintenance, and initial setup.
- **GUI & Desktop Environments:** Fully supported! Users can pre-install their preferred graphical desktop during initial installation (`grintion-install --desktop <env>`), or install and configure desktop environments and GPU drivers anytime using `grintion-desktop`.

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
| `grintion-desktop list` | Display available desktop environments, window managers, and their characteristics. |
| `grintion-desktop install <name>` | Install desktop packages, install recommended GPU drivers, and configure display manager. |
| `grintion-desktop drivers` | Automatically detect GPU hardware (Intel, AMD, NVIDIA, QEMU/KVM, VMware) and install driver packages. |
| `grintion-desktop status` | Show current display server, installed desktops, and active display manager services. |

### Options

- `--dm, --display-manager <sddm|lightdm|gdm>`: Override the default display manager.
- `--root <path>`: Install into a specific root filesystem (e.g. `/mnt` for disk installation).
- `--no-drivers`: Skip automatic GPU driver detection and installation.
- `-y, --noconfirm`: Run non-interactively without prompting for confirmation.

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

When a display manager is installed, `grintion-desktop` creates and enables the `/var/service/display-manager` service:

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
- For Sway: run `sway` directly from the console prompt.

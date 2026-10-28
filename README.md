```text
        █
       █▓█
      █▓▒▓█
     █▓▒@▒▓█
    █▓▒@@▒▓█
   █▓▒@+-+@▒▓█
  █▓▒@+-----+@▒▓█
 █▓▒@+---/-\--+@▒▓█
█▓▒@+---/     \--+@▒▓█
     ▓▒@   @▒▓         
    ▓▒@       @▒▓
   ▓▒@           @▒▓
  ▓▒@               @▒▓
 █@█           █@█
```

# Grintion-OS

> **A completely independent, vanilla Linux-kernel operating system built for paranoid users.**  
> *Zero distribution heritage. No telemetry. Minimalist attack surface. Total DIY control.*

---

## 🎯 The MISS Philosophy

Grintion-OS does not branch from Debian, Arch, Red Hat, Alpine, Void, or Gentoo. It is built strictly on top of the **vanilla Linux kernel** paired directly with GNU coreutils, the `runit` init supervision suite, and the custom `garb` package manager.

```
┌────────────────────────────────────────────────────────────────────────┐
│  M — MINIMALIST  │  Zero superfluous daemons; runs entirely in RAM.   │
│  I — INDEPENDENT │  Directly kernel-native; zero distro dependencies. │
│  S — SECURE      │  Hardened sysctl, seccomp sandboxing, paranoid.    │
│  S — STABLE      │  Runit deterministic process supervision.          │
└────────────────────────────────────────────────────────────────────────┘
```

* **Minimalist**: Stripped of bloat, analytics, and complex dependency webs. Idles under 50MB of RAM.
* **Independent**: Complete sovereignty over package manifests, ABI compilation, and system configuration.
* **Secure**: Tailored specifically for **paranoid users** who require transparent auditability, memory wiping on shutdown, strict sandboxing, and immutable system roots.
* **Stable**: Deterministic `runit` supervision guarantees fast boots, predictable shutdown stages, and zero cascading init failures.

---

## 💻 Target Hardware

| Architecture | Platform | Boot Modes |
| :--- | :--- | :--- |
| **x86_64** | 64-bit Intel & AMD PCs, Laptops, Servers | UEFI (64-bit) & Legacy BIOS |
| **AArch64 / ARM64** | 64-bit ARM SBCs, Neoverse, UEFI Workstations | UEFI (AArch64) |

---

## 🛡️ Core System Stack

* **Kernel**: Vanilla Linux Kernel with security hardening:
  * Strict memory protection (`slab_nomerge`, `init_on_alloc=1`, `init_on_free=1`).
  * Kernel page-table isolation (`kpti=on`), ASLR level 2, user namespace sandboxing.
  * Restricted `/dev/mem`, `/dev/kmem`, and `dmesg_restrict=1`.
* **Init System**: `runit`
  * Fast, deterministic 3-stage supervision (`/etc/runit/1`, `2`, `3`).
  * Clean service links in `/var/service`.
* **Core Utilities**: **GNU coreutils** (`ls`, `cat`, `cp`, `chmod`, `dd`, `chroot`, etc.).
* **Universal & Container Sandboxing**:
  * Out-of-the-box support for **Flatpak**, **Snap**, and **AppImage**.
  * Utilizes kernel cgroups v2, user namespaces, FUSE (`/dev/fuse`), and bubblewrap sandboxing.
* **Package Manager**: **`garb`**
  * Minimalist, cryptographically verified package manager designed specifically for Grintion-OS.

---

## 🚀 Live RAM Environment & DIY Experience

When you boot the Grintion-OS ISO, it loads entirely into **RAM (`tmpfs`)** and presents you with a root prompt featuring the Grintion-OS ASCII emblem. There are no pre-assumed defaults: **you are in complete DIY control**.

### 🛠️ The DIY Installation Workflow

```mermaid
graph LR
    Boot[1. Boot Live ISO into RAM] --> Net[2. Configure Network]
    Net --> Disk[3. Partition & Format Disk]
    Disk --> Mount[4. Mount Target /mnt]
    Mount --> Bootstrap[5. garb bootstrap base]
    Bootstrap --> Conf[6. Users, Drivers & Config]
    Conf --> Bootloader[7. Install Bootloader]
    Bootloader --> Reboot[8. Reboot & Eject ISO]
```

### Step-by-Step DIY Guide:

#### 1. Bring up Networking
```bash
# Check detected interfaces
ip link

# Bring up interface and request DHCP lease
ip link set eth0 up
dhcpcd eth0
# or configure static IP
ip addr add 192.168.1.50/24 dev eth0
ip route add default via 192.168.1.1
echo "nameserver 1.1.1.1" > /etc/resolv.conf

# Test connectivity
ping -c 3 kernel.org
```

#### 2. Partition and Format the Disk
```bash
# Identify target block device
lsblk

# Partition using fdisk or parted (GPT recommended)
fdisk /dev/nvme0n1
# Example:
#   /dev/nvme0n1p1 : 512M EFI System Partition (type EFI)
#   /dev/nvme0n1p2 : Remainder Linux Root Filesystem

# Format filesystems
mkfs.vfat -F32 /dev/nvme0n1p1
mkfs.ext4 -L GRINTION_ROOT /dev/nvme0n1p2
```

#### 3. Mount Target Filesystems
```bash
mount /dev/nvme0n1p2 /mnt
mkdir -p /mnt/boot/efi
mount /dev/nvme0n1p1 /mnt/boot/efi
```

#### 4. Bootstrap Base System with `garb`
```bash
# Bootstrap Grintion base (kernel, runit, gnu coreutils, garb) into /mnt
garb bootstrap /mnt

# Generate filesystem table
genfstab -U /mnt > /mnt/etc/fstab
```

#### 5. Configure System in Chroot
```bash
grintion-chroot /mnt

# Set system hostname
echo "paranoid-station" > /etc/hostname

# Set root password
passwd

# Create everyday user with wheel access
useradd -m -G wheel -s /bin/bash freddy
passwd freddy

# Configure services in runit
ln -s /etc/sv/agetty-tty1 /var/service/
ln -s /etc/sv/network /var/service/
```

#### 6. Install Bootloader
```bash
# Install Limine bootloader for UEFI & BIOS
limine-deploy --efi /mnt/boot/efi --disk /dev/nvme0n1
```

#### 7. Reboot and Remove ISO/USB
```bash
exit
umount -R /mnt
reboot
# Remove the USB or ISO when prompted!
```

---

## 📦 The `garb` Package Manager

`garb` (**G**rintion **A**tomic **R**eliable **B**uilder) is built for minimalist, secure package operations:

```bash
# Update repository index and verify cryptographic signatures
garb update

# Search for available packages
garb search wireguard

# Install packages
garb install wireguard-tools iptables

# Inspect package manifests and integrity
garb verify wireguard-tools

# Remove package cleanly
garb remove wireguard-tools

# Execute sandboxed container apps (AppImage, Flatpak, Snap)
garb sandbox run ./Element.AppImage --isolated
```

### Garbfile Manifest Structure
Each package is defined by a declarative, human-readable manifest:
```toml
[package]
name = "tor"
version = "0.4.8.10"
release = 1
description = "Anonymizing overlay network for TCP"
license = "BSD-3-Clause"
arch = ["x86_64", "aarch64"]

[security]
sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
signature = "tor-0.4.8.10.sig"
hardened = true
sandbox = ["seccomp", "net-only"]

[dependencies]
runtime = ["libevent", "openssl", "zlib"]

[build]
configure = "./configure --prefix=/usr --sysconfdir=/etc --disable-asciidoc"
compile = "make -j$(nproc)"
install = "make DESTDIR=$PKGDIR install"
```

---

## 🔨 Building the Grintion-OS ISO

To generate the bootable live RAM `.iso` image on your local machine:

```bash
# Check prerequisites and build the hybrid ISO
make iso
# or run the build script directly:
./build/build-iso.sh
```

The resulting file `grintion-os-x86_64.iso` is ready to be burned to a USB stick using `dd`:
```bash
sudo dd if=output/grintion-os-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

---

## 📄 License & Integrity

Grintion-OS is distributed under the **GPL-3.0 License** for all OS orchestration scripts, with individual components respecting their respective upstream open-source licenses (Linux Kernel: GPL-2.0, GNU Coreutils: GPL-3.0+, Runit: 3-clause BSD). See [`LICENSE`](LICENSE) for complete details.

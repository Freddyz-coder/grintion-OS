# Grintion-OS Quick Setup Guide

## 1. Requirements & VM Configuration

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **RAM** | 2 GB | 4 GB+ |
| **CPU** | 1 Core | 2+ Cores |
| **Storage** | 15 GB | 25 GB+ |
| **Firmware** | UEFI / BIOS | UEFI |

> **VirtualBox Note:** Set Network Adapter to **Intel PRO/1000 MT Desktop (82540EM)** in VM Settings → Network → Advanced. The default PCnet adapter is not supported.

---

## 2. Live Boot & Login

- **Boot Menu:** Select `Grintion-OS (x86_64)`
- **User:** `root`
- **Password:** `root` (or press Enter)

---

## 3. Network & Internet Setup

### Test Connection
```bash
ping -c 3 1.1.1.1
```

### Wired (DHCP)
If no IP was assigned automatically:
```bash
# 1. Identify interface (e.g. eth0, enp0s3)
ip link

# 2. Bring up interface and request IP
ip link set eth0 up
dhcpcd eth0

# Or restart network service
sv restart network
```

### Wi-Fi Setup
```bash
# 1. Unblock and bring up wireless interface
rfkill unblock wifi 2>/dev/null || true
ip link set wlan0 up

# 2. Generate configuration
wpa_passphrase "SSID" "PASSWORD" > /etc/wpa_supplicant/wpa_supplicant.conf

# 3. Connect and obtain IP
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
dhcpcd wlan0

# 4. Verify
ping -c 3 1.1.1.1
```

### Static IP
```bash
ip link set eth0 up
ip addr add 192.168.1.50/24 dev eth0
ip route add default via 192.168.1.1 dev eth0
echo "nameserver 1.1.1.1" > /etc/resolv.conf
```

### Fix DNS (Domains Not Resolving)
If `ping 1.1.1.1` works but domain names fail:
```bash
echo "nameserver 1.1.1.1" > /etc/resolv.conf
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
```

### Network Diagnostics
```bash
ip addr                  # View interfaces and IP addresses
ip route                 # View default routes
cat /var/log/dhcpcd.log  # View DHCP daemon logs
```

---

## 4. Install to Disk

```bash
# 1. Identify target drive (e.g. /dev/sda, /dev/vda, /dev/nvme0n1)
lsblk

# 2. Run installer (formats disk, copies system, creates user)
grintion-install --disk /dev/sda --user grintion --desktop xfce

# Or interactive mode:
grintion-install --disk /dev/sda
```

---

## 5. First Boot

1. Power off: `poweroff`
2. Remove the ISO / installation media.
3. Boot and log in with your created user credentials.
4. Verify sudo:
   ```bash
   sudo whoami  # returns root
   ```

---

## 6. Desktop Environments

Install pre-configured desktop environments and GPU drivers:

```bash
# Install desktop (options: xfce, gnome, kde, lxqt, sway, i3)
sudo grintion-desktop install xfce

# Enable login manager on boot
sudo ln -sfn /etc/sv/display-manager /var/service/display-manager
sudo sv restart display-manager

# Or launch XFCE manually without a display manager
echo "exec startxfce4" > ~/.xinitrc
startx
```

---

## 7. Package Management (`garb`)

| Command | Action |
| :--- | :--- |
| `sudo garb update` | Update package databases |
| `sudo garb upgrade` | Upgrade installed packages |
| `sudo garb install <pkg>` | Install package |
| `sudo garb remove <pkg>` | Remove package |
| `garb search <query>` | Search packages |
| `sudo garb clean` | Clean package cache |

### Common Packages
```bash
# Web browser, text editors, development tools
sudo garb install firefox nano vim git htop fastfetch
```

---

## 8. Service Management (`runit`)

| Command | Action |
| :--- | :--- |
| `sudo sv status <service>` | Check service status |
| `sudo sv status /var/service/*` | Check all running services |
| `sudo sv restart <service>` | Restart service |
| `sudo ln -s /etc/sv/<service> /var/service/` | Enable on boot |
| `sudo rm /var/service/<service>` | Disable on boot |

---

## 9. Troubleshooting

- **No network in VirtualBox:** Change VM Adapter to `Intel PRO/1000 MT Desktop (82540EM)` in Settings → Network → Advanced.
- **Reboot / Poweroff:** Use `sudo reboot` or `sudo poweroff` (add `-f` to force).
- **Change resolution:** Run `xrandr -s 1920x1080` or use Settings → Display in XFCE.

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
- **Password:** none. The live console auto-logs in through `live-shell`; the PAM root account is locked, so `su`/`login` do not accept a blank password.

---

## 3. Network & Internet Setup

### Test Connection
```bash
grintion-network status     # configured interfaces and service state
ping -c 3 1.1.1.1
```

The live shell appears before DHCP has finished, so a ping in the first few
seconds can report "Network is unreachable". `grintion-network status` tells you
whether the lease has landed.

### Wired (DHCP)
This is automatic at boot on every wired interface. If no address was assigned:
```bash
sudo sv restart network
grintion-network status
tail -n 20 /var/log/dhcpcd.log
```

### Wi-Fi Setup
```bash
grintion-network wifi-scan                    # list visible networks
sudo grintion-network connect "SSID" "PASSWORD"
```

`connect` writes `/etc/grintion/network.conf` (mode 0600), enables the
`wpa_supplicant` service and restarts `network`. To forget the network:
```bash
sudo grintion-network disconnect
```

### Static IP
```bash
sudo grintion-network set-static eth0 192.168.1.50/24 192.168.1.1 1.1.1.1,8.8.8.8
```

The last argument is a comma-separated DNS list. The address survives reboot
because it is stored in `/etc/grintion/network.conf`, not applied by hand.

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

1. Power off: `poweroff` (`sudo poweroff` in the installed system)
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
# The full XFCE download can take several minutes on a slow mirror; package
# manager output is streamed to the screen and saved to
# /var/log/grintion-desktop.log
sudo tail -n 40 /var/log/grintion-desktop.log

# grintion-desktop enables and starts the login manager for you; to redo it by hand:
sudo ln -sfn /etc/sv/dbus /var/service/dbus
sudo ln -sfn /etc/sv/display-manager /var/service/display-manager
sudo sv restart display-manager

# If the manager will not stay up, read its log
sudo tail -n 40 /var/log/display-manager.log

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
| `garb list [--upgradable]` | List installed or upgradable packages |
| `sudo garb clean` | Purge cached repository data (run `garb update` afterwards) |

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
- **Reboot / Poweroff:** Use `sudo reboot` or `sudo poweroff`; `-f` skips the
  service shutdown and powers off immediately. `poweroff` without root fails on
  purpose, exactly like it does without `sudo` on Arch.
- **Change resolution:** Run `xrandr -s 1920x1080` or use Settings → Display in XFCE.
- **D-Bus login messages:** `dbus-daemon` startup warnings are written to
  `/var/log/dbus.log`, not the login prompt. A desktop install also creates the
  service accounts (polkitd, colord, avahi) and groups the installed D-Bus
  policies name.

# Grintion-OS Security Hardening Architecture

This document describes the defense-in-depth security model implemented in Phase 8 of Grintion-OS.

## 1. Security Profiles

Grintion-OS supports four system security profiles managed via `grintion-security`:

| Profile | Target Environment | Firewall Policy | AppArmor Mode | USB Policy | Network | Audit Trail |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`workstation`** | Desktop / Workstation | Drop unsolicited inbound | Enforce on daemons, complain on user apps | Allowed | Enabled | Sudo I/O + Auth |
| **`server`** | Hardened Headless Server | Strict drop, SSH/whitelisted only | Enforce all | Data-block enabled | Enabled | Full Auditd |
| **`kiosk`** | Display / Single-app Kiosk | Strict drop, loopback only | Enforce all | Input devices only | Controlled | Full Auditd |
| **`air-gapped`** | Offline / Classified | Drop all network traffic | Enforce all | Data-block enabled | Disabled | Strict Auditd |

The security profile can be chosen during installation via `grintion-install --security-profile <PROF>` and inspected at any time with `grintion-security status` or `grintion-security-report`.

## 2. Mandatory Access Control (AppArmor)

AppArmor is compiled into the kernel (`CONFIG_SECURITY_APPARMOR=y`), the boot
command line selects it (`security=apparmor apparmor=1`), `/etc/runit/1` mounts
securityfs, and the `apparmor` runit service loads every profile at boot. A
profile file that is not loaded confines nothing, so do not treat the files in
`/etc/apparmor.d/` as enforcement evidence by themselves.

- Profiles:
  - `bin.grintion-network`: confines the network manager while allowing
    netlink, DHCP and Wi-Fi helpers. Denies credential files, raw disks, boot
    files, kernel memory, MAC policy and dangerous capabilities.
  - `usr.bin.garb`: confines package installation. Package managers need broad
    filesystem write access, so the boundary is credentials, host keys, boot
    files, raw block devices, kernel memory, `/sys` and `/proc/sys` writes, and
    capabilities such as `sys_admin`, `sys_module` and `sys_rawio`.
  - `usr.bin.browser-sandbox`: confines browser processes to their own config,
    cache, downloads, X11 and D-Bus paths. SSH/GPG keys, cloud tokens, host
    private keys, raw devices and kernel memory are explicitly denied.
- Profiles use `flags=(attach_disconnected,mediate_deleted)`, and every
  sensitive-path `deny` rule overrides inherited abstractions. The rootfs build
  parses every profile with the real `apparmor_parser` and fails closed on a
  syntax error.
- Manage them with `grintion-apparmor status`, `grintion-apparmor load-all`,
  `grintion-apparmor verify`, `grintion-apparmor enforce <profile>` and
  `grintion-apparmor complain <profile>`. `verify` fails unless the kernel has
  loaded the profiles in enforce mode; `status` separates on-disk profiles from
  kernel-loaded profiles.
- An experimental SELinux configuration remains at `/etc/selinux/config`; it is
  not the default MAC implementation.

## 3. Application Sandboxing (`grintion-sandbox`)

- Applications and risky network clients (browsers, document viewers) can be wrapped using `grintion-sandbox`:
  - Private mount, user, and PID namespaces.
  - Read-only root filesystem (`--ro-bind / /`).
  - Private temporary storage (`/tmp` tmpfs).
  - Explicit home shielding: prevents reading `~/.ssh`, `~/.gnupg`, and `/root`.
  - Network isolation toggle: `--no-net` drops all outbound network connectivity.

## 4. Audit Logging & Privileged Tracing

- Supervised `auditd` service runs under runit (`/etc/sv/auditd/run`) with rules in `/etc/audit/audit.rules`.
- Monitors `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, privilege escalation (`su`/`sudo`), and MAC policy changes.
- Sudo I/O logging is enabled via `/etc/sudoers.d/audit-log` saving session input/output to `/var/log/sudo-io`.
- Inspected using `grintion-audit-log` or `grintion-audit-log --sudo`.

## 5. File Integrity Baseline (`grintion-integrity`)

- Uses SHA-256 baseline hashing across critical system binaries (`/bin`, `/sbin`, `/usr/bin`, `/etc/grintion`, `/etc/shadow`).
- Initialized with `grintion-integrity init`.
- Verified at boot or on-demand with `grintion-integrity check`. Any unauthorized modification causes a non-zero exit and security failure report.

## 6. Anti-Malware & SUID Scans (`grintion-scan`)

- Inspects suspicious world-writable paths (`/tmp`, `/var/tmp`, `/dev/shm`) for unauthorized SUID/SGID binaries.
- Checks network interfaces for unauthorized promiscuous mode sniffing.
- Integrates with `rkhunter` and `chkrootkit` if installed.

## 7. USB & Thunderbolt Protection (`grintion-usb`)

- Manages USBGuard daemon (`/etc/sv/usbguard/run`) and policies (`/etc/usbguard/rules.conf`).
- Provides USB data-block mode (`grintion-usb block-data`): blocks mass storage and untrusted USB data devices while permitting keyboards and mice.
- Supports manual device authorization and revocation (`grintion-usb authorize <DEV>`).

## 8. Secrets Vault & Trust Store (`grintion-vault`)

- Portable symmetric encrypted key-value vault (`grintion-vault set <KEY> <VAL>`, `grintion-vault get <KEY>`).
- Cryptographic multi-pass file shredding (`grintion-vault shred <FILE>`).
- System CA trust store management (`grintion-vault trust-cert <CERT>`, `untrust-cert <NAME>`).

## 9. Privacy Dashboard (`grintion-privacy`)

- Visualizes listening sockets, exposed non-loopback ports, active outbound network connections, camera/microphone availability, and human-readable firewall rule explanations.

## 10. SSH Brute-Force Shield (`grintion-shield`)

- Daemon monitoring authentication failures (`/etc/sv/grintion-shield/run`).
- Automatically blacklists abusive IP addresses via `nftables` or `/etc/hosts.deny` upon exceeding retry thresholds.

## 11. X11 Access Control

- `startx` uses `/etc/X11/xinit/xserverrc`, which starts Xorg with
  `-nolisten tcp -nolisten local`. This removes the TCP listener and the
  abstract-namespace socket; clients must use `/tmp/.X11-unix` and present the
  per-session MIT-MAGIC-COOKIE.
- `grintion-desktop` writes the same flags into LightDM's
  `xserver-command` and SDDM's `[X11] ServerArguments`, so graphical logins do
  not reopen the remote transports. The files are written after package
  installation because pacman can replace `xserverrc`.
- `etc/X11/xinit/xinitrc.d/05-grintion-x11-security.sh` runs `xhost -` to keep
  the server access-control list enabled and makes `$XAUTHORITY` mode 0600.
- `Xwrapper.config` sets `allowed_users = console`; only the local console user
  may start Xorg. `needs_root_rights = yes` is required because the image has no
  logind, so Xorg runs as root. That is an accepted limitation, not a claim of
  rootless X11.
- X11 is not a security boundary between clients running as the same user.
  These controls stop remote and other-user connections; they do not isolate a
  compromised X11 client from the rest of the session. Use the Wayland
  profiles or `grintion-sandbox` when client isolation is required.


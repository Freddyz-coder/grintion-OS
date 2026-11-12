# Grintion-OS Security Hardening Architecture

This document describes the defense-in-depth security model implemented in Phase 8 of Grintion-OS.

## 1. Security Profiles

Grintion-OS supports four system security profiles managed via `grintion-security`:

| Profile | Target Environment | Firewall Policy | AppArmor Mode | USB Policy | Network | Audit Trail |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`workstation`** | Desktop / Workstation | Drop unsolicited inbound | Enforce shipped daemon profiles | Allowed | Enabled | Rules staged; no daemon |
| **`server`** | Hardened Headless Server | Strict inbound drop; no service ports opened by default | Enforce all | Data-block enabled | Enabled | Rules staged; no daemon |
| **`kiosk`** | Display / Single-app Kiosk | Strict inbound drop | Enforce all | Data-block enabled | Enabled | Rules staged; no daemon |
| **`air-gapped`** | Offline / Classified | Drop all network traffic | Enforce all | Data-block enabled | Disabled | Rules staged; no daemon |

The security profile can be chosen during installation via `grintion-install --security-profile <PROF>` and inspected at any time with `grintion-security status` or `grintion-security-report`.

`grintion-security set <PROF>` applies live controls by default: USB policy,
AppArmor load plus `verify`, and a generated nftables ruleset. It writes
configuration only after those steps succeed and then re-checks the running
state; a failed control rolls back the profile files and the previous firewall.
Use `--config-only` when staging an image or in tests that cannot load kernel
policy. `verify` checks the active `nft list ruleset` chain marker, AppArmor
enforcement, the USB config, and auditd availability instead of trusting the
configuration file alone.

**Auditd is not shipped in the current base image.** The rules and service file
are staged for a future package, but `auditd`/`auditctl` userspace is absent, so
the profile reports a warning. Do not read the profile table as a claim that an
audit daemon is running.

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

- `/etc/audit/audit.rules` and `/etc/sv/auditd/run` are staged and describe monitoring for `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`, privilege escalation and MAC policy changes.
- The current base image does **not** include the `auditd`/`auditctl` userspace. The security profile reports auditd as a warning; it does not claim that a daemon is consuming those rules. Kernel audit support may still be present.
- Sudo I/O logging is configured separately via `/etc/sudoers.d/audit-log` and does not depend on auditd.
- Inspect available logs with `grintion-audit-log` or `grintion-audit-log --sudo` when the relevant daemon or sudo I/O files exist.

## 5. File Integrity Baseline (`grintion-integrity`)

- Records SHA-256, mode, owner, group and size for critical binaries and configuration (`/bin`, `/sbin`, `/usr/bin`, `/usr/sbin`, `/etc/grintion`, PAM/sudo/AppArmor configuration, `/etc/shadow`, `/boot`).
- Initialized with `grintion-integrity init`; the baseline is written atomically with mode 0600 and refuses to save if a monitored file cannot be hashed.
- Verified at boot or on-demand with `grintion-integrity check`. It reports modified, added, removed, size-changed and mode-changed files separately. A newly added setuid/setgid bit is reported as a privilege change even when the file hash is unchanged.
- A missing or corrupt baseline exits with status 2 rather than being treated as clean.

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

## 12. Boot Health and Auto-Revert (`grintion-boot-health`)

- The `boot-health` service records one attempt at boot and marks the boot good
  after a session is confirmed or a stable window passes.
- Attempt counters are updated under a lock, parsed as bounded numbers, and
  replaced atomically. A corrupt or partial counter cannot turn into an
  unbounded boot loop.
- Three failed attempts write `failed`, log the result, and rewrite the Limine
  default entry to an existing snapshot or recovery entry. The edit is
  validated and replaced atomically, with a `.pre-boot-health` backup.
- This is a bootloader selection change only. It does not restore a root
  filesystem, verify that the alternate entry boots, or replace
  `grintion-snapshot` rollback. The variable overrides
  `GRINTION_BOOT_HEALTH_STATE` and `GRINTION_LIMINE_CONF` exist for tests and
  recovery environments.


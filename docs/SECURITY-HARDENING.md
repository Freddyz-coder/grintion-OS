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

- AppArmor profiles are located in `/etc/apparmor.d/`:
  - `bin.grintion-network`: Isolates network tools, restricts access to shadow/root credentials.
  - `usr.bin.garb`: Confines package manager operations, preventing access to user SSH keys and passwords.
  - `usr.bin.browser-sandbox`: Strictly sandboxes browser processes to temporary cache and Downloads folders.
- Managed using `grintion-apparmor status`, `grintion-apparmor enforce <profile>`, and `grintion-apparmor complain <profile>`.
- An experimental track configuration is tracked at `/etc/selinux/config`.

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


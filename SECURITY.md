# Security Policy & Hardening Model

Grintion-OS is engineered for **paranoid users**: individuals, researchers, and administrators who operate under heightened adversarial models and demand zero telemetry, strict isolation, verifiable supply chains, and minimal attack surfaces.

---

## 1. Threat Model & Security Principles

Grintion-OS addresses the following primary threat vectors:

1. **Persistent Espionage & Covert Telemetry**:
   - Zero background analytics, diagnostic telemetry, or remote telemetry sockets exist in Grintion-OS.
   - All network traffic is initiated solely by explicit user commands.

2. **Tampering & Supply Chain Poisoning**:
   - The OS does not rely on foreign distribution mirrors.
   - All packages managed by `garb` require cryptographic hash verification (SHA-256 / BLAKE3) and detached signature verification.

3. **Userland Compromise & Lateral Movement**:
   - Universal application packages (**Flatpak**, **Snap**, **AppImage**) run inside unprivileged sandboxes utilizing Linux user namespaces, cgroups v2, and seccomp-bpf filter profiles.
   - Core system binaries are strictly separated from user applications.

4. **Forensic Recovery from Cold RAM / Physical Inspection**:
   - The live environment operates in ephemeral RAM (`tmpfs`).
   - `runit` stage 3 implements memory buffer flushing and unmount safety to prevent cold-boot and residual disk leaks.

---

## 2. Kernel Hardening & Sysctl Profiles

Grintion-OS enforces kernel security parameters at boot (`/etc/runit/1` and `/etc/sysctl.d/99-paranoid.conf`):

```ini
# Prevent unprivileged users from reading kernel logs (dmesg)
kernel.dmesg_restrict = 1

# Prevent unprivileged users from viewing kernel pointer addresses
kernel.kptr_restrict = 2

# Restrict ptrace execution to processes with predefined parent/child relationships
kernel.yama.ptrace_scope = 2

# Enable full Address Space Layout Randomization (ASLR)
kernel.randomize_va_space = 2

# Disable unprivileged eBPF to prevent speculative execution micro-architectural leaks
kernel.unprivileged_bpf_disabled = 1

# Protect against symlink and hardlink race condition exploits
fs.protected_symlinks = 1
fs.protected_hardlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2

# Network stack hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
```

---

## 3. Sandboxing Universal Containers (Flatpak, Snap, AppImage)

Grintion-OS treats all third-party software as untrusted:

```
[Untrusted Binary / AppImage / Flatpak]
                 │
                 ▼
┌─────────────────────────────────┐
│     garb sandbox wrapper        │
├─────────────────────────────────┤
│ • User Namespaces (unshare)     │
│ • Seccomp System Call Filters   │
│ • Read-Only Root Filesystem     │
│ • Isolated Private /tmp & /dev  │
│ • Optional Network Namespace    │
└─────────────────────────────────┘
                 │
                 ▼
          [Host Kernel]
```

- **AppImage**: Executed inside an isolated bubblewrap (`bwrap`) container with a restricted `/dev/fuse` pass-through, protecting `$HOME` and system directories.
- **Flatpak**: Runs via native unprivileged container sandboxes backed by bubblewrap and Portal interfaces.
- **Snap**: Confinement via AppArmor/Seccomp and mount namespaces.

---

## 4. Cryptographic Verification in `garb`

Every package in `garb` is verified prior to unpacking:
- **Checksum Verification**: SHA-256 and BLAKE3 digests calculated against known manifests.
- **Signature Checking**: Detached Ed25519 signatures verified against trusted keyring stored in `/etc/garb/keys/`.
- **Atomic Rollback**: Package files are placed into staging directories before transaction commit; corrupted or compromised files cause an immediate abort and rollback.

---

## 5. Vulnerability Disclosure & Reporting

If you identify a security flaw, vulnerability, or potential exploit vector in Grintion-OS, please follow our coordinated disclosure policy:

1. **Do not create public GitHub issues or social media disclosures** for zero-day vulnerabilities.
2. Email your findings encrypted with PGP to:  
   **`security@grintion-os.org`**
3. Include:
   - Detailed description of the vulnerability.
   - Proof-of-concept (PoC) or reproduction steps.
   - Threat impact assessment (local privilege escalation, sandbox escape, kernel panic).
4. Our team will acknowledge receipt within **48 hours** and provide a patch timeline within **7 business days**.

# Security policy

Grintion-OS is a small Operating system with defensive defaults. It is not a
hardened, audited, or verified-boot platform. This document states what the
0.10.0 release actually provides, what it does not, and how to report a problem.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.10.x | Security fixes on a best-effort basis |
| Earlier versions | No |

There is no long-term-support branch and no guaranteed response time. Security
fixes are published as a new release; there are no automatic updates.

## Reporting a vulnerability

Open a **private** security advisory:

<https://github.com/Freddyz-coder/grintion-OS/security/advisories/new>

Do not open a public issue for an unfixed vulnerability. Include:

- the affected version (`cat /etc/grintion/version`) and architecture;
- the contents of `output/BUILD-INFO` if you built the image yourself;
- a minimal reproducer and the impact you observed;
- whether the issue affects the live image, an installed system, the installer,
  or `garb`.

Reports are handled on a best-effort basis by the maintainers. There is no bug
bounty and no formal disclosure deadline.

---

## Security properties

### Boot and kernel

- Linux 6.12.114 is built from kernel.org source. `make kernel` verifies the
  tarball against `config/linux-6.12.114.tar.xz.sha256`, which is derived from
  kernel.org's signed checksums.
- `config/kernel-hardened.config` disables the BPF syscall, kexec, hibernation
  and `/dev/mem`, and enables Yama, hardened usercopy and strict devmem.
  `binfmt_misc` is compiled out and io_uring is disabled at runtime with
  `kernel.io_uring_disabled=2`. `build/check-kernel-config.sh` fails the build
  if a required symbol is dropped.
- Every loadable module is signed by the build; `CONFIG_MODULE_SIG_FORCE=y`
  rejects unsigned modules. Third-party out-of-tree modules will not load.
- The live ISO boots an unsigned kernel and initramfs through Limine for broad
  hardware compatibility. On installed systems, Unified Kernel Images (UKI)
  and Secure Boot with user-enrolled Machine Owner Keys (MOK) are supported via
  `grintion-secureboot` and `grintion-uki`, alongside TPM 2.0 PCR attestation
  (`grintion-attest`).

### Runtime

`/etc/runit/1` applies `/etc/sysctl.d/99-grintion.conf`. The effective settings
include:

| Setting | Value |
| --- | --- |
| `kernel.randomize_va_space` | 2 |
| `kernel.dmesg_restrict` | 1 |
| `kernel.kptr_restrict` | 2 |
| `kernel.yama.ptrace_scope` | 2 |
| `kernel.perf_event_paranoid` | 3 |
| `kernel.unprivileged_bpf_disabled` | 1 |
| io_uring | Disabled at runtime (`kernel.io_uring_disabled=2`) |
| binfmt_misc | Compiled out (`CONFIG_BINFMT_MISC=n`) |
| `fs.protected_symlinks`, `fs.protected_hardlinks` | 1 |
| `fs.protected_fifos`, `fs.protected_regular` | 2 |
| `fs.suid_dumpable` | 0 |
| `kernel.core_pattern` | `/dev/null` |

The image has no udev; `devtmpfs` creates device nodes and BusyBox `mdev`
applies `/etc/mdev.conf`. The setuid list is explicit in
`config/rootfs.setuid` and applied at build time.

### Accounts and access

- The live image logs in as `root` on the console without a password through
  `agetty --skip-login` and `live-shell`. The PAM root account is locked (`*`
  in `/etc/shadow`), so `su` and `login` do not accept a blank password. This
  console bypass is deliberate for an installation medium and is not a property
  of installed systems.
- The installer creates one administrative user in `wheel`. Root is locked
  unless `--root-password-stdin` (or `GRINTION_ROOT_PASSWORD`) is supplied.
- `sudo` is restricted to `wheel`; `/etc/sudoers` is mode `0440`.
- PAM uses `pam_faillock`; the configuration is in `/etc/security/faillock.conf`
  and `/etc/pam.d/system-auth`, and `/run/faillock` is created by runit stage 1.
  Console logins go through `login(1)` on installed systems.
- `su` is restricted to `wheel` with `pam_wheel.so`; `sudo` is restricted to
  `wheel` in `/etc/sudoers`. New password hashes use yescrypt
  (`ENCRYPT_METHOD YESCRYPT`).

### Network

- The default nftables ruleset drops unsolicited inbound traffic, allows
  loopback, established/related traffic, DHCP replies and ICMP, and permits all
  outbound traffic.
- The network daemons enabled at boot are `dhcpcd` on the detected wired
  interfaces and, when `grintion-network connect` has configured Wi-Fi, the
  supervised `wpa_supplicant` service. Wi-Fi credentials live in
  `/etc/grintion/network.conf` and `/etc/wpa_supplicant/wpa_supplicant.conf`,
  both mode `0600`. There is no SSH server, web server or remote administration
  service enabled by default.
- The image contains the OpenSSH client, not `sshd`.

### Packages

- `garb` verifies an Ed25519 signature over the exact `index.json` bytes before
  parsing it. Trust is rooted in `/etc/garb/keys/*.pub`.
- A signed index carries an `index_version` and an `expires` timestamp. `garb
  update` refuses missing, expired or replayed (older-version) indexes, so a
  captured old index cannot be served to downgrade clients.
- Package archives are verified against the index SHA-256. Every declared file
  is re-hashed during installation; undeclared files and path traversal are
  rejected. Packages may not install setuid or setgid files; the base image's
  setuid list is applied separately by the build.
- A failed transaction restores replaced files and removes files installed
  during the attempt; an incomplete restore keeps the backup and reports its
  path. Installs refuse files owned by another package, and removal refuses to
  break a reverse dependency, unless `--force` is used.
- No repository key is trusted by default and no repository is configured.
- The image also contains **pacman** as an external backend for `garb`. It
  verifies Arch packages against the Arch public keyring with
  `SigLevel = Required DatabaseOptional`, matching Arch's own default. Database
  signatures cannot be required because the official mirrors do not publish
  `core.db.sig`/`extra.db.sig` (both return 404); `DatabaseRequired` breaks
  `pacman -Sy`. The keyring is pinned by
  `config/pacman-keyring.sha256`. It does not use garb's signed
  indexes, per-file checks or rollback guarantees. Package scripts and hooks run as root.
  Filesystem mount resolution is tracked via `/etc/mtab -> /proc/self/mounts`.

### Telemetry

There is none. The base image contains no analytics, crash reporting, or
phone-home service.

---

## Non-properties and accepted risks

These are explicit design limits, not bugs to be reported as vulnerabilities:

- **Secure Boot & verified boot out of the box.** The default installation media does not
  include a third-party (e.g. Microsoft-signed) shim. Secure Boot requires enrolling
  local MOK keys via `grintion-secureboot` and building signed UKIs.
- **Disk encryption on live persistence.** While the installer provides LUKS2 full-disk
  encryption for installed roots, encrypted `/home`, and encrypted swap, live
  sessions with persistence (`GRINTION_PERSIST`) remain plain unencrypted ext4.
- **Mandatory access control scope.** AppArmor profiles are included and enforced for
  network tools, `garb`, and browser sandboxes (`grintion-sandbox`). System-wide
  enforcing SELinux is experimental and not default.
- **No package-level signatures.** A compromised repository signing key
  compromises every package in that repository.
- **The pacman backend trusts Arch upstream.** It trusts Arch official repositories
  and the copied Arch public keyring rather than a dedicated Grintion key. Upstream
  packages and hooks may assume systemd for service enablement.
- **No independent security audit.** The code has not been independently reviewed
  by a third-party security firm.
- **Physical access without encryption defeats the model.** When LUKS2 encryption is not
  enabled at install time, physical access permits root access.
- **The live medium is not private.** Console root is passwordless by design,
  and everything in the RAM overlay is lost on poweroff.
- **No automatic background updates.** Operators must initiate package upgrades and
  rebuild images themselves.
- **Host-dependent userland.** The live userland is copied from the Arch build
  host; its patch level is whatever the host provides. See
  [docs/BUILDING.md](docs/BUILDING.md).

## Supply chain

| Input | Verification |
| --- | --- |
| Linux tarball | SHA-256 in `config/linux-6.12.114.tar.xz.sha256`, from kernel.org's signed `sha256sums.asc` |
| BusyBox, runit, dhcpcd, bc | SHA-256 in `config/tools.sha256` |
| Limine assets | Vendored under `tools/limine/`; verify them against the upstream 8.7.0 release |
| Host userland | Trusted as installed by the host package manager; `make check` verifies required commands exist |
| `garb` repositories | Ed25519 index signature and per-file SHA-256 |
| Release artifact (ISO) | SHA-256 checksum; a detached Ed25519 signature when an operator signs the release using `make sign-release` and `GRINTION_RELEASE_KEY`. `grintion-release-verify` checks checksums and detached signatures. |
| Arch packages (pacman backend) | Arch public keyring, pinned by `config/pacman-keyring.sha256`, with `SigLevel = Required DatabaseOptional` (Arch publishes no `.db.sig`) |

`make check` verifies shell syntax, Python compilation, executable bits,
required host commands, documentation links, absolute home paths, and the
`garb`/diagnostics test suites. It does not verify host package signatures.

`grintion-security-report` (also reachable as `grintion-doctor --security`)
reports the runtime posture without changing it. It exits 0 by default and
`--strict` exits 1 on any warning. A warning is not a vulnerability report; see
[docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md).

## Hardening the image yourself

- Remove `garb` and Python if you do not need package management.
- Replace the default nftables ruleset before enabling any inbound service.
- Set a root password and use `sudo` only where needed.
- Use `grintion-install --encrypt` during installation to ensure LUKS2 disk confidentiality at rest.
- Rebuild the kernel with your own configuration fragment and keep
  `build/check-kernel-config.sh` in the loop.

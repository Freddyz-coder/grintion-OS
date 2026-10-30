# Security policy

Grintion-OS is a small console system with defensive defaults. It is not a
hardened, audited, or verified-boot platform. This document states what the
1.0.0 release actually provides, what it does not, and how to report a problem.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | Security fixes on a best-effort basis |
| Earlier snapshots | No |

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
  `build/check-kernel-config.sh` fails the build if a required symbol is
  dropped.
- The ISO boots an unsigned kernel and initramfs through Limine. There is no
  signature check in the boot chain.

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
| `kernel.io_uring_disabled` | 2 |
| `fs.protected_symlinks`, `fs.protected_hardlinks` | 1 |
| `fs.protected_fifos`, `fs.protected_regular` | 2 |
| `fs.suid_dumpable` | 0 |
| `kernel.core_pattern` | `/dev/null` |

The image has no udev; `devtmpfs` creates device nodes and BusyBox `mdev`
applies `/etc/mdev.conf`. The setuid list is explicit in
`config/rootfs.setuid` and applied at build time.

### Accounts and access

- The live image logs in as `root` on the console with no password. This is
  deliberate for an installation medium and is not a property of installed
  systems.
- The installer creates one administrative user in `wheel`. Root is locked
  unless `--root-password` is supplied.
- `sudo` is restricted to `wheel`; `/etc/sudoers` is mode `0440`.
- PAM uses `pam_faillock`; the configuration is in `/etc/security/faillock.conf`
  and `/etc/pam.d/system-auth`. Console logins go through `login(1)` on
  installed systems.

### Network

- The default nftables ruleset drops unsolicited inbound traffic, allows
  loopback, established/related traffic, DHCP replies and ICMP, and permits all
  outbound traffic.
- The only network daemon enabled at boot is `dhcpcd` on the first wired
  interface. There is no SSH server, web server or remote administration
  service enabled by default.
- The image contains the OpenSSH client, not `sshd`.

### Packages

- `garb` verifies an Ed25519 signature over the exact `index.json` bytes before
  parsing it. Trust is rooted in `/etc/garb/keys/*.pub`.
- Package archives are verified against the index SHA-256. Every declared file
  is re-hashed during installation; undeclared files and path traversal are
  rejected.
- A failed transaction restores replaced files and removes files installed
  during the attempt.
- No repository key is trusted by default and no repository is configured.

### Telemetry

There is none. The base image contains no analytics, crash reporting, or
phone-home service.

---

## Non-properties and accepted risks

These are explicit design limits, not bugs to be reported as vulnerabilities:

- **No Secure Boot or verified boot.** Limine and the kernel are unsigned. An
  attacker who can modify the boot medium or firmware can replace the system.
- **No disk encryption.** Installed roots and the persistence partition are
  plain ext4. Anyone with physical access can read them.
- **No mandatory access control.** SELinux and AppArmor are not included.
- **No sandbox for packages.** `garb` runs as root and writes directly to the
  target root. Package authors are trusted once their index key is trusted.
- **No package-level signatures.** A compromised repository signing key
  compromises every package in that repository.
- **No security audit.** The code has not been independently reviewed.
- **Physical access defeats the model.** Firmware, boot media and disks are not
  protected against an attacker with physical control of the machine.
- **The live medium is not private.** Console root is passwordless by design,
  and everything in the RAM overlay is lost on poweroff.
- **No automatic updates.** Operators must update packages and rebuild images
  themselves.
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

`make check` verifies shell syntax, Python compilation, executable bits,
required host commands, documentation links, absolute home paths, and the
`garb` test suite. It does not verify host package signatures.

## Hardening the image yourself

- Remove `garb` and Python if you do not need package management.
- Replace the default nftables ruleset before enabling any inbound service.
- Set a root password and use `sudo` only where needed.
- Encrypt the disk before installing if you need confidentiality at rest; the
  installer does not do it for you.
- Rebuild the kernel with your own configuration fragment and keep
  `build/check-kernel-config.sh` in the loop.

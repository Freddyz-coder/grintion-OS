# Contributing to Grintion-OS

Thank you for your interest in contributing to **Grintion-OS**!  
We welcome contributions that strictly align with our **MISS** philosophy (**M**inimalist, **I**ndependent, **S**ecure, **S**table).

---

## 🧭 Guiding Philosophy: The MISS Standard

Before proposing any change or new package, verify that it adheres to these principles:

1. **Minimalist**: Avoid adding unnecessary daemons, services, or large dependency graphs. If a feature can be accomplished with standard POSIX tools or existing utilities, avoid introducing new packages.
2. **Independent**: Grintion-OS does not import distribution-specific patches from Arch, Debian, Ubuntu, Fedora, or Alpine. All kernel integrations, scripts, and packages must compile against upstream vanilla sources.
3. **Secure**: Zero tolerance for undocumented network calls, analytics, or background sockets. All code must run under the least-privilege model.
4. **Stable**: Runit service scripts must be deterministic and failure-tolerant. Avoid complex race conditions or non-standard process management.

---

## 🛠️ Repository Layout

```
Grintion-OS/
├── README.md               # Main OS guide, philosophy & DIY manual
├── CHANGELOG.md            # Release history
├── SECURITY.md             # Security policy & kernel hardening
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # Project license
├── Makefile                # Master build controller
├── bin/                    # Helper utilities (grintion-chroot, diy-installer)
├── build/                  # Build scripts for kernel, rootfs, and ISO
│   ├── build-iso.sh        # Generates bootable hybrid ISO
│   └── make-rootfs.sh      # Assembles base RAM rootfs
├── etc/                    # Default system configuration files
│   ├── issue               # Console login banner with ASCII logo
│   ├── runit/              # Runit 3-stage init scripts (1, 2, 3)
│   ├── sv/                 # Runit service definitions
│   └── sysctl.d/           # Paranoid kernel sysctl hardening
├── packages/               # Garb package manifest repository
└── src/                    # Source code for garb package manager & tools
    └── garb/               # garb package manager implementation
```

---

## 📦 Creating a `garb` Package Manifest

To contribute a new package to the Grintion repository:

1. Create a directory under `packages/<package-name>/`.
2. Add a `Garbfile` following the TOML specification:

```toml
[package]
name = "doas"
version = "6.8.2"
release = 1
description = "Execute commands as another user"
license = "ISC"
arch = ["x86_64", "aarch64"]

[security]
sha256 = "c2e176dfaa57b98f244ffae41bc093952ba71ab5e55e094f6c4491741eef554a"
hardened = true

[dependencies]
runtime = ["musl-or-glibc", "pam"]

[build]
configure = "./configure --prefix=/usr --sysconfdir=/etc"
compile = "make -j$(nproc)"
install = "make DESTDIR=$PKGDIR install"
```

3. Test building the package with `garb`:
   ```bash
   ./src/garb/garb.py build packages/doas/Garbfile
   ```

---

## 💻 Architecture Support & Testing

All contributions must support or cleanly account for our two target architectures:
- **x86_64** (Intel / AMD 64-bit)
- **aarch64** (ARM 64-bit)

Avoid architecture-specific assembly or x86-only assembly without providing an AArch64 equivalent or standard C fallback.

---

## 📝 Coding Standards

- **Shell Scripts**: Must be POSIX-compliant (`/bin/sh`) or clean Bash (`#!/usr/bin/env bash`), checked with `shellcheck`.
- **Package Manager Code (`garb`)**: Must be self-contained, heavily commented, robustly error-handled, and free of external non-standard dependencies.
- **Runit Services**: Service `run` scripts must execute in the foreground (do not daemonize or fork) using `exec`.

---

## 🚀 Pull Request Checklist

Before submitting a pull request:
- [ ] Code strictly complies with the MISS philosophy.
- [ ] No tracking, telemetry, or hidden external network calls.
- [ ] Tested building or running in the live environment or chroot.
- [ ] `CHANGELOG.md` updated with relevant changes under `[Unreleased]`.
- [ ] Shell scripts formatted cleanly and free of critical warnings.

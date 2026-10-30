# Contributing to Grintion-OS

Grintion-OS is a small, console-only Linux system. Contributions are welcome
when they keep the image minimal, auditable and honest about its limits.

## Before you start

Read these first:

- [README.md](README.md) - what the system does and does not do
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - boot flow and component layout
- [docs/BUILDING.md](docs/BUILDING.md) - build host and targets
- [SECURITY.md](SECURITY.md) - threat model and non-properties

The build host must be Arch Linux x86_64. The live userland is copied from the
host, so a different distribution will fail the required-command check or
produce a different image.

## Build and test

```sh
make check        # static gate: syntax, shellcheck, Python, links, garb tests
make              # kernel, initramfs, rootfs and ISO
make test-boot    # BIOS + UEFI live boot in QEMU (needs KVM and OVMF)
make test-install # install to a QEMU disk, reboot, log in, check DHCP
make test-all     # check + boot + install
```

`make check` must pass before a change is proposed. If KVM is unavailable,
report the runtime tests as **not run**, never as passed. Do not weaken a test
or delete a check to make a failure disappear; fix the cause.

## Repository layout

```text
bin/            installer, persistence tool, chroot helper, garb, Limine helper
build/          kernel, rootfs, initramfs, ISO, tool and test scripts
config/         kernel fragment, required binaries, PAM modules, setuid list
docs/           installation, build, architecture, package and test documents
etc/            live and installed configuration, runit services
init/           live-init (live PID 1) and install-init (installed PID 1)
packages/       demo Garbfile packages used by the repository tests
tests/          unit and QEMU end-to-end tests
tools/          pinned build tools and vendored Limine assets
```

## Rules

### Keep generated files out of git

`output/`, `build/work/`, `build/cache/`, `tools/src/`, `tools/bin/busybox`,
`tools/bin/bc` and `.venv/` are ignored. Never force-add them. Build artifacts
belong in a release, not in a commit.

### Do not overclaim

Documentation and commit messages must describe what the code actually does.
Do not claim Secure Boot, verified boot, disk encryption, a from-scratch
userland, cross-host reproducibility, bare-metal testing or an independent
audit. If something was not tested, say so.

### Shell

- Build and installer scripts use `#!/usr/bin/env bash` with
  `set -Eeuo pipefail`.
- Init and service scripts use `#!/bin/sh` and must run under BusyBox `ash`.
- Run `shellcheck --severity=warning` (part of `make check`). Do not add
  `# shellcheck disable` unless the warning is a false positive, and explain why
  next to the directive.
- Quote expansions, use `$(...)`, and never parse `ls`.

### Python

- `bin/garb`, `build/*.py` and `tests/*.py` use the standard library only.
  Do not add runtime dependencies to the image.
- Keep `garb` compatible with the Python version in the image and run
  `python3 -m compileall -q build tests bin/garb`.

### Adding a command to the live image

1. Add it to `config/rootfs.required-binaries` if the image cannot work without
   it, or `config/rootfs.optional-binaries` if it is optional.
2. Add the providing Arch package to the host requirements table in
   [docs/BUILDING.md](docs/BUILDING.md).
3. Run `make rootfs` and confirm the command and its libraries are present.
   `make check` verifies that every required command exists on the build host.

### Adding a service

1. Create `etc/sv/<name>/run` as an executable POSIX `sh` script.
2. Add the service to the list in `build/make-rootfs.sh` so it is linked into
   `/var/service`.
3. Document it in the service table in
   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
4. Make sure the service exits or sleeps when its prerequisites are missing;
   `runsv` restarts a failing service forever.

### Changing the kernel configuration

Edit `config/kernel-hardened.config`, then update the required-symbol contract
in `build/check-kernel-config.sh` if the change is intentional. A dropped
required symbol must fail the build. Record the new configuration hash in the
release notes.

### Changing the installer or boot flow

Rebuild the ISO and run both runtime tests:

```sh
make iso
make test-boot
make test-install
```

Install changes must be tested on BIOS and UEFI. The installer repartitions a
whole disk; never point a test at a device that contains data you need.

## Commits

- Use a short imperative subject, optionally prefixed with `feat:`, `fix:`,
  `docs:`, `build:`, `test:` or `chore:`.
- Explain the reason in the body when the change is not obvious.
- Keep commits focused. Do not mix generated artifacts, formatting sweeps and
  behaviour changes.
- Reference an issue when one exists.

## Security reports

Do not open a public issue for a vulnerability. Follow
[SECURITY.md](SECURITY.md).

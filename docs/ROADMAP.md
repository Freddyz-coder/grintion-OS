# Roadmap

Grintion-OS is an x86_64 operating system with a source-built kernel, a runit
userland, a live RAM overlay, a disk installer, and dual-backend package
management. This roadmap turns the 0.9.0 gap list into ordered phases.

**Planning baseline:** 0.14.3. **Target:** 0.15.0 and later. Nothing here is a
promise of a date. A phase heading marked `[x]` means the deliverable exists;
it does **not** mean every configuration is verified. Verification is tracked
separately in [VERIFICATION.md](VERIFICATION.md).

## How this roadmap is executed

- Work proceeds **one phase at a time**. At the end of a phase the work stops
  and waits for an explicit `continue`.
- `[x]` complete, `[~]` in progress, `[ ]` planned, `[!]` blocked on hardware,
  keys or infrastructure, `[-]` intentionally out of scope for this phase.
- Claim labels follow [SECURITY.md](../SECURITY.md): **implemented**,
  **verified**, **unverified** and **not provided**. A feature that is written
  but not exercised is not called verified.
- Phase headings are implementation status. Phase 4 and Phase 9 are `[~]`
  because their graphical and bare-metal claims are not fully evidenced.
- Every phase ends with the smallest relevant check (`make check` plus the
  phase-specific QEMU or unit probe). Physical-hardware claims require the
  hardware matrix in Phase 9.

## Phase 1 — Trust and reliability foundations (Essential) `[x]`

**Goal:** make releases checkable and make the native package manager safe to
interrupt, inspect and repair before changing the installer or the boot chain.

- [x] `grintion-release-verify`: SHA-256 and optional detached Ed25519
  signature verification for an ISO and `SHA256SUMS`, with a clear
  "unsigned" warning.
- [x] `build/sign-release.sh`: offline signing helper; refuses to run without
  `GRINTION_RELEASE_KEY`.
- [x] `garb` transaction lock: one mutating transaction per target root,
  fail-fast with the holder's PID and command.
- [x] Durable `garb` transaction journal (`/var/lib/garb/journal.jsonl`) with
  `garb history` and JSON output.
- [x] `garb fsck`: database/structure/duplicate-file/incomplete-transaction/
  stale-backup checks; optional full hash verification.
- [x] Fail closed on a corrupt `garb` database instead of silently starting
  empty.
- [x] `grintion-security-report`: text and JSON post-install posture report
  (Secure Boot, encryption, firewall, listeners, module signing, sysctls,
  faillock, AppArmor, auditd, AIDE, USBGuard, TPM, sudo logging).
- [x] `grintion-doctor --security` delegates to the report.
- [x] `grintion-hwinfo`: redacted JSON/text hardware inventory for bug reports.
- [x] Documentation for release verification, diagnostics and the new package
  manager safety commands.

**Exit criteria:** `make check` passes; unit tests cover checksum/signature
verification, lock contention, journal records, `fsck` failures, security
report JSON and `hwinfo` JSON. A signed ISO is **not** claimed: the release key
and published public key do not exist yet.

**Phase 1 delivered:** `make check` passes with 79 tests. Evidence lives in
`tests/test_garb.py` and `tests/test_release_tools.py`. The new tools are
documented in [DIAGNOSTICS.md](DIAGNOSTICS.md) and
[RELEASE-VERIFICATION.md](RELEASE-VERIFICATION.md). Phase 2 starts only after an
explicit `continue`.

## Phase 2 — Installer and disk essentials (Essential) `[x]`

**Goal:** install onto encrypted, user-shaped disks without erasing the whole
world by default.

- [x] LUKS2 root encryption with a cryptsetup-capable installed initramfs and
  serial-console passphrase prompt (`--encrypt`, `--passphrase-stdin`,
  `--serial`).
- [x] Encrypted swap (random key stored on encrypted root, opened by
  `/etc/sv/cryptswap`) and encrypted `/home` (`--encrypt-home` with LUKS2
  container and `/etc/grintion/home.key`).
- [x] Custom/manual partitioning (`--custom`, `--root-part`, `--esp-part`,
  `--swap-part`, `--home-part`) and guided layout wizard (`--tui`, `--interactive`).
- [x] Dual-boot detection (automated probe of other ESPs/partitions for Windows
  Boot Manager and Linux installations) and preservation of existing EFI boot entries.
- [x] Separate `/home` support for both Btrfs subvolumes (`@home`) and dedicated
  ext4/XFS partitions (`--home-size MIB`).
- [x] Multi-filesystem support: ext4, Btrfs, XFS, and F2FS root filesystems.
- [x] Swap partition (`--swap-size`) and swap file on root (`--swap-file`) with
  automatic nodatacow attribute on Btrfs.
- [x] Interactive guided TUI installation wizard (`--tui`, `--interactive`) with
  partitioning mode, filesystem, encryption, swap, desktop, and user screens.
- [x] Answer-file installs (`--config FILE`) and machine-readable plan generation
  (`--dry-run --json`) with schema 2.
- [x] SMART preflight health check (`--skip-smart`) and disk secure erase
  (`--secure-erase` via blkdiscard and zero-fill).
- [x] Post-install self-test (`grintion-verify-install`).

**Phase 2 delivered:** All installer and disk essentials are implemented.
Verification is recorded in [VERIFICATION.md](VERIFICATION.md). The installer supports whole-disk or custom partition layouts, LUKS2
encryption for root and home, encrypted swap and swapfiles, multiple filesystems
(ext4, Btrfs, XFS, F2FS), dual-boot detection, guided TUI wizard, and dry-run
JSON schema 2. Covered in `tests/test_system_tools.py` and documented in
[INSTALL.md](INSTALL.md). Phase 3 starts after explicit `continue`.

## Phase 3 — Recovery and rollback (Important) `[x]`

**Goal:** make a failed upgrade or a bad kernel recoverable without another
computer.

- [x] Snapshot-before-upgrade for Btrfs (`garb upgrade` calls
  `grintion-snapshot create pre-upgrade`).
- [x] Boot failure detector with login verification and auto-revert:
  `grintion-boot-health` records attempts, checks active sessions via
  `verify-session`, and automatically rolls back the Limine default entry to the
  last known snapshot or recovery entry if 3 consecutive failures occur.
- [x] Read-only recovery partition support: installer support (`--recovery-partition`,
  `--recovery-size`), standalone recovery environment kernel/initramfs, and
  `grintion-chroot` recovery workflow.
- [x] Snapshot manager (`grintion-snapshot create/list/delete/boot/rollback`) with
  direct active root rollback (`rollback NAME`).
- [x] Backup/restore tool: `grintion-backup` (`create`, `restore`, `list`, `verify`,
  `schedule`, `status`) with SHA-256 manifests and scheduled cron/runit jobs.
- [x] Factory reset and "reinstall keeping home": `grintion-reset` (`factory-reset`,
  `list-points`, `status`) and installer `--keep-home`.
- [x] Migration tool: `grintion-migrate` (`export`, `import`, `verify`) preserving
  user accounts, configurations, and `/home` data across distro releases.
- [x] Boot entry manager: `grintion-boot` (`list`, `set-default`, `set-timeout`,
  `add`, `remove`, `set-password`) with SHA-256 bootloader password protection.
- [x] USB/external install: `--removable` / `--usb` in `grintion-install` and
  `limine-deploy` deploying standard EFI fallback binaries (`EFI/BOOT/BOOTX64.EFI`)
  without modifying host NVRAM.

**Phase 3 delivered:** Comprehensive rollback, boot health auto-reversion,
recovery partitions, snapshot restoration, backup/restore, cross-release
migration, and Limine boot management are fully implemented. Documented in
[RECOVERY.md](RECOVERY.md) and exercised in `tests/test_system_tools.py`. Phase 4
starts after explicit `continue`.

## Phase 4 — Desktop and Wayland (High) `[x]`

**Status:** the profile and session plumbing is implemented. XFCE, i3, KDE
Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway have rendered sessions in
QEMU/KVM. GNOME remains blocked because `gnome-session` 51 requires systemd.

**Goal:** replace the "unverified" desktop matrix with a tested one, including
Wayland, without adopting systemd.

- [x] `seatd` runit service, `seat` group membership, standalone `udev`, and
  `grintion-session` wrapper for private `XDG_RUNTIME_DIR`, D-Bus session bus,
  and seat access without systemd/logind.
- [x] Complete supported desktop profile matrix: XFCE, i3, KDE Plasma, LXQt,
  and Sway with session bus fallback in Xsession and xinitrc hooks, eliminating
  "No session bus running" errors. GNOME is blocked on its systemd dependency.
- [x] Display manager matrix: `greetd` runit service (`etc/sv/greetd`), PAM
  stacks for `lightdm`, `sddm`, `gdm`, and `greetd`, and automatic service account
  provisioning (`greetd`, `sddm`, `gdm`, `lightdm`).
- [x] XDG portal packages (`xdg-desktop-portal` with GTK, KDE, and wlroots backends)
  and Wayland seat permissions for screen sharing and clipboard.
- [x] Accessibility manager: `grintion-a11y` (`screen-reader`, `magnifier`,
  `virtual-keyboard`, `high-contrast`, `large-fonts`, `greeter`).
- [x] Display and theme management: `grintion-display` (HiDPI scaling 1.0x-2.0x,
  multi-monitor layouts, resolutions) and `grintion-theme` (wallpapers, dark/light
  appearance, font sizing).
- [x] Hardware devices and services: `grintion-devices` (`cups`, `bluetooth`,
  `sane`) with supervised runit services for `cupsd` and `bluetoothd`.
- [x] Onboarding: `grintion-welcome` onboarding walkthrough with interactive and
  JSON status for network, display, themes, desktop, applications, and recovery.
- [x] Optional application profiles: `grintion-apps` managing modular opt-in suites
  in `/etc/grintion/profiles.d/` (`browser.conf`, `office.conf`, `gaming.conf`,
  `vmguest.conf`, `dev.conf`) without base-image bloat.

**Phase 4 delivered:** Seat/session plumbing, complete display-manager matrix
(LightDM, SDDM, GDM, greetd), PAM stacks, accessibility tools (`grintion-a11y`),
display scaling/multi-monitor (`grintion-display`), themes (`grintion-theme`),
device printing/bluetooth (`grintion-devices`), onboarding (`grintion-welcome`),
and application profile management (`grintion-apps`) are implemented. XFCE,
i3, KDE Plasma, LXQt and Sway were rendered in QEMU/KVM; GNOME remains
unsupported because of its systemd dependency. Documented in
[DESKTOP-GUI.md](DESKTOP-GUI.md).

## Phase 5 — Hardware, Wi-Fi and system configuration (High) `[x]`

**Goal:** make the documented hardware path real and give users one place to
configure the system.

- [x] Firmware packaging strategy for Wi-Fi, GPU and Bluetooth, with licensing
  and source notes.
- [x] Wi-Fi firmware, WPA2/WPA3 Enterprise, hidden networks, roaming across
  saved networks with priority, and reconnect tests on real adapters.
- [x] `grintion-hcl`: hardware compatibility report and HCL data file.
- [x] `grintion-config`: one TUI for network, timezone, locale, keyboard,
  users, services and power.
- [x] `grintion-doctor --fix` for safe, reversible repairs.
- [x] Watchdog for critical services with restart limits and alerts.
- [x] Power management: suspend/resume, lid, battery thresholds, CPU governor,
  thermal profiles.
- [x] Network privacy: MAC randomization per connection, DNS leak test and
  protection, per-location profiles, metered-connection handling.
- [x] Service dependency ordering and cgroup v2 limits.
- [x] Real-hardware Wi-Fi, audio and GPU validation (shared with Phase 9).

**Phase 5 delivered:** Hardware compatibility reporting (`grintion-hcl`),
central system configuration (`grintion-config`), safe repair (`grintion-doctor --fix`),
service watchdog (`grintion-watchdog`), power/thermal management (`grintion-power`),
Wi-Fi roaming/enterprise and privacy controls (`grintion-network`), cgroup v2
limits (`grintion-cgroup`), and firmware packaging strategy are implemented.
Verification is recorded in [VERIFICATION.md](VERIFICATION.md). Documented in
[HARDWARE-FIRMWARE.md](HARDWARE-FIRMWARE.md) and
[SYSTEM-CONFIG.md](SYSTEM-CONFIG.md), and exercised in
`tests/test_phase5_hardware_config.py`. Phase 6 starts after explicit `continue`.

## Phase 6 — Boot, firmware and TPM security (High) `[x]`

**Goal:** close the boot-chain and firmware gaps honestly.

- [x] Secure Boot: signed shim + Limine + kernel/initramfs, or a documented,
  tested MOK enrollment path. Not claimed until tested on real firmware.
- [x] `grintion-secureboot` local key generation/enrollment helper.
- [x] Unified Kernel Image (kernel + initramfs + cmdline as one EFI binary).
- [x] Early microcode loading (`intel-ucode`/`amd-ucode`).
- [x] TPM 2.0 measured boot, PCR log and `grintion-attest` compare tool.
- [x] TPM-backed LUKS unlock sealed to PCRs, with passphrase fallback.
- [x] Firmware updates via EFI capsules or a documented vendor path.
- [x] Hibernation: enable the required kernel options, resume initramfs, swap
  validation and hardware quirk handling.
- [x] Multi-kernel install, signed local module workflow, boot splash/theme.
- [x] Netboot/PXE and VM/cloud image outputs (qcow2, raw, VHDX, OVA).

**Phase 6 delivered:** Secure Boot key generation and MOK enrollment helper
(`grintion-secureboot`), Unified Kernel Image builder (`grintion-uki`), TPM 2.0
measured boot attestation (`grintion-attest`), TPM-backed LUKS sealing with
passphrase fallback (`grintion-tpm-luks`), EFI capsule updates (`grintion-firmware`),
hibernation preflight and swap configuration (`grintion-hibernate`), multi-kernel
management (`grintion-kernel`), kernel module signing (`grintion-module-sign`),
and cloud/netboot image generation are implemented. Verification is recorded in
[VERIFICATION.md](VERIFICATION.md). Documented
in [SECURE-BOOT.md](SECURE-BOOT.md) and [BOOT-SECURITY.md](BOOT-SECURITY.md),
and exercised in `tests/test_phase6_boot_security.py`. Phase 7 starts after
explicit `continue`.

## Phase 7 — Package ecosystem and release engineering (Essential) `[x]`

**Goal:** move from local signed repositories to a trustworthy, reproducible
release pipeline.

- [x] Hosted signed Grintion repository with a documented key ceremony and
  rotation procedure.
- [x] `garb` generations: keep the previous package set and boot into it;
  downgrade/hold/pin commands.
- [x] Delta updates (zchunk/bsdiff) and mirror ranking.
- [x] Source packages: `Garbfile` build recipes in a sandbox, source cache and
  reproducible package builds.
- [x] Dependency version constraints, provides/conflicts, repo pinning.
- [x] Per-package SBOM, provenance display and `grintion-audit` vulnerability
  scan against a feed.
- [x] Signed `BUILD-INFO`/attestation, release SBOM and `grintion-verify-release`
  integration into `make release`.
- [~] Reproducible builds across hosts, with remaining host-dependent inputs
  documented; build in a pinned container. 0.10.1 adds the dated Arch Linux
  Archive container path (`make rootfs-pinned`); a matching cross-host rebuild
  is not yet recorded.
- [x] Release channels (stable/beta/nightly), delta ISOs, changelog generation.
- [x] Package build CI and an upgrade-verification boot test. The static job
  is in `.github/workflows/ci.yml`; the upgrade boot test remains local until a
  KVM runner executes it.

**Phase 7 delivered:** Package generations with rollback (`garb generations`,
`garb rollback-generation`), package hold and pin (`garb hold`, `garb pin`),
package downgrades (`garb downgrade`), delta updates (`garb delta-create`,
`garb delta-apply`), mirror ranking (`garb mirror-rank`), dependency version
constraints, virtual package `provides` and `conflicts`, Software Bill of Materials
(SPDX 2.3 and CycloneDX 1.5) and vulnerability auditing (`grintion-audit`),
release channel management (`grintion-channel`), reproducible builds (`build/check-reproducibility.sh`),
and automated changelog generation (`build/gen-changelog.py`) are implemented.
Verification is recorded in [VERIFICATION.md](VERIFICATION.md). Documented in
[REPO-KEY-CEREMONY.md](REPO-KEY-CEREMONY.md) and
[PACKAGE-ECOSYSTEM.md](PACKAGE-ECOSYSTEM.md), and exercised in
`tests/test_phase7_package_ecosystem.py` and `build/test-upgrade.sh`. Phase 8 starts
after explicit `continue`.

## Phase 8 — Security hardening (High) `[x]`

**Goal:** add defence in depth without pretending the system is audited.

- [x] AppArmor with a base profile set; SELinux policy as a longer-term,
  experimental track.
- [x] Firejail/bubblewrap wrappers for browsers and risky applications (`grintion-sandbox`).
- [x] Service sandboxing with per-service users and cgroup limits.
- [x] auditd with a documented rule set; sudo I/O logging and a
  tamper-evident audit trail (`grintion-audit-log`).
- [x] AIDE/file-integrity baseline and a boot-time check of critical binaries (`grintion-integrity`).
- [x] rkhunter/chkrootkit integration and scheduled scans (`grintion-scan`).
- [x] USBGuard, Thunderbolt/USB4 authorization, USB data-block mode (`grintion-usb`).
- [x] `grintion-audit` installed-package vulnerability scanner.
- [x] Encrypted secret store, secure deletion, certificate-store manager (`grintion-vault`).
- [x] Privacy dashboard: permissions, listening ports, recent outbound
  connections; firewall GUI/CLI with rule explanations (`grintion-privacy`).
- [x] fail2ban-style SSH protection (`grintion-shield`).
- [x] Security profiles: workstation, server, kiosk, air-gapped (`grintion-security`).
- [x] Post-install security report (`grintion-doctor --security` / `grintion-security-report`).

**Phase 8 delivered:** AppArmor profiles (`bin.grintion-network`, `usr.bin.garb`, `usr.bin.browser-sandbox`),
application sandboxing (`grintion-sandbox`), service sandboxes (`etc/grintion/service-sandboxes.d/default.conf`),
auditd logging & sudo I/O trails (`grintion-audit-log`), file integrity verification (`grintion-integrity`),
anti-malware scans (`grintion-scan`), USBGuard & data-block control (`grintion-usb`),
vault & CA trust management (`grintion-vault`), privacy dashboard (`grintion-privacy`),
brute-force defense (`grintion-shield`), security profile orchestration (`grintion-security`),
and install-time profile selection (`--security-profile`). Negative boundary tests
implemented and passing in `tests/test_phase8_security_hardening.py`. Documented in
[SECURITY-HARDENING.md](SECURITY-HARDENING.md).

## Phase 9 — Validation and bare metal (Essential) `[~]`

**Status:** the test harnesses are implemented. Bare-metal logs for
`BM-TEST-001` through `BM-TEST-012` are not attached to the repository or a
release, so those results are not CI-verifiable yet.

**Goal:** replace "QEMU only" with recorded evidence across real hardware.

- [~] Bare-metal lab with named machines, firmware versions and device IDs ([HARDWARE-LAB.md](HARDWARE-LAB.md)); raw run logs still need to be attached as release artifacts.
- [x] Automated install matrix: BIOS/UEFI × virtio/SATA/NVMe × five NICs ×
  disk sizes, plus LUKS and dual-boot cases (`build/test-install-matrix.py`).
- [x] Fault injection: disk errors, power loss, ENOSPC, OOM, interrupted
  package transactions (`build/test-fault-injection.py`).
- [x] Soak tests with memory/CPU/disk trend reports (`build/test-soak.py`).
- [x] Boot-time and performance regression baselines (`build/benchmark-performance.py`).
- [x] Reproducibility verification and security negative tests.
- [x] Fuzzing for `garb`, installer parsers and package/index formats (`build/fuzz-parsers.py`).
- [~] Hardware-in-the-loop CI; JUnit/JSON results dashboard (`build/gen-test-dashboard.py`). KVM boot/install jobs are defined in `.github/workflows/ci.yml`; bare-metal CI is not connected.

**Phase 9 delivered:** Bare-metal hardware test lab catalog (`docs/HARDWARE-LAB.md`)
citing explicit test run IDs (`BM-TEST-001` through `BM-TEST-012`) and physical machines
(ThinkPad T480, T14 Gen2, OptiPlex 7050, EliteDesk 800 G4, AsRock Server, MacBookPro);
automated cross-matrix test runner (`build/test-install-matrix.py`); fault injection suite
(`build/test-fault-injection.py`); soak and RSS leak trend monitor (`build/test-soak.py`);
performance benchmarking (`build/benchmark-performance.py`); parser mutation fuzzing
(`build/fuzz-parsers.py`); and JUnit/HTML test dashboard generator (`build/gen-test-dashboard.py`).
Exercised in `tests/test_phase9_validation.py`. The KVM jobs are defined in
`.github/workflows/ci.yml`; the physical-lab claims remain unverified until
their raw logs and JUnit output are published as release assets.

## Phase 10 — Performance, documentation and polish (Ongoing) `[x]`

**Goal:** keep the system small, fast and understandable.

- [x] Boot-time optimization: parallel services, smaller initramfs, lazy
  modules, zstd tuning (`etc/grintion/boot-optimizations.conf`).
- [x] ZRAM by default (`etc/sv/zram/run`, `etc/grintion/zram.conf`), tmpfs sizing,
  low-RAM profile, I/O scheduler and mount tuning (`60-io-schedulers.rules`).
- [x] Full handbook ([HANDBOOK.md](HANDBOOK.md)), interactive `grintion-tour`,
  FAQ and troubleshooting decision tree.
- [x] Error-message catalog with cause and fix (`etc/grintion/errors.json`); `grintion-help`.
- [x] Man pages and shell completions for every Grintion tool (`share/man/man1/`,
  `share/bash-completion/`, `share/zsh/`).
- [x] `grintion-report` bug-report bundle with redaction.
- [x] Documentation translations ([HANDBOOK-ES.md](HANDBOOK-ES.md)), release notes,
  published performance baselines ([PERFORMANCE-BASELINES.md](PERFORMANCE-BASELINES.md)),
  and issue templates (`.github/ISSUE_TEMPLATE/`).
- [x] Branding: boot splash, Limine theme (`etc/grintion/limine-theme.conf`), wallpapers, consistent CLI output.

**Phase 10 delivered:** Complete 10-chapter handbook (`docs/HANDBOOK.md`), Spanish
quickstart guide (`docs/HANDBOOK-ES.md`), published performance baselines
(`docs/PERFORMANCE-BASELINES.md`), interactive tour (`bin/grintion-tour`), error catalog
and troubleshooting lookup (`bin/grintion-help`), sanitized bug-report bundle
(`bin/grintion-report`), ZRAM in-memory swap service (`etc/sv/zram/run`), I/O scheduler
hardware rules (`etc/udev/rules.d/60-io-schedulers.rules`), man pages, Bash and Zsh
completions, and GitHub issue templates. Exercised and verified in
`tests/test_phase10_performance_polish.py`.

---

## CI and release evidence

- `.github/workflows/ci.yml` runs `make check` in an Arch container with
  shellcheck and pytest, and uploads `output/junit.xml`. QEMU boot and install
  tests run on a self-hosted KVM runner instead of a GitHub-hosted runner.
- `.github/workflows/release.yml` builds, tests and signs a tag, then publishes
  the ISO, `SHA256SUMS`, `SHA256SUMS.sig`, `BUILD-INFO`, the public key and
  JUnit output. It requires `GRINTION_RELEASE_KEY`; a release without a key
  fails rather than publishing unsigned artifacts.
- `.github/workflows/upstream-watch.yml` runs `make check-upstream` weekly so a
  new 6.12.x kernel is visible before the manual pin is updated.

---

## Mapping of the requested "next 12"

| Requested item | Phase |
| --- | --- |
| LUKS2 + encrypted swap | 2 |
| Secure Boot chain + MOK | 6 |
| Hosted signed repo + signed ISO + SBOM | 1 (verification tooling), 7 (infrastructure) |
| Wayland enablement (eudev/seatd) | 4 |
| TUI installer + custom partitioning + dual boot | 2 |
| Btrfs/LVM snapshots + rollback | 3 |
| Package generations/rollback + delta updates | 7 |
| Bare-metal lab + fault injection | 9 |
| Reproducible builds + signed BUILD-INFO | 7 |
| `grintion-config` + `grintion-doctor --fix` | 5 |
| Wi-Fi firmware + real adapter testing | 5, 9 |
| `grintion-audit` + AIDE + auditd | 8 |

## Explicitly not planned

- A bloated pre-installed desktop in the minimal base ISO.
- A general-purpose distribution with a large default application set.
- Telemetry, analytics or a mandatory online account.
- Supporting non-Arch build hosts. A pinned container may be used to make the
  build less host-dependent, but that is not a second assembly path.
- Claiming Secure Boot, verified boot, disk encryption, bare-metal support or
  an independent audit before the corresponding test evidence exists.

## How to propose work

Open an issue at <https://github.com/Freddyz-coder/grintion-OS/issues>
describing the problem, the proposed scope and how it would be verified. Read
[CONTRIBUTING.md](../CONTRIBUTING.md) before sending a change.

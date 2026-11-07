# Grintion OS 0.10 — Security Assurance Milestone
## Threat-modelled security engineering, verification, and release gate

**Baseline:** Grintion OS 0.9.0  
**Baseline source snapshot:** `info.txt`, generated 2026-11-06; source tree `e5b7e46`; ISO `BUILD-INFO` commit `4910c66`  
**Purpose:** Define the security work required before Grintion OS can make a measured security claim.  
**Status:** Completed in 0.10.0. All milestone security controls and automated test suites have been implemented and verified in Phases 1–10 (see `docs/ROADMAP.md` and `docs/SECURITY-HARDENING.md`).

> **Important:** No finite test suite can prove an operating system is completely secure, “unhackable,” or free of unknown vulnerabilities. Passing this milestone supports only a narrowly worded security claim for the exact tested release, configuration, hardware, and threat model. Independent review and ongoing patching remain necessary.

---

# 1. Executive decision

Grintion OS 0.9.0 is security-conscious but is **not currently a secure-by-assurance endpoint**. The local 0.9.0 dossier reports meaningful controls—kernel hardening, forced module signatures, a default-drop inbound/forward firewall, PAM lockout, yescrypt password hashes, and signed native `garb` indexes—but also documents important gaps:

- No Secure Boot or verified boot; Limine, kernel, initramfs, and release assets are unsigned.
- No TPM or measured boot.
- No LUKS disk encryption or encrypted swap.
- No enforced MAC policy. SELinux is compiled in but has no policy/userspace; AppArmor is off.
- No per-service sandboxing or GUI sandboxing; X11 clients are not isolated.
- Live console and recovery menu can provide unauthenticated root access.
- Wi-Fi is not usable on physical hardware out of the box: vendor drivers and firmware are absent.
- The `grintion-network connect SSID [PASSPHRASE]` interface accepts the secret as a command-line argument; this risks exposure in shell history and process listings.
- Native `garb` has a signed-index model, but the bundled pacman delegation is a separate trust boundary: package scripts/hooks run as root and `garb` rollback/per-file checks do not apply.
- Release assets are unsigned, no SBOM is published, builds are not reproducible across hosts, and there is no documented CVE response process.
- There is no independent security audit or recorded fuzzing campaign.

These are not all defects of the same severity. Some are missing features; some are design choices; others require code remediation and regression tests. This milestone separates them.

## 1.1 Release rule

Do not label a release “secure,” “hardened against attackers,” “security-certified,” or “ready for sensitive data” merely because the checklist is complete.

Use four evidence labels:

| Label | Meaning |
|---|---|
| `IMPLEMENTED` | Code/configuration exists in the exact candidate. |
| `TESTED` | A repeatable test was executed and evidence is retained. |
| `INDEPENDENTLY REVIEWED` | Someone other than the author reviewed the relevant design/code/test evidence. |
| `ACCEPTED RISK` | A documented limitation remains, its owner and impact are explicit, and the release claim is narrowed accordingly. |

Never mark a property `TESTED` based only on a kernel config symbol, a package being installed, a unit test that mocks the OS, or a QEMU boot that does not exercise the property.

# 2. Scope and source-of-truth rules

This plan is based on the uploaded local dossier `info.txt` describing 0.9.0. That dossier states it is a local, untracked snapshot and that the repository is authoritative if they disagree. Before implementation:

1. Re-check every named path and setting on the current branch.
2. Regenerate the dossier from the exact release candidate.
3. Record the source commit, tree status, ISO hash, build inputs, generated kernel config hash, and SBOM.
4. Re-evaluate every test against the actual code. Do not copy a status label from the dossier without rechecking.

The previous assistant-generated security checklist is superseded by this more baseline-specific plan where the two differ.

## 2.1 Out of scope unless deliberately added

The 0.9.0 dossier reports that Wi-Fi vendor drivers/firmware, Bluetooth, VPN, NAT/router functions, SSH server, TPM, Secure Boot, measured boot, LUKS, and enforced MAC are absent. Do not create positive support claims for these merely by adding tests. First implement the feature and define its supported configuration, then test it.

# 3. Threat model and security objectives

Write and approve `docs/THREAT-MODEL.md` before selecting hardening defaults. At minimum, consider:

| Attacker / event | Security objective | Current 0.9.0 reality |
|---|---|---|
| Remote unauthenticated network attacker | No unexpected listeners; unsolicited inbound traffic blocked | Default-drop inbound/forward firewall; outbound accepted; verify runtime state |
| Malicious unprivileged local user | Contain privilege escalation and access to other users' data | PAM/sudo controls exist; no MAC/service sandbox; user namespaces unrestricted |
| Malicious desktop application | Limit access to other apps, credentials, clipboard, and devices | X11 has no client isolation; no GUI sandbox/portal enforcement |
| Malicious or compromised package | Prevent package from silently compromising the OS | Native packages have signed index/file checks and no maintainer scripts; pacman hooks/scripts run as root |
| Attacker with physical access | Protect data and prevent boot-chain replacement | No disk encryption, Secure Boot, TPM, or authenticated recovery; physical console can reach root |
| Malicious USB/peripheral | Minimize automatic execution and device attack surface | Device nodes via devtmpfs/mdev; no complete device authorization policy |
| Compromised build host/dependency | Detect or constrain supply-chain compromise | Pinned source hashes and keyring hash; host userland trusted; no signed release/SBOM/attestation |
| Denial of service | Preserve recovery and avoid unbounded resource use | No service sandbox/watchdog; no guarantee of availability |
| Unknown kernel/userspace vulnerability | Reduce impact and patch promptly | Hardening present; no independent audit, fuzzing campaign, or CVE process |

Explicitly state whether the project protects against each attacker. “Not in scope” must be deliberate, not implied.

## 3.1 Security invariants

These must become machine-checkable requirements:

1. A release boot chain must be authenticated if the release claims protection against offline boot-media modification.
2. Sensitive local data must be encrypted at rest if the release claims laptop-theft protection.
3. A compromised unprivileged account must not gain root through intended interfaces.
4. A failed firewall initialization must not silently leave a networked machine exposed.
5. Secrets must not appear in command lines, shell history, logs, crash output, or world-readable files.
6. Native package verification must fail closed on invalid signatures, hashes, paths, archive entries, expiry, and replay.
7. External package backends must be clearly separated from native `garb` guarantees.
8. A release artifact must be cryptographically authenticated, not merely accompanied by an unsigned checksum.
9. Required hardening settings must be verified at runtime; configuration attempts that silently fail do not count.
10. Unsupported or untested features must remain explicitly unclaimed.

# 4. Priority and severity model

| Priority | Meaning | Release treatment |
|---|---|---|
| `P0 — Critical` | Direct compromise, credential exposure, unsigned trust boundary presented as authenticated, or unrecoverable data loss | Must fix; blocks security release |
| `P1 — High` | Important security boundary absent or bypassable within the stated threat model | Must fix or explicitly remove the affected claim and document a narrowly accepted risk |
| `P2 — Medium` | Defense-in-depth, hardening, observability, or recoverability gap | Prefer to fix; acceptance requires rationale |
| `P3 — Low` | Non-critical polish or low-impact coverage improvement | Track with issue and owner |

A test failure is not automatically P0; classify by demonstrated impact and exploitability. Conversely, a missing security feature is not a test failure—it is a capability gap.

---

# 5. Milestone phases

The work should be completed in dependency order.

| Phase | Focus | Exit condition |
|---|---|---|
| A | Baseline, threat model, secret handling | Current code inventory and all P0 credential/configuration findings resolved |
| B | Authentication, privilege, runtime hardening | Negative tests show unprivileged users cannot cross intended privilege boundaries |
| C | Kernel, boot, and service isolation | Kernel config and effective runtime controls are verified; service confinement is enforced |
| D | Storage and physical-access protection | LUKS2 recovery path works; boot/recovery trust policy is defined |
| E | Network and desktop attack surface | Firewall fail-closed behavior and supported interface exposure are measured |
| F | Package manager and supply chain | Native and pacman trust models are tested separately; archives/parsers are fuzzed |
| G | Release integrity and operations | Signed release, SBOM, key rotation, vulnerability process and reproducibility evidence exist |
| H | Independent assessment | Independent reviewer reports findings; no unresolved Critical/High findings for the claim |
| I | Release gate | All mandatory tests and evidence are tied to the exact release candidate |

Do not attempt Secure Boot/LUKS integration as an isolated one-line config change. Both require boot/initramfs/installer/recovery design and destructive test coverage.

# 6. Test environment and safety rules

## 6.1 Required environments

- Disposable QEMU/KVM VMs for automated adversarial tests.
- BIOS and UEFI firmware profiles.
- At least two VM disk sizes and multiple RAM sizes.
- A dedicated test network with controllable DHCP, DNS, IPv4, IPv6, and firewall peers.
- A separate disposable physical machine or spare disk for hardware/firmware validation.
- A separate non-production signing key for CI tests.
- A test package repository with trusted, untrusted, expired, replayed, malformed, and corrupted fixtures.

## 6.2 Safety

- Never run destructive disk, filesystem, bootloader, encryption, or power-loss tests on a machine containing important data.
- Never run exploit/fuzz campaigns against production systems or third-party networks.
- Use snapshots and disposable virtual disks; verify target device identity before formatting.
- Keep test signing keys, release keys, Wi-Fi secrets, and test passwords separate.
- Retain logs with secrets redacted.
- Use a controlled test clock only in isolated VMs.
- Do not run concurrent package transactions unless concurrency itself is the test.
- A failed recovery test must not be “fixed” by silently restoring an old snapshot before evidence is captured.

# 7. Security test catalog

Each test requires: test ID, exact source commit, image hash, environment, commands or harness version, raw output, result, reviewer, issue link for failures, and whether it is release-blocking.

## 7.1 Baseline, threat model, and claims — 12 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-001 | Threat-model completeness | Identify assets, trust boundaries, attacker capabilities, and out-of-scope cases; reviewer signs off. |
| SEC-002 | Security claim review | Every README/release claim maps to a tested property or is removed. |
| SEC-003 | Current-source inventory | Compare dossier paths/settings with exact candidate tree; no stale claims. |
| SEC-004 | Configuration provenance | Record generated kernel config hash and verify it matches the ISO contents. |
| SEC-005 | Image provenance | Record source commit, clean/dirty state, toolchain, host package manifest, and ISO hash. |
| SEC-006 | Live/install divergence | Compare security-critical files in live root and installed root; intended differences are documented. |
| SEC-007 | Root-of-trust map | Document firmware, bootloader, kernel, initramfs, rootfs, package, and key trust transitions. |
| SEC-008 | Data classification | Identify secrets, user data, keys, logs, caches, swap, persistence, and temporary files. |
| SEC-009 | Unsupported-feature claims | Check Wi-Fi, Bluetooth, VPN, TPM, Secure Boot, MAC and encryption wording against actual artifacts. |
| SEC-010 | Security ownership | Assign an owner and response path for each P0/P1 control and vulnerability report. |
| SEC-011 | Risk register | Every accepted risk has impact, likelihood, compensating control, owner, expiry/review date. |
| SEC-012 | Evidence integrity | Store raw test evidence and hashes; results cannot be edited without traceability. |

## 7.2 Secret handling and configuration injection — 18 tests

**Known baseline issue to remediate:** the documented `grintion-network connect SSID [PASSPHRASE]` interface takes the Wi-Fi passphrase as an argument. A typed command can enter shell history, and process arguments can be visible to other processes/users subject to system permissions. Do not keep this interface as the recommended secret-input path.

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-013 | Wi-Fi secret input redesign | Read passphrase from a non-echoing TTY prompt or stdin; never require a secret command-line argument. |
| SEC-014 | Process-list secret leak | While connecting, inspect `/proc/*/cmdline` and `ps`; passphrase is absent. |
| SEC-015 | Shell-history secret leak | Use the documented connection workflow; shell history contains no passphrase. |
| SEC-016 | Log leak | Inspect syslog, service logs, stdout/stderr and doctor output; no credential values. |
| SEC-017 | Crash/error leak | Force controlled failures in config generation; secrets are not printed in tracebacks/errors. |
| SEC-018 | File permissions | `network.conf` and `wpa_supplicant.conf` are owned by root and mode `0600` (or stricter). |
| SEC-019 | Atomic secret-file replacement | Interrupt writes; no world-readable temporary file or partial credential file remains. |
| SEC-020 | SSID serialization | Test quotes, backslashes, control chars, newlines and leading/trailing spaces; output is safely encoded or rejected. |
| SEC-021 | Passphrase validation | Accept only the documented supported lengths/formats; reject malformed values before changing active config. |
| SEC-022 | Shell metacharacter handling | Inputs containing `$`, backticks, quotes, semicolons and command substitutions are treated as data, never executed. |
| SEC-023 | Newline injection | Embedded newline cannot append extra wpa_supplicant directives or shell commands. |
| SEC-024 | Temporary-file symlink attack | Pre-create a symlink at a predictable temp path; tool uses safe exclusive temp creation and does not overwrite target. |
| SEC-025 | Config ownership | Reject or safely repair an unexpected owner/group/mode without following attacker-controlled symlinks. |
| SEC-026 | Installer password arguments | Confirm passwords are never accepted through process-visible arguments. |
| SEC-027 | Installer environment secrets | Document environment variable risk; ensure secrets are unset/redacted and not copied into logs/build metadata. |
| SEC-028 | Clipboard and GUI disclosure | Document that X11 clients can access clipboard/input; do not claim secret isolation for X11. |
| SEC-029 | Secret removal on disconnect | Removing Wi-Fi config removes active secret copies and reports any remaining known copies; SSD wear-leveling caveat documented. |
| SEC-030 | Secret regression suite | Add automated tests for all above cases and run on each change to network/config tooling. |

## 7.3 Authentication, account lifecycle, and privilege — 22 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-031 | Installed root lock | Fresh install without root password cannot authenticate as root through PAM. |
| SEC-032 | Normal-user login | Correct password succeeds; incorrect password fails. |
| SEC-033 | Password hashing | New passwords use yescrypt as configured; inspect hash prefix and algorithm parameters. |
| SEC-034 | Password input exposure | Passwords do not appear in argv, environment dumps, shell history, process logs, or installer transcript. |
| SEC-035 | Lockout threshold | More than the configured five failures triggers `pam_faillock`. |
| SEC-036 | Lockout timer | Account unlocks according to the configured interval; test boundary times. |
| SEC-037 | Lockout reset behavior | Successful login resets failures as intended; verify state storage and reboot behavior. |
| SEC-038 | PAM stack fail-closed | Missing/invalid required auth module causes authentication failure, not bypass. |
| SEC-039 | PAM service coverage | Console, `su`, `sudo`, LightDM and any added login service use intended PAM stacks. |
| SEC-040 | `su` boundary | Non-wheel user cannot use `su`; wheel user requires the expected authentication. |
| SEC-041 | `sudo` boundary | Non-wheel user is denied; wheel user follows configured password policy. |
| SEC-042 | Sudo environment | Environment variables, `PATH`, editor, loader variables and shell functions cannot bypass sudo policy. |
| SEC-043 | Sudo logging | Commands and failures are logged; logs are root-protected and do not contain entered secrets. |
| SEC-044 | Sudoers syntax | `visudo -c` passes for base and every drop-in. |
| SEC-045 | Setuid inventory | Actual setuid/setgid files exactly match the reviewed allowlist; unexpected entries fail the release. |
| SEC-046 | Setuid file ownership | Every allowed privileged file is root-owned and not writable by unprivileged users. |
| SEC-047 | File capability inventory | Enumerate `getcap -r /`; unexpected file capabilities fail the gate. |
| SEC-048 | Account database permissions | passwd, shadow, group and gshadow have correct owner/mode and no symlink substitution. |
| SEC-049 | Duplicate/conflicting IDs | Installer rejects duplicate UID/GID and unsafe usernames. |
| SEC-050 | Account creation interruption | Interrupt account creation; databases remain valid and mutually consistent. |
| SEC-051 | Password aging policy | Replace effectively unlimited aging with a documented policy or explicitly accept it for the single-user desktop threat model. |
| SEC-052 | Root recovery policy | Define who may use recovery; authenticate it or explicitly state physical-access root bypass remains. |

## 7.4 Live media, boot menu, and recovery shell — 16 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-053 | Live root warning | Live root autologin is clearly labeled installation/recovery-only and not described as a secure installed mode. |
| SEC-054 | Recovery-entry access | Verify the `rdinit=/bin/sh` entry is unauthenticated; implement a password-protected or physically acknowledged recovery policy if physical-access protection is claimed. |
| SEC-055 | Boot-menu edit | Attempt to alter kernel command line; authenticated boot chain prevents unauthorized modification where claimed. |
| SEC-056 | Bootloader asset hashes | Validate every Limine binary against trusted upstream release/signature metadata. |
| SEC-057 | Kernel authentication | Bootloader verifies signed kernel before execution. |
| SEC-058 | Initramfs authentication | Bootloader verifies the exact initramfs, not just the kernel. |
| SEC-059 | Boot config authentication | Protect boot entries and kernel command line against unauthorized edits. |
| SEC-060 | Secure Boot enforcement | On physical UEFI firmware with Secure Boot enabled, only enrolled trusted components boot. |
| SEC-061 | Secure Boot negative test | Modified/unsigned bootloader, kernel, initramfs and configuration are rejected. |
| SEC-062 | Secure Boot recovery | Document recovery and key-enrollment flow; no silent Secure Boot disable. |
| SEC-063 | TPM availability | Detect TPM absence safely; do not claim measured boot if no measurement chain exists. |
| SEC-064 | Measured boot chain | If implemented, verify expected PCR measurements for firmware, bootloader, kernel and initramfs. |
| SEC-065 | PCR policy | If secrets are TPM-sealed, authorized boot updates recover; tampered boot does not unseal secrets. |
| SEC-066 | Kernel command-line validation | Reject or constrain dangerous parameters in a production secure-boot profile. |
| SEC-067 | Rescue path audit | Every rescue path has an explicit access policy and test evidence. |
| SEC-068 | Physical access statement | State plainly whether the product protects data and integrity against a person holding the device. |

## 7.5 Kernel configuration, boot parameters, and module integrity — 22 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-069 | Kernel config contract | `build/check-kernel-config.sh` validates the final generated config, not only the fragment. |
| SEC-070 | Runtime kernel identity | `uname -r`, config, build metadata and booted image correspond to the release candidate. |
| SEC-071 | KASLR | Verify kernel randomization is active on supported hardware; document when virtualized tests cannot prove it. |
| SEC-072 | W^X | Verify strict kernel/module RWX settings and effective runtime behavior. |
| SEC-073 | Stack protector | Confirm compiler/config support and inspect build flags/artifacts. |
| SEC-074 | FORTIFY | Confirm enabled at the intended optimization level; inspect compiler/build logs. |
| SEC-075 | Hardened usercopy | Confirm config and execute relevant negative tests where available. |
| SEC-076 | Memory initialization | Confirm init-on-alloc/free and stack initialization in the final config/command line. |
| SEC-077 | CPU mitigations | Record `lscpu` and vulnerability status; do not assume every CPU supports every mitigation. |
| SEC-078 | SMEP/SMAP | Inspect actual final config and CPU state; claim only if present and active. |
| SEC-079 | IBT/CET | Verify hardware/kernel support and report active/inactive status accurately. |
| SEC-080 | PTI and speculation controls | Confirm actual runtime mitigation status in `/sys/devices/system/cpu/vulnerabilities/`. |
| SEC-081 | BPF surface | Confirm BPF syscall is unavailable as intended; test unprivileged and privileged cases. |
| SEC-082 | io_uring restriction | Confirm `kernel.io_uring_disabled=2` at runtime; required setting failure blocks release. |
| SEC-083 | kexec restriction | Confirm kexec is not available through kernel configuration and interfaces. |
| SEC-084 | `/dev/mem`/`/proc/kcore` | Verify absent/unusable under the intended policy. |
| SEC-085 | Module signature enforcement | Attempt to load unsigned module in disposable VM; kernel rejects it. |
| SEC-086 | Signed module verification | Verify every shipped module signature and signing algorithm. |
| SEC-087 | Signing-key protection | Private signing key is not embedded in ISO, build artifacts, git history, or public CI logs. |
| SEC-088 | Module unload policy | Confirm forced unload is disabled and unnecessary module loading is restricted. |
| SEC-089 | Firmware loading | Only trusted firmware packages/paths are used; missing firmware fails safely and is not silently described as supported. |
| SEC-090 | Kernel taint policy | Test harness records taints; unexpected taint is a release failure requiring explanation. |

## 7.6 Runtime hardening and sysctl enforcement — 16 tests

**Baseline concern:** `/etc/runit/1` applies sysctl files with errors suppressed (`sysctl -p ... || true`). A security profile must distinguish optional unsupported keys from required controls that failed to apply.

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-091 | Required sysctl manifest | Classify each setting as mandatory, optional, or unsupported with a reason. |
| SEC-092 | Effective sysctl test | Read back every mandatory value after full boot; compare with expected policy. |
| SEC-093 | Fail-closed sysctl handling | A missing required control prevents secure-profile readiness or emits a blocking failure. |
| SEC-094 | ASLR | Verify `kernel.randomize_va_space=2` at runtime. |
| SEC-095 | dmesg restriction | Verify unprivileged user cannot read restricted kernel logs. |
| SEC-096 | kptr restriction | Verify kernel pointer exposure is restricted. |
| SEC-097 | Yama ptrace | Verify unprivileged processes cannot ptrace unrelated users beyond policy. |
| SEC-098 | Perf event access | Verify `perf_event_paranoid` policy from an unprivileged account. |
| SEC-099 | BPF restriction | Verify unprivileged BPF access remains disabled. |
| SEC-100 | Core dumps | Verify process core dumps are disabled or securely handled; confirm no secret dump files. |
| SEC-101 | Protected symlink/hardlink | Run hostile ownership and link tests in a disposable filesystem. |
| SEC-102 | Protected FIFO/regular files | Test sticky directories and unsafe file replacement cases. |
| SEC-103 | Redirect/source-route policy | Verify IPv4 and IPv6 redirect/source-route settings on all interfaces. |
| SEC-104 | Reverse-path filtering | Test expected behavior in multi-interface and spoofed-source VM scenarios. |
| SEC-105 | IP forwarding | Verify IPv4 and IPv6 forwarding remain disabled unless explicitly supported and enabled. |
| SEC-106 | Sysctl drift | Modify a required sysctl at runtime; doctor/audit detects drift and reports it. |

## 7.7 MAC, namespaces, and process confinement — 20 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-107 | Choose MAC implementation | Select SELinux or AppArmor; document why and the policy boundary. |
| SEC-108 | MAC actually enforcing | Boot with policy loaded; verify enforcing mode, not merely kernel support. |
| SEC-109 | Policy coverage | Every privileged service has an explicit policy/domain/profile. |
| SEC-110 | Policy default-deny | Unlisted access is denied; policy exceptions are reviewed. |
| SEC-111 | MAC boot failure | Missing/invalid policy fails closed in secure profile; no silent permissive fallback. |
| SEC-112 | Service privilege drop | Network, firewall, logging and optional services run with least privilege where feasible. |
| SEC-113 | Service filesystem view | Services only write to required paths; test forbidden writes. |
| SEC-114 | Service device access | Services only access required device nodes. |
| SEC-115 | Service network access | Services cannot open arbitrary listeners or make unrelated connections if policy forbids it. |
| SEC-116 | Seccomp policy | Define per-service syscall allowlists/deny rules and test representative allowed/denied calls. |
| SEC-117 | Capability bounding | Remove unnecessary Linux capabilities from services and verify via `/proc/<pid>/status`. |
| SEC-118 | Namespace policy | Decide whether unprivileged user namespaces are enabled; record security trade-off. |
| SEC-119 | User namespace escalation test | Run namespace/container exploit regression tests in a disposable VM; no privilege boundary escape. |
| SEC-120 | Mount namespace | Verify services cannot alter host mounts outside their namespace. |
| SEC-121 | PID namespace | Verify process visibility is limited where intended. |
| SEC-122 | Network namespace | Verify a restricted service cannot bypass host firewall by creating an unauthorized network context. |
| SEC-123 | Cgroup availability | Verify cgroup v2 is mounted and usable; required isolation must not be silently skipped. |
| SEC-124 | Resource limits | Set CPU, memory, task and file-descriptor limits for exposed services. |
| SEC-125 | Service restart behavior | Crash a service; runit restarts it without infinite rapid restart/log flooding. |
| SEC-126 | Confinement regression | Test that package upgrades do not remove/override MAC or service profiles. |

## 7.8 Storage, encryption, and data lifecycle — 22 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-127 | LUKS2 design | Specify cipher, key derivation, header backup, recovery, discard policy and supported devices. |
| SEC-128 | Encrypted root install | Install to disposable disk with LUKS2; verify root is encrypted at rest. |
| SEC-129 | Unlock boot | Correct passphrase unlocks; wrong passphrase does not; timeout and retry behavior are safe. |
| SEC-130 | Recovery key | Document secure recovery key generation, storage and rotation; no plaintext copy on target disk. |
| SEC-131 | Header backup | Create and validate LUKS header backup; store it off-device and protect it. |
| SEC-132 | Header recovery | Restore from backup in a disposable image and verify data availability. |
| SEC-133 | Encrypted swap | Ensure swap is encrypted or use an ephemeral key policy; verify no plaintext swap. |
| SEC-134 | Hibernation policy | Keep hibernation disabled unless encrypted swap/resume security is fully designed and tested. |
| SEC-135 | Live persistence encryption | Encrypt persistent overlay or clearly retain a no-secrets warning; test locked/unlocked behavior. |
| SEC-136 | Temporary data | Inventory `/tmp`, `/var/tmp`, `/run`, caches and logs; verify expected mount flags and lifetimes. |
| SEC-137 | Mount flags | Verify `nosuid,nodev,noexec` where intended; verify no accidental writable executable mount. |
| SEC-138 | ESP handling | Verify EFI partition permissions/mount options; state that ESP files remain unencrypted unless authenticated. |
| SEC-139 | Device path safety | Installer resolves the selected disk and child partitions safely; symlink/device replacement cannot redirect writes. |
| SEC-140 | Installer target confirmation | Destructive target is clearly displayed and confirmed; dry-run does not modify anything. |
| SEC-141 | Storage exhaustion | Fill target filesystem; security-critical services and logs fail safely. |
| SEC-142 | TRIM/discard privacy | Document discard behavior under encryption; do not enable discard blindly. |
| SEC-143 | SSD deletion claims | Do not promise secure deletion on SSD; document crypto-erase/device sanitize limits. |
| SEC-144 | Crash consistency | Power-cut tests on disposable disk; filesystem and encrypted mapping recover without silent corruption. |
| SEC-145 | Backup confidentiality | Backup archives are encrypted, authenticated, and restore-tested if backup tooling is added. |
| SEC-146 | Data remanence | Verify sensitive files are not copied into logs, build cache, ISO, package archives, or backup snapshots. |
| SEC-147 | Disk theft test | With device powered off, remove disk and attempt read; encrypted volumes reveal no plaintext user data. |
| SEC-148 | Key lifecycle | Rotate/revoke lost keys and remove former keys; verify recovery procedure. |

## 7.9 Firewall and network security — 20 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-149 | Default inbound deny | From a separate test VM, scan IPv4/IPv6; no unexpected inbound port is reachable. |
| SEC-150 | Forward default deny | Confirm forwarding is off and nftables forward chain drops traffic. |
| SEC-151 | Output policy review | Document why output is accepted; if egress filtering is claimed, implement and test it. |
| SEC-152 | IPv4 firewall coverage | Test TCP, UDP, ICMP, fragments, established/related and invalid traffic. |
| SEC-153 | IPv6 firewall coverage | Repeat tests over IPv6; no IPv6 bypass around the inet ruleset. |
| SEC-154 | Firewall boot ordering | Firewall is loaded before network is considered ready and before optional listeners start. |
| SEC-155 | Firewall load failure | Corrupt config in disposable VM; machine must not silently operate with no firewall while network is up. |
| SEC-156 | Firewall service crash | Kill/restart firewall service; rules remain or are restored without exposure window. |
| SEC-157 | Firewall ruleset drift | `grintion-doctor` compares live ruleset to approved policy, not just checks table existence. |
| SEC-158 | Unexpected listener detection | Enumerate sockets with `ss`; any listener not in allowlist fails release. |
| SEC-159 | Loopback policy | Confirm local services work without allowing external spoofed loopback packets. |
| SEC-160 | DHCP exceptions | Only required client reply traffic is allowed; spoofed/out-of-state replies are rejected. |
| SEC-161 | ICMPv6 correctness | Necessary neighbor discovery/PMTU behavior works while unsolicited inbound remains constrained. |
| SEC-162 | DNS spoofing | Controlled hostile DNS tests; document resolver trust and lack of DNS encryption/cache. |
| SEC-163 | DNS fallback privacy | Make use of public fallback resolvers explicit; no misleading privacy claim. |
| SEC-164 | Network config permissions | Static/Wi-Fi config cannot be changed by unprivileged users. |
| SEC-165 | Interface spoofing | Test forged source/MAC/IP packets in isolated network; host follows explicit anti-spoof policy. |
| SEC-166 | DHCP starvation/DoS | Verify timeouts and service recovery; do not claim DoS immunity. |
| SEC-167 | Wi-Fi support boundary | Until supported vendor drivers and firmware are shipped and tested, report Wi-Fi as unsupported. |
| SEC-168 | Remote management | Confirm no sshd or other remote admin daemon is started by default; future daemon requires dedicated hardening tests. |

## 7.10 Native `garb` package security — 30 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-169 | Signature-before-parse | Malformed or unsigned index is rejected before metadata is trusted. |
| SEC-170 | Wrong signing key | Index signed by untrusted key is rejected. |
| SEC-171 | Signature corruption | Flip bytes in index/signature; update/install fails closed. |
| SEC-172 | Key missing | Missing configured public key blocks update. |
| SEC-173 | Key replacement | Replaced key requires an explicit trusted rotation path. |
| SEC-174 | Expired index | Expired signed index is rejected. |
| SEC-175 | Replay index | Older index version is rejected even if signature is valid. |
| SEC-176 | Clock rollback | Move test clock backwards; cached anti-replay state still prevents downgrade. |
| SEC-177 | Clock forward | Incorrect future clock cannot silently make all signed metadata valid forever; behavior is explicit. |
| SEC-178 | Index schema validation | Missing/wrong-typed/oversized fields fail without crash or unsafe defaults. |
| SEC-179 | Duplicate JSON keys | Duplicate package/metadata keys are rejected or canonicalized under a documented safe rule. |
| SEC-180 | Archive digest | Modified archive fails SHA-256 validation before extraction. |
| SEC-181 | Per-file digest | Modified installed file is detected by `garb verify`. |
| SEC-182 | Undeclared files | Extra archive entries are rejected. |
| SEC-183 | Absolute path traversal | Absolute paths and `..` escapes are rejected. |
| SEC-184 | Symlink traversal | Symlink archive entries cannot redirect writes outside target root. |
| SEC-185 | Hardlink traversal | Hardlinks cannot reference paths outside target root or sensitive host paths. |
| SEC-186 | Special files | Device nodes, sockets, FIFOs, and unsupported types are rejected unless explicitly required. |
| SEC-187 | Duplicate archive paths | Duplicate/conflicting paths are rejected deterministically. |
| SEC-188 | Archive bomb | Extreme file count, decompressed size, nesting, or compression ratio is bounded. |
| SEC-189 | Metadata resource cap | Oversized index/metadata is rejected before excessive memory/CPU use. |
| SEC-190 | Path normalization | Unicode, repeated separators, dot segments and case behavior cannot bypass path checks. |
| SEC-191 | Symlink race | Replace path components during install; writes remain confined to target root. |
| SEC-192 | TOCTOU ownership | Pre-create attacker-controlled files/directories; installation refuses unsafe ownership conflicts. |
| SEC-193 | Setuid/setgid rejection | Package cannot add setuid/setgid bits or file capabilities. |
| SEC-194 | Ownership handling | Package cannot assign arbitrary privileged ownership in an unsafe way. |
| SEC-195 | Dependency cycle | Circular dependencies fail cleanly without partial install. |
| SEC-196 | Missing dependency | Transaction fails before changing target or rolls back exactly. |
| SEC-197 | Conflicting package files | Two packages cannot silently overwrite each other's owned files. |
| SEC-198 | Transaction interruption | Kill `garb` during each transaction phase; recovery leaves consistent database/filesystem or a clearly recoverable backup. |
| SEC-199 | Rollback corruption | Make a restore operation fail; original backup is retained and failure is explicit. |
| SEC-200 | Concurrent transactions | Two package transactions cannot race on the same root/database; lock or reject one. |
| SEC-201 | Local archive trust | Local `.garb` receives the same archive/path/type checks as repository downloads. |
| SEC-202 | Target-root safety | `--root` symlinks, mount boundaries and path aliases cannot cause writes outside target. |
| SEC-203 | Unsigned override | `--allow-unsigned` is unavailable or hard-blocked in production profile and clearly marked development-only. |
| SEC-204 | Native package fuzzing | Fuzz index parser, Garbfile parser, archive reader, path sanitizer and transaction state machine; no crash escape, arbitrary write, or silent acceptance. |

## 7.11 Pacman backend and external package execution — 14 tests

Treat this as a separate security domain. The dossier states that pacman packages/hooks may run as root and that delegation bypasses native `garb` signature/index/per-file/rollback guarantees.

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-205 | Backend disclosure | CLI clearly reports when pacman rather than native backend is selected. |
| SEC-206 | Trust boundary prompt | First use or explicit policy requires informed acknowledgement that package scripts execute as root. |
| SEC-207 | Native/pacman state separation | Native database and pacman local database cannot silently overwrite or misreport each other's state. |
| SEC-208 | Signature policy | Verify package signatures are required and wrong/unsigned packages fail. |
| SEC-209 | Database trust statement | `DatabaseOptional` is clearly documented; do not claim signed repository database metadata. |
| SEC-210 | Keyring provenance | Verify pinned keyring hash and provide auditable source/provenance. |
| SEC-211 | Keyring freshness | Define update/revocation process; pinned stale keyring must not become permanent trust. |
| SEC-212 | Root script execution | Install a test package with a harmless script/hook in a disposable VM; verify execution context and logs. |
| SEC-213 | Malicious script containment | If a sandbox is added, prove package scripts cannot access host secrets/devices/network beyond policy. |
| SEC-214 | Offline/partial upgrade | Test mirror interruption and partial transaction recovery using disposable root. |
| SEC-215 | Unsupported systemd hooks | Detect/report hooks requiring systemd; do not report transaction success as full feature success. |
| SEC-216 | Backend downgrade | Switching from native to pacman cannot silently downgrade/replace protected packages. |
| SEC-217 | Backend disable mode | Provide a profile/build without pacman delegation for users requiring only native repository semantics. |
| SEC-218 | Backend audit | Independent review covers command construction, environment, target root and all translated arguments. |

## 7.12 Desktop, X11, display manager, and audio — 14 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-219 | X11 limitation warning | State clearly that X11 clients in one session can read/inject into other clients. |
| SEC-220 | Wayland support claim | Do not claim isolated Wayland security until Wayland session and compositor policy are tested. |
| SEC-221 | Display-manager privilege | Review root-running display manager and greeter PAM paths; minimize privileged code and test authentication boundary. |
| SEC-222 | Screen-lock policy | Configure and verify automatic lock on idle and lid close for supported desktop profiles, or explicitly do not claim unattended physical protection. |
| SEC-223 | Lock bypass | Test VT switching, X server restart, crash, suspend/resume and remote input paths; locked session remains locked. |
| SEC-224 | GUI autostart | Audit desktop autostart entries and user-writable startup paths for privilege escalation. |
| SEC-225 | Audio service privilege | PipeWire/WirePlumber run as the logged-in user; no unnecessary root service. |
| SEC-226 | GUI app filesystem access | Apply and test sandbox/portal policy if GUI sandboxing is claimed. |
| SEC-227 | Removable media autorun | Confirm no untrusted executable autoruns on USB insertion. |
| SEC-228 | Clipboard/selection | Document X11 exposure; test any clipboard manager doesn't log or persist secrets unexpectedly. |
| SEC-229 | Display crash recovery | Crashing Xorg/display manager cannot expose greeter credentials or leave privileged helper alive. |
| SEC-230 | Desktop profile permissions | Installed desktop config, service links and session hooks have safe ownership and permissions. |
| SEC-231 | Audio device privacy | Test microphone capture permissions and mute state; no claim of microphone privacy without a working control path. |
| SEC-232 | Unverified desktops | GNOME, KDE, LXQt, Sway and Wayland stay unclaimed until separately tested and reviewed. |

## 7.13 Installer and recovery security — 16 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-233 | Device selection confirmation | Selected whole-disk target, size and model are displayed before destructive write. |
| SEC-234 | Wrong device safety | Test device-name changes and hotplug races; installer aborts rather than wiping a different disk. |
| SEC-235 | Dry-run purity | Compare disk hashes/partition tables before and after dry-run; no change. |
| SEC-236 | Password stdin handling | Passwords do not leak through argv, logs, shell trace or temporary files. |
| SEC-237 | Environment cleanup | Unset secret environment variables after consumption and avoid writing them to logs. |
| SEC-238 | Installer interruption | Interrupt before partitioning, during partitioning, during copy, during bootloader install and during finalization; document safe recovery. |
| SEC-239 | Partial install detection | Booting a partially installed target gives a clear recovery path, not silent success. |
| SEC-240 | Target file ownership | Installed files have expected root/user ownership and modes. |
| SEC-241 | Boot assets | Kernel, initramfs and boot config hashes match release manifest. |
| SEC-242 | Secure Boot refusal | Secure Boot enabled with unsigned chain is refused unless user deliberately overrides; override is prominent and logged. |
| SEC-243 | Override warning | `--force` cannot be confused with ordinary installation; its security consequences are printed. |
| SEC-244 | Recovery authenticity | Recovery media and recovery shell obey the chosen boot authentication policy. |
| SEC-245 | Recovery secret handling | LUKS recovery doesn't expose keys in command line, logs, environment, or shell history. |
| SEC-246 | Filesystem repair | Corrupt root filesystem repair is tested on copies; no automatic destructive “repair” without clear policy. |
| SEC-247 | ESP rollback | Failed bootloader upgrade preserves a recoverable previous boot entry/image. |
| SEC-248 | Persistence security | Confirm live persistence remains nosuid,nodev and document lack of encryption/integrity until implemented. |

## 7.14 Build, release, and software supply chain — 24 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-249 | Clean build tree | Release build refuses dirty source tree or records exact diff and requires approval. |
| SEC-250 | Build provenance | `BUILD-INFO` identifies exact commit, source tree state, kernel config, toolchain and host package manifest. |
| SEC-251 | ISO source binding | ISO is rebuilt from the exact tagged commit; `BUILD-INFO` commit equals tag commit. |
| SEC-252 | Same-host reproducibility | Two clean same-host builds produce byte-identical artifacts or a fully explained deterministic diff. |
| SEC-253 | Cross-host reproducibility plan | Identify host-dependent userland inputs and work toward reproducible builds; never claim cross-host reproducibility prematurely. |
| SEC-254 | Source signature verification | Verify upstream signed release/checksum metadata, not only a checksum fetched from the same unauthenticated channel. |
| SEC-255 | Dependency pinning | Pin versions/digests for all build inputs, including host-derived packages. |
| SEC-256 | Host package manifest | Emit exact installed package versions used to assemble the rootfs. |
| SEC-257 | SBOM | Publish machine-readable SPDX or CycloneDX SBOM for ISO and desktop profiles. |
| SEC-258 | License inventory | Cross-check SBOM with `THIRD-PARTY.md`; no unknown or untracked component. |
| SEC-259 | Vulnerability scan | Scan shipped userspace/kernel/tool components against a documented vulnerability source and date. |
| SEC-260 | Release signing | Sign ISO, checksum, BUILD-INFO and SBOM with offline-controlled release key. |
| SEC-261 | Signature verification instructions | A clean machine can verify release signatures using a separately published trusted public key. |
| SEC-262 | Release-key separation | Release signing key is not present in source repo, ISO, build VM, CI logs or developer daily-use machine. |
| SEC-263 | Key rotation | Exercise old-key/new-key transition, expiry and emergency revocation in a test release. |
| SEC-264 | Compromised key procedure | Document revoke, publish advisory, rebuild, re-sign, and user recovery steps. |
| SEC-265 | CI isolation | Build/test jobs use least-privilege ephemeral credentials and do not expose release signing keys. |
| SEC-266 | Artifact retention | Store exact logs, SBOM, build manifest, signatures and test reports for each release. |
| SEC-267 | Dependency substitution | Replace one pinned source/archive with modified bytes; build fails before use. |
| SEC-268 | Build script injection | Test malicious filenames, environment variables and archive entries in build staging; no host path escape. |
| SEC-269 | Repository compromise drill | Simulate a compromised package index/key in a controlled environment; clients reject it and response plan works. |
| SEC-270 | CI policy | Security tests and independent review status are required checks before release tagging. |
| SEC-271 | Third-party assets | Validate Limine and vendored binaries against authenticated upstream provenance. |
| SEC-272 | Release asset consistency | Published ISO hash matches signed manifest; all attached artifacts correspond to same tag/build. |

## 7.15 Fuzzing, static analysis, and independent review — 18 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-273 | ShellCheck | Run ShellCheck on all project shell scripts; reviewed suppressions only. |
| SEC-274 | Python static analysis | Run a suitable Python linter/type checker/security scanner; triage all findings. |
| SEC-275 | Shell parser fuzzing | Fuzz `network.lib.sh`, config parsers and installer argument handling. |
| SEC-276 | Garb parser fuzzing | Fuzz JSON, Garbfile, tar/gzip metadata and path handling. |
| SEC-277 | Archive corpus | Maintain malicious archive corpus: traversal, symlinks, hardlinks, duplicate paths, special files, truncation and bombs. |
| SEC-278 | Installer fuzzing | Fuzz device arguments, sizes, hostnames, usernames, profile names and environment. |
| SEC-279 | Protocol fuzzing | Fuzz any network-facing parser/service introduced by the project; no unbounded crash or memory corruption. |
| SEC-280 | Kernel sanitizers | Use suitable debug/sanitizer kernel builds in disposable VMs; record any reports. Do not ship debug-only config without review. |
| SEC-281 | Long fuzz campaign | Run continuous fuzzing for a documented duration and corpus; publish duration, coverage and crash count. |
| SEC-282 | Crash triage | Every crash is reproduced, classified, fixed or explicitly accepted before release. |
| SEC-283 | Regression corpus | Every fixed security bug receives a permanent regression test. |
| SEC-284 | Independent code review | Reviewer not responsible for original implementation reviews installer, init, `garb`, network, PAM, firewall, boot and build scripts. |
| SEC-285 | Threat-model review | Independent reviewer challenges attacker assumptions and security claims. |
| SEC-286 | Penetration test | Independent tester attempts local privilege escalation, package compromise, boot tampering and network entry in authorized lab. |
| SEC-287 | Report publication | Publish scope, date, tools/method, findings, exclusions and remediation status without exposing exploitable details prematurely. |
| SEC-288 | Finding closure | No unresolved Critical/High finding for any security claim made by the release. |
| SEC-289 | Retest | Reviewer retests fixes on the release candidate, not only the developer's working tree. |
| SEC-290 | Audit independence | Reviewer records conflicts of interest and exact commit/image hash reviewed. |

## 7.16 Vulnerability management and maintenance — 14 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-291 | Private reporting channel | Verify security advisory process and contact method work. |
| SEC-292 | Triage policy | Define severity, acknowledgement target, remediation target and disclosure policy. |
| SEC-293 | CVE monitoring | Track kernel, BusyBox, runit, glibc, OpenSSL, Python, Limine, Xorg, PipeWire and shipped package vulnerabilities. |
| SEC-294 | Supported release policy | Publish supported versions and end-of-life dates. |
| SEC-295 | Patch process | Build, test, sign and publish security fixes with advisory and affected-version range. |
| SEC-296 | Emergency release drill | Simulate a critical vulnerability; demonstrate patch and notification path. |
| SEC-297 | Key compromise drill | Simulate release/repository key loss or compromise and exercise revocation. |
| SEC-298 | User notification | Document how users learn of a security update; no automatic-update claim without updater. |
| SEC-299 | Update verification | Verify updates use authenticated metadata and reject rollback/downgrade attempts. |
| SEC-300 | Unsupported software | Publish how users identify desktop packages and optional components outside the base support set. |
| SEC-301 | Security log retention | Define what is logged, who can read logs, retention limits and secret redaction. |
| SEC-302 | Incident evidence | Preserve forensic evidence without collecting unnecessary personal data. |
| SEC-303 | Risk review expiry | Revisit accepted risks on every release and at least once per planned maintenance interval. |
| SEC-304 | Post-release monitoring | Track new upstream CVEs and issues for the entire supported release lifetime. |

## 7.17 Physical hardware and platform-specific security — 12 tests

| ID | Test / requirement | Procedure and pass condition |
|---|---|---|
| SEC-305 | Real UEFI firmware | Test the signed boot chain on physical UEFI hardware with Secure Boot on. |
| SEC-306 | Firmware settings | Record Secure Boot, TPM, virtualization and IOMMU state; do not infer them from QEMU. |
| SEC-307 | NVMe/SATA data protection | Test LUKS on physical NVMe and SATA where supported; verify power-loss recovery. |
| SEC-308 | USB boot tampering | Modify boot media; authenticated boot must reject it if tamper protection is claimed. |
| SEC-309 | External disk attack | Test offline disk removal/read against encrypted installed system. |
| SEC-310 | DMA/IOMMU | If physical DMA protection is claimed, verify IOMMU state and device policy; otherwise state exclusion. |
| SEC-311 | Laptop sleep | Test sleep/resume with encrypted volumes and locked session; ensure keys and screen are not exposed. |
| SEC-312 | Battery/power loss | Test unexpected battery removal/power cut; verify filesystem and encryption recovery. |
| SEC-313 | CPU-specific mitigations | Record real CPU vulnerability/mitigation status and explain unsupported mitigations. |
| SEC-314 | Firmware update threat | Define trust and rollback policy for firmware updates if a supported update path is added. |
| SEC-315 | Peripheral hotplug | Test USB storage/HID/audio hotplug; no autorun and no unexpected privilege gain. |
| SEC-316 | Hardware support boundary | Publish exact devices tested, driver/firmware versions, and untested components. |

---

# 8. Specific baseline remediation backlog

These are prioritized because they are visible in the 0.9.0 dossier. Recheck them against the exact current source before changing code.

| Priority | Baseline item | Required action |
|---|---|---|
| P0 | Wi-Fi passphrase accepted as CLI argument | Replace with hidden prompt/stdin interface; add argv/history/log/config-injection regression tests. |
| P0 | Unsigned ISO, bootloader, kernel/initramfs, BUILD-INFO | Do not claim boot/release authenticity; implement signed release and verified boot before making that claim. |
| P0 for theft-protection claim | Plain ext4 root, plain swap, unencrypted persistence | Implement and validate LUKS2 and a safe swap/persistence design. |
| P1 | Inert SELinux and no AppArmor | Ship one complete MAC implementation with policies and enforcing-mode tests, or state MAC is absent. |
| P1 | No service sandbox; privileged daemons | Inventory every service; drop privileges and apply namespaces/seccomp/capabilities/MAC where possible. |
| P1 | X11 client access and no screen lock | Keep X11 limitations explicit; add tested screen lock and consider a supported Wayland path with verified isolation. |
| P1 | Recovery menu gives root shell | Protect recovery or explicitly exclude physical-access resistance. |
| P1 | Pacman hooks/scripts run as root | Separate the backend trust model, provide warning/opt-out, review hooks, and avoid implying native `garb` rollback guarantees. |
| P1 | No CVE process or automatic security updates | Establish monitoring, triage, signed security releases and a user notification process. |
| P1 | No SBOM or independent audit | Publish SBOM and obtain independent review. |
| P2 | `runit/1` suppresses sysctl errors | Make required hardening settings mandatory and verify effective values after boot. |
| P2 | Unrestricted user namespaces | Decide policy based on browser/desktop needs; test and document the attack-surface trade-off. |
| P2 | No auditd userspace | Define minimum security-event logging and retention suitable for runit. |
| P2 | No NTP/time synchronization | Define trusted time source or explain effects on certificate and signed-index validation. |
| P2 | No Wi-Fi vendor drivers/firmware | Keep Wi-Fi unsupported until drivers, firmware, authentication, and real hardware are tested. |
| P2 | Build host userland is trusted | Capture host package manifest, verify provenance, and reduce host-dependent inputs. |

**Do not mark the P0 rows “fixed” by adding documentation alone.** Documentation can narrow a claim; it cannot implement cryptographic verification or encryption.

# 9. Security tooling and evidence

Use the tools that match the code and environment. Tool output is evidence, not a verdict.

## 9.1 Static and source review

- `shellcheck` for shell scripts.
- Python static analysis and dependency scanning for `bin/garb` and build/test code.
- Search for secrets, unsafe temporary files, shell interpolation, unchecked return codes, permissive file modes, and external command construction.
- Review all uses of `eval`, `source`, `PATH`, `LD_*`, `TMPDIR`, symlinks, archive extraction, and privileged file writes.
- Review the exact final source diff and all generated configuration.

## 9.2 Runtime inspection

Representative commands (adapt to installed tools; absent tools are themselves a recorded limitation):

```sh
uname -a
cat /proc/cmdline
cat /proc/sys/kernel/randomize_va_space
cat /proc/sys/kernel/dmesg_restrict
cat /proc/sys/kernel/kptr_restrict
cat /proc/sys/kernel/yama/ptrace_scope
cat /proc/sys/kernel/io_uring_disabled
sysctl -a
find / -xdev -type f -perm /6000 -printf '%m %u:%g %p\n' 2>/dev/null
getcap -r / 2>/dev/null
ss -lntup
nft list ruleset
findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS
lsmod
dmesg --level=err,warn
sv status /var/service/*
```

Never paste output containing private keys, Wi-Fi PSKs, passwords, tokens or personal data into a public issue.

## 9.3 Network lab

Use two or more isolated VMs on a host-only/internal network. Include IPv4 and IPv6, a controlled DHCP server, DNS server, and a scanner/test peer. Test allowed and denied paths. Do not scan public networks without authorization.

## 9.4 Package fuzzing

Build a local test repository. Include malformed JSON, invalid signatures, expired/replayed indexes, corrupt gzip, path traversal, symlink/hardlink escape, duplicate paths, special files, huge archives, interrupted writes, disk-full failures and concurrent transactions. Assert that no write escapes the target root and no invalid package is marked installed.

## 9.5 Secure Boot and LUKS testing

These need physical firmware tests plus disposable VM tests. QEMU-only success can verify implementation logic but does not prove compatibility with consumer UEFI firmware, TPM firmware, NVMe controllers or laptop recovery paths.

# 10. Mandatory release acceptance criteria

A release cannot pass this security milestone merely by having all rows in a checklist marked complete. It must satisfy the applicable gates below.

## Gate A — No critical credential leaks

- No passwords/passphrases in argv, shell history, logs, environment dumps or world-readable files.
- No unsafe config injection through SSID, hostname, username, path or package metadata.
- Credential tests run against the release candidate.

## Gate B — Privilege boundaries are verified

- Installed root is locked unless deliberately configured.
- PAM, `sudo`, `su`, setuid inventory, account files and file capabilities pass negative tests.
- Required kernel/sysctl controls are active at runtime.
- Service privilege and confinement status is explicit.

## Gate C — Package integrity is trustworthy

- Native `garb` rejects invalid signatures, hashes, archive paths, malformed metadata, replay, expiry and transaction interruption.
- Pacman is separately described and tested; do not attribute native guarantees to it.
- No unresolved package-manager escape or arbitrary-write finding.

## Gate D — Network exposure is understood

- Firewall is loaded before the machine is declared network-ready.
- Failure is fail-closed.
- IPv4 and IPv6 are tested from an independent peer.
- No unexpected listening service exists.
- Unsupported Wi-Fi is not advertised as working.

## Gate E — Physical-access claims match implementation

For a claim of **offline data confidentiality**, LUKS2 (including swap and persistence policy) must be implemented and tested.

For a claim of **boot tamper resistance**, signed boot chain and Secure Boot must be implemented and tested on physical UEFI hardware.

For a claim of **measured boot**, TPM measurements and verification must be implemented; Secure Boot alone is not measured boot.

If these features are absent, state that physical access can compromise boot integrity and read unencrypted storage.

## Gate F — Release supply chain is authenticated

- Exact tagged source tree is clean.
- ISO and manifest refer to the same commit and build.
- Release signature verifies using a separately trusted public key.
- SBOM and build provenance are published.
- Key custody, rotation and revocation are documented.
- No release key in repo/ISO/CI artifacts.

## Gate G — Independent review

- Independent reviewer covers boot chain, installer, `garb`, pacman boundary, secrets, PAM/sudo, network/firewall, init/services, and build/release pipeline.
- No unresolved Critical or High findings for the stated release claim.
- Fixes are retested against the exact candidate artifact.
- Assessment scope and exclusions are published.

## Gate H — Operational maintenance

- Vulnerability reporting works.
- CVE monitoring and patch policy have an owner.
- Security update and emergency-release drills succeed.
- Accepted risks are reviewed and have expiry/review dates.

# 11. Release claim levels

Use a claim level rather than a vague “secure” badge.

| Level | Name | Minimum evidence |
|---|---|---|
| 0 | Security-conscious experimental OS | Existing hardening and limitations documented; no certification implication |
| 1 | Security-tested experimental OS | Gates A–D pass; package and runtime tests completed; gaps disclosed |
| 2 | Authenticated release | Level 1 plus signed release artifacts, SBOM, build provenance, key rotation and verified artifact instructions |
| 3 | Physical-access-aware endpoint | Level 2 plus tested LUKS2, secure boot chain and documented recovery on supported hardware |
| 4 | Independently assessed release | Level 3 plus independent review/penetration test, no unresolved Critical/High issues for claim, remediation retest, operational vulnerability process |

Level 4 still does **not** mean “unhackable,” “formally certified,” or safe against every unknown vulnerability. Any certification claim requires the named certification and its actual scope.

# 12. Suggested implementation order

1. **Immediate:** fix Wi-Fi passphrase argument exposure; harden SSID/config serialization; add regression tests.
2. **Immediate:** convert sysctl policy from “best effort” to mandatory verification for required controls.
3. **Immediate:** test PAM, setuid, sudo, setcap and recovery-console boundaries.
4. **Next:** add a fail-closed firewall boot gate and runtime ruleset validation.
5. **Next:** audit/fuzz native `garb`, especially archive extraction, symlink/path handling, rollback and concurrency.
6. **Next:** clearly isolate or disable pacman delegation in a security-focused profile.
7. **Next:** service privilege drop, MAC policy, seccomp and cgroup confinement.
8. **Next:** secure-release signing, SBOM, key custody/rotation and source/build provenance.
9. **Next:** LUKS2 with recovery-safe initramfs/installer and encrypted swap/persistence policy.
10. **Next:** signed boot chain, Secure Boot and optional TPM measured-boot integration.
11. **Then:** physical hardware testing, fuzzing campaign, independent audit and retest.
12. **Before every release:** repeat applicable tests on the exact tagged source and published artifacts.

# 13. Required repository deliverables

Create or maintain these files as work progresses:

```text
docs/THREAT-MODEL.md
docs/SECURITY-ARCHITECTURE.md
docs/SECURITY-TEST-PLAN.md
docs/SECURITY-TEST-RESULTS.md
docs/SECURITY-INCIDENT-RESPONSE.md
docs/SECURITY-KEY-MANAGEMENT.md
docs/SECURE-BOOT.md
docs/DISK-ENCRYPTION.md
docs/SUPPLY-CHAIN.md
docs/INDEPENDENT-REVIEW.md
security/
  test-data/
  malicious-archives/
  fuzz-corpus/
  reports/
  sbom/
```

Suggested automation targets (only add targets after their scripts exist):

```text
make security-static
make security-config
make security-runtime
make security-auth
make security-firewall
make security-garb
make security-fuzz-smoke
make security-release
make security-all
```

`security-all` must not silently skip a required tool/test. It should print `PASS`, `FAIL`, or `NOT RUN` with a reason, and return non-zero when a mandatory check is skipped or fails. Long fuzzing and physical tests may be separate release gates, but must never be reported as passed when not executed.

# 14. Security test result template

Copy this for every test:

```text
Test ID:
Title:
Severity / release gate:
Source commit:
ISO SHA-256:
BUILD-INFO commit:
Kernel release:
Generated kernel-config SHA-256:
Environment:
Hardware / VM:
Preconditions:
Exact procedure / command:
Expected result:
Observed result:
Evidence paths / hashes:
PASS / FAIL / NOT RUN:
Failure issue:
Fix commit:
Retest source commit:
Reviewer:
Notes / limitations:
```

# 15. Final security release report template

```text
Grintion OS version:
Source tag:
Source commit:
Working tree clean:
ISO SHA-256:
BUILD-INFO:
SBOM:
Release signature:
Signing key fingerprint:
Build host/toolchain:
Test date:
Test environments:
Tests PASS:
Tests FAIL:
Tests NOT RUN:
P0 findings open:
P1 findings open:
P2 findings open:
Independent reviewer:
Independent report:
Accepted risks:
Supported hardware:
Unsupported features:
Security claim level:
Exact allowed public claim:
```

The report must list all `NOT RUN` items. Do not convert missing evidence into a pass.

# 16. Final decision

The uploaded 0.9.0 dossier is valuable precisely because it names limitations instead of hiding them. Preserve that standard. The next milestone is not “add every security technology”; it is to build a coherent chain of trust, protect secrets, reduce privilege, confine services, validate package inputs, encrypt sensitive storage, authenticate boot/releases, test the real implementation, and obtain review outside the original author.

**Recommended public wording before this milestone passes:**

> Grintion OS is an experimental x86_64 Linux system with selected kernel hardening, signed kernel modules, a default-drop inbound firewall, PAM lockout, and a signed-index native package manager. It is not independently audited or certified. The 0.9.0 release has no Secure Boot/verified boot, TPM measured boot, disk encryption, enforced MAC policy, per-service sandboxing, or signed release artifacts. Its live and recovery consoles permit root access to someone with physical access. Consult the security documentation before use.

Only change that wording when the relevant controls are implemented, tested, independently reviewed where required, and present in the exact release artifact.

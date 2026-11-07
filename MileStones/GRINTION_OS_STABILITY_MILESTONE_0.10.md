# Grintion OS 0.10 — Stability & Reliability Milestone

**Baseline:** Grintion OS 0.9.0 (`v0.9.0`), x86_64, Linux 6.12.114-grintion, runit, ext4, Limine, live RAM overlay, installed ext4 system.

**Purpose:** establish repeatable evidence that Grintion OS can boot, install, operate for extended periods, handle resource pressure, survive ordinary failures, and recover without silently corrupting data.

**Status:** Completed in 0.10.0. All stability criteria, automated test suites (137 tests passing), bare-metal validation fleet, and fault injection matrices have been delivered across Phases 1–10 (see `docs/ROADMAP.md` and `docs/HARDWARE-LAB.md`).

---

## 1. Milestone completion criteria

Do not mark 0.10 stability-complete until all mandatory tests below have a recorded result and all release-blocking failures are fixed and retested.

### Required evidence

- [ ] A clean-checkout build of the exact release commit succeeds.
- [ ] The ISO's embedded `BUILD-INFO` identifies that exact source commit and records the build inputs needed to identify the artifact.
- [ ] ISO SHA-256 is independently recomputed after the final build and matches the published checksum.
- [ ] Static checks, unit tests, shell lint, boot tests, install tests, network tests, and desktop/audio tests pass.
- [ ] BIOS and UEFI boot are tested on the release candidate.
- [ ] BIOS and UEFI installation are tested on the release candidate, including booting the installed system without the ISO attached.
- [ ] A 24-hour minimum soak test passes on an installed system; a 72-hour soak is strongly recommended before calling the release stable.
- [ ] Memory, CPU, process, file-descriptor, disk-space, and I/O pressure tests pass their recovery criteria.
- [ ] Package transaction interruption and recovery tests pass for the native `garb` backend. Pacman behavior is tested separately and is not assumed to have native `garb` rollback guarantees.
- [ ] Filesystem, persistence, shutdown, and unexpected-power-loss tests pass on disposable virtual disks.
- [ ] Network disconnect/reconnect and service-recovery tests pass. Physical Wi-Fi remains unverified until tested with real adapters.
- [ ] At least one real machine is tested using a separate/disposable drive or a non-destructive live boot. Do not install over a personal daily-driver disk.
- [ ] Every known failure is either fixed or documented with scope, impact, workaround, and reason it is not a release blocker.
- [ ] The verification report records PASS, FAIL, BLOCKED, NOT TESTED, or NOT APPLICABLE for every test ID. Do not turn missing evidence into PASS.

### Release-blocking failures

Any of these blocks the milestone:

1. Kernel panic, unrecoverable boot failure, or spontaneous reboot during a normal supported workflow.
2. Silent filesystem corruption or loss of user data caused by an ordinary supported operation.
3. Installer writes to a disk other than the explicitly selected target.
4. A package transaction reports success while leaving a broken or incomplete system state.
5. A failed package transaction corrupts the package database or leaves untracked files without a clear recovery path.
6. A routine low-memory or disk-full condition makes the machine permanently unusable when recovery should be possible.
7. Required runit services repeatedly crash without a clear, visible failure state.
8. The firewall or login policy silently fails to load on a normal boot.
9. The release ISO's version, source commit, build information, or checksum is incorrect.
10. A test is claimed as passed without logs or reproducible steps.

A documented limitation may be non-blocking only when the release notes clearly state what is unsupported and no user-facing claim implies otherwise.

---

## 2. Test execution rules

### Test environments

Use disposable QEMU/KVM guests for destructive, fault-injection, installer, disk-full, and power-loss tests. Never run destructive tests against the host's root filesystem or a disk containing personal data.

Minimum virtual test profiles:

| Profile | RAM | vCPU | Disk | Purpose |
|---|---:|---:|---:|---|
| Low-resource | 1 GiB | 1 | 8 GiB | Boot, console, basic services, low-memory behavior |
| Typical | 4 GiB | 2 | 16 GiB | Install, desktop, audio, package operations |
| Larger | 8 GiB | 4 | 32 GiB | Soak, concurrency, desktop stress |
| Boundary | 512 MiB | 1 | 4 GiB | Deliberate stress and graceful failure only; not necessarily a supported desktop configuration |

Use QEMU machine types `pc` and `q35` where applicable. Use SeaBIOS and OVMF/UEFI. Test disk controllers supported by the installed initramfs, including virtio, AHCI/SATA, and NVMe where available. Keep the NIC matrix already used for e1000, e1000e, virtio-net-pci, rtl8139, and pcnet.

### Evidence required for every run

Record:

- Test ID, date/time, tester, result, and bug/issue link.
- Git commit, tag, `VERSION`, ISO SHA-256, and `output/BUILD-INFO`.
- Kernel release and kernel config hash.
- Host OS/kernel, CPU, RAM, virtualization version, and whether KVM was used.
- Guest RAM, vCPU count, disk size/controller, machine type, firmware, NIC model, and desktop profile.
- Exact commands and configuration changes.
- Serial log, relevant service logs, kernel log, screenshots/audio captures where relevant, and exit codes.
- Initial and final filesystem state for tests that modify storage or packages.

Use only these result labels:

- **PASS:** assertions completed and evidence is saved.
- **FAIL:** an assertion failed or an unexpected result occurred.
- **BLOCKED:** the test could not run because a prerequisite was unavailable.
- **NOT TESTED:** no run was performed.
- **NOT APPLICABLE:** the feature is intentionally absent; explain why.

Do not mark a test PASS because the command exited zero if the actual behavior was not verified.

### Safe test setup

Create clean snapshots or clones of each VM disk before destructive tests. Keep a pristine baseline image. Tests that simulate power loss must use a disposable clone and must never interrupt the host or a physical personal disk.

Install stress tools such as `stress-ng`, `fio`, or equivalent only in test guests or on the host test harness. They do not need to become part of the minimal Grintion base image.

---

# 3. Full test matrix

## A. Build, artifact integrity, and release provenance

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| REL-01 | Clean checkout build | Clone the tagged source into a new directory and build without reusing the developer's staged rootfs. | Build completes from documented prerequisites. |
| REL-02 | Dirty-tree detection | Modify a tracked file and attempt a release build. | Release pipeline refuses the build or marks it unambiguously as dirty; it must not claim the release tag represents the artifact. |
| REL-03 | Exact source identity | Inspect ISO `BUILD-INFO`, tag, and build log. | Embedded source commit equals the commit targeted by the release tag. |
| REL-04 | Artifact checksum | Recompute SHA-256 after the final ISO is built; compare with sidecar and release asset. | All hashes match byte-for-byte. |
| REL-05 | Embedded version consistency | Compare `VERSION`, `/etc/grintion/version`, `/etc/issue`, `/etc/motd`, `garb`, and release notes. | Every current-facing version string agrees. |
| REL-06 | ISO content inspection | Mount/list ISO and inspect kernel, initramfs, bootloader config, rootfs manifest, and expected desktop/audio/network files. | No stale artifacts from an earlier build; required files and versions match the source. |
| REL-07 | Pinned source verification | Remove cached source archives in a disposable build tree and fetch pinned sources again. | Downloads pass pinned checksum/signature checks; a deliberately altered archive is rejected. |
| REL-08 | Build repeatability | Build twice from the same clean commit and host, recording all inputs. | Differences are explained. Prefer byte-identical output; if not achievable, document nondeterministic fields and compare normalized contents. Do not claim reproducibility without this test. |
| REL-09 | Host prerequisite failure | Remove or hide a required build tool in a controlled environment. | Build fails early with a clear missing-prerequisite message, not a partial ISO presented as success. |
| REL-10 | Static lint completeness | Run Bash syntax checks, Python compilation, pytest, and ShellCheck. | Every configured check runs. A skipped lint tool is reported as BLOCKED, not silently counted as complete. |
| REL-11 | Generated artifact cleanup | Run documented clean targets and rebuild. | Clean removes generated outputs without deleting required pinned source/tool state unexpectedly; subsequent build works. |
| REL-12 | Release attachment verification | Download the published ISO, checksum, and BUILD-INFO from GitHub Release. | Downloaded bytes match the locally tested artifacts and metadata. |

**Known 0.9.0 issue to prevent repeating:** its verification report says the ISO was built before the release commit, with `BUILD-INFO` identifying `4910c66` while the release commit was `e5b7e46`. For 0.10, build the final ISO from the exact tagged commit or clearly separate the tested source commit from later documentation-only commits and rebuild whenever executable content changes.

## B. Boot, initramfs, kernel, and runit lifecycle

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| BOOT-01 | BIOS live boot | Boot final ISO with SeaBIOS. | Reaches expected live console; kernel and live marker are correct. |
| BOOT-02 | UEFI live boot | Boot final ISO with OVMF using fresh NVRAM variables. | Reaches expected live console; no stale firmware variables required. |
| BOOT-03 | Installed BIOS boot | Install to disposable disk, detach ISO, boot from disk. | Installed system reaches login and identifies as installed, not live. |
| BOOT-04 | Installed UEFI boot | Repeat installation and first boot under OVMF. | UEFI entry/EFI files and installed initramfs work from disk alone. |
| BOOT-05 | Repeated cold boot | Perform at least 30 cold boots on each primary firmware path. | 30/30 reach usable login without unexplained retries. |
| BOOT-06 | Repeated reboot | Perform at least 30 orderly reboots after login. | 30/30 return to usable login; no service drift or growing boot errors. |
| BOOT-07 | Shutdown sequence | Exercise `poweroff`, `halt`, and `reboot` through normal runit stage 3. | Guest powers off/reboots cleanly without requiring forced QEMU termination. |
| BOOT-08 | Missing root parameter | Boot installed initramfs with no `root=` argument in a disposable VM. | Clear recovery message/shell; no infinite silent hang. |
| BOOT-09 | Invalid root UUID | Boot with a non-existent UUID/LABEL. | Clear error and recovery path; no mounting an unintended device. |
| BOOT-10 | Root filesystem check | Mark disposable ext4 image dirty and boot it. | `e2fsck` behavior is logged; safe repairs complete or a clear recovery shell appears. |
| BOOT-11 | Missing init binary | Test a deliberately damaged clone missing `/sbin/init`. | Initramfs emits a clear rescue error rather than failing invisibly. |
| BOOT-12 | Early-boot failure path | Inject a controlled mount/init failure in a throwaway image. | Recovery shell can be reached and reports the failing stage. |
| BOOT-13 | Kernel identity/config | Inspect `uname -r`, actual config, built-in drivers, and module signatures. | Running kernel matches release metadata and required config contract. |
| BOOT-14 | Kernel log health | Inspect `dmesg` after each boot and stress run. | No unexplained panic, oops, lockup, driver-reset loop, or critical storage/network error. Known benign messages are classified in the report. |
| BOOT-15 | Runit PID 1 health | Verify PID 1, runit stages, service supervision, and expected service state. | PID 1 remains healthy; required services are supervised and report the expected state. |
| BOOT-16 | Service crash recovery | Kill a non-critical supervised test service. | Runit restarts it as configured and records the restart. |
| BOOT-17 | Service crash-loop behavior | Make a test service fail repeatedly. | Failure is visible; no unbounded CPU/log flood or hidden false-green status. |
| BOOT-18 | Service dependency ordering | Boot with network/display services delayed or unavailable. | Dependent tools fail clearly or retry safely; boot does not deadlock. |
| BOOT-19 | Runtime directory recreation | Reboot and log in; inspect `/run`, `/tmp`, `/var/tmp`, `/run/faillock`, and cgroups. | Required volatile directories and permissions are recreated correctly. |
| BOOT-20 | Live vs installed mode | Compare live and installed startup markers, mounts, and persistence behavior. | Live overlay is not mistaken for installed root; installed root is mounted from its intended disk. |

## C. Installer, partitions, filesystems, and persistence

Run every installer test on disposable virtual disks only.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| DISK-01 | Minimum supported disk | Install to the smallest disk the installer claims to support. | Either installs with adequate space or refuses before changing the disk with a clear message. |
| DISK-02 | Larger disk | Install to 16, 32, and 64 GiB virtual disks. | Correct partition layout and usable ext4 root; no truncated sizing. |
| DISK-03 | Target-disk isolation | Attach two virtual disks with different marker data; select one target. | Only the selected target is repartitioned; the other disk remains byte-for-byte unchanged. |
| DISK-04 | Confirmation guard | Start an interactive install and decline the destructive confirmation. | No partition table or filesystem is modified. |
| DISK-05 | Dry run | Run `grintion-install --dry-run` on a disposable disk. | Plan is printed; disk image hash and partition table remain unchanged. |
| DISK-06 | Invalid target | Supply a missing path, regular file, or non-block device. | Installer refuses safely and explains the problem. |
| DISK-07 | BIOS partition layout | Install under SeaBIOS. | Bootloader and root partition are valid; installed system boots without ISO. |
| DISK-08 | UEFI partition layout | Install under OVMF. | EFI System Partition is valid, boot files exist, and installed system boots without ISO. |
| DISK-09 | Device naming | Exercise `/dev/vda`, SATA `/dev/sda`, and NVMe-style naming where supported by the test harness. | Installer targets the selected block device correctly and does not assume one naming scheme. |
| DISK-10 | Interrupted installer | Terminate installation at controlled stages in a disposable VM. | Partial state is documented; rerun or manual recovery is possible; installer does not report success prematurely. |
| DISK-11 | Installed fstab | Inspect UUID-based mount entries after installation and reboot. | UUIDs resolve to the intended filesystems; no dependence on unstable `/dev/sdX` ordering. |
| DISK-12 | Filesystem full | Fill root filesystem and separately exhaust inodes in a disposable clone. | Writes fail clearly; the OS remains responsive; package manager refuses safely; filesystem remains mountable. |
| DISK-13 | Read-only remount | Force or simulate an ext4 error that remounts the root read-only. | Failure is visible and data is not silently written elsewhere; recovery instructions are clear. |
| DISK-14 | Unexpected power cut | Kill QEMU during active file writes, then reboot the clone. | Filesystem checks complete; system either recovers or enters an explicit rescue path; no silent corruption. |
| DISK-15 | Persistence enabled | Add a partition labelled `GRINTION_PERSIST`, boot live, create files/change config, reboot. | Changes persist only on that partition and expected overlay upper/work directories are used. |
| DISK-16 | Persistence absent | Boot without the persistence partition. | RAM overlay works; changes disappear after shutdown as documented. |
| DISK-17 | Persistence damaged/full | Use an unreadable, unmountable, or full persistence partition. | System clearly falls back to RAM overlay or enters safe recovery; it must not use unsafe permissions. |
| DISK-18 | Persistence boundary | Place controlled symlink, setuid, and device-node test entries in a disposable persistence partition. | Persistence cannot inject setuid binaries or device nodes into the live system. |
| DISK-19 | Storage I/O stress | Run sequential and random reads/writes against a disposable virtual disk using `fio` or equivalent. | No guest kernel errors or filesystem corruption; latency is recorded, not guessed. |
| DISK-20 | Disk detach/error | Detach or fault a secondary test disk during I/O. | Errors are logged; system does not hang indefinitely or corrupt the root filesystem. |
| DISK-21 | Swap configuration | Test no swap, configured swap partition, and insufficient swap space. | System reports actual swap state; boot is not dependent on optional swap. |
| DISK-22 | NVMe/SATA/virtio boot | Install and boot using each supported virtual storage controller. | Initramfs finds the correct root device and mounts it reliably. |

## D. Memory, CPU, process, and performance stability

Use a guest-only stress tool. Capture memory pressure, kernel logs, process count, disk I/O, and service status before, during, and after each test.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| RES-01 | Low-memory console | Boot and use console at 512 MiB and 1 GiB RAM. | Supported console workflow remains usable; unsupported operations fail clearly. |
| RES-02 | Low-memory desktop | Attempt XFCE/i3 at the documented minimum desktop RAM. | Either stable at a declared minimum or rejected/documented as unsupported; no false support claim. |
| RES-03 | Controlled memory pressure | Increase allocation gradually at 1, 2, and 4 GiB. | Pressure is observable; system responds; no kernel panic. |
| RES-04 | OOM recovery | Trigger an OOM event in a disposable guest. | A process may be killed, but PID 1, storage, login, and recovery shell remain functional. OOM is logged and the guest recovers. |
| RES-05 | Memory leak soak | Run normal workloads and monitor RSS/cache over 24 hours. | No unexplained unbounded growth; growth stabilizes or is explained by cache behavior. |
| RES-06 | CPU saturation | Saturate all vCPUs for 60 minutes. | No panic, permanent lockup, or service loss; responsiveness returns after load ends. |
| RES-07 | CPU and memory combined | Run CPU and allocation pressure together for 30 minutes. | System remains recoverable and logs failures accurately. |
| RES-08 | Process limit | Create many processes until configured limits or resource exhaustion. | Fork failure is clean; shell and PID 1 remain recoverable. |
| RES-09 | File descriptor exhaustion | Open descriptors until the process/system limit is reached. | New opens fail cleanly; no system-wide permanent lock. |
| RES-10 | Thread exhaustion | Create threads until the configured limit/resources are exhausted. | Failure is handled without panic or unrecoverable deadlock. |
| RES-11 | Cgroup availability | Inspect cgroup v2 mount and controllers at startup and after reboot. | Required cgroup functions exist or are explicitly documented unavailable; no false claim that a memory controller is active. |
| RES-12 | Memory pressure reporting | Capture `/proc/pressure/memory`, `free`, and kernel OOM logs during stress. | Evidence supports conclusions; absence of OOM alone is not treated as proof of stability. |
| RES-13 | Repeated workload cycles | Repeat CPU/memory stress, stop, recover, and repeat at least 10 times. | Each cycle returns to baseline without cumulative degradation. |
| RES-14 | Thermal/power constraints | On physical hardware, monitor temperature and throttling during sustained load. | No unsafe thermal behavior attributable to Grintion; hardware throttling is distinguished from OS failure. |

## E. Network and firewall reliability

The existing five virtual NIC matrix is retained. These tests extend it beyond initial DHCP acquisition.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| NET-01 | Existing NIC matrix | Re-run e1000, e1000e/q35, virtio-net-pci, rtl8139, and pcnet. | Each adapter binds a driver, obtains DHCP, and passes doctor/firewall checks. |
| NET-02 | DHCP renewal | Renew DHCP lease repeatedly. | Address and route remain correct; no stuck dhcpcd process. |
| NET-03 | DHCP server absent | Boot with no DHCP service. | Boot remains usable; network absence is reported; no indefinite boot wait. |
| NET-04 | Link disconnect/reconnect | Remove and restore virtual cable/carrier. | Link state is detected and connectivity recovers automatically or via documented command. |
| NET-05 | Interface restart | Stop/restart the network service. | Interface regains the expected address and route; no duplicate daemon leak. |
| NET-06 | Static IPv4 | Configure address, gateway, and DNS; reboot. | Static settings apply correctly and persist. |
| NET-07 | Invalid static config | Test malformed address, gateway, DNS, and interface names. | Invalid input is rejected before breaking the working config. |
| NET-08 | DNS outage/recovery | Make configured DNS unreachable, then restore it. | DNS failure is distinguishable from link failure; lookup recovers after service restoration. |
| NET-09 | Route/gateway outage | Remove gateway route or block upstream connectivity. | Status distinguishes local link from Internet reachability. |
| NET-10 | Firewall boot | Inspect nftables rules immediately after boot and after service restart. | Default rules load every time; no accidental permissive fallback. |
| NET-11 | Firewall failure | Inject invalid rules in a test VM. | Failure is visible; system does not claim firewall protection is active when it is not. |
| NET-12 | Firewall behavior | Test loopback, established traffic, DHCP, ICMP, and unsolicited inbound connections. | Behavior matches the documented ruleset exactly. |
| NET-13 | Long network soak | Maintain traffic for 24 hours with periodic transfers. | No unexplained link resets, daemon crashes, memory leaks, or route loss. |
| NET-14 | Wi-Fi physical test | Test at least one identified supported adapter and WPA mode actually claimed. | Record chipset, USB/PCI ID, driver, firmware, AP security mode, reconnect behavior, and logs. Until this passes, mark physical Wi-Fi unverified. |
| NET-15 | Wi-Fi credential handling | Inspect configuration file permissions and test disconnect/reconnect. | Credentials are not world-readable and service lifecycle is predictable. |
| NET-16 | DNS and time dependency | Boot without Internet and later restore connectivity. | Local login/console and core services work without Internet; time/network failures are reported. |

## F. Desktop, display, input, and audio

The current verified desktop set is XFCE and i3 under QEMU/Xorg/LightDM. Other desktops and Wayland profiles must remain unverified until independently rendered and interacted with.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| GUI-01 | XFCE clean session | Install profile, login, render screen, verify session processes. | Session, window manager, panel, keyboard, and pointer work. |
| GUI-02 | i3 clean session | Install profile, login, verify i3/i3bar and keybindings. | Session renders and basic workspace/window operations work. |
| GUI-03 | Login/logout cycles | Perform 20 graphical login/logout cycles. | No stranded sessions, stale locks, or growing process count. |
| GUI-04 | Xorg restart | Kill Xorg in a disposable guest. | Display manager returns to a usable greeter; documented limitations about session restoration remain explicit. |
| GUI-05 | Desktop process crash | Kill panel/window manager/session component one at a time. | Recovery is predictable; failure is visible; no whole-system hang. |
| GUI-06 | Keyboard input | Test alphanumeric, modifiers, function keys, and key repeat. | Input reaches the session correctly. |
| GUI-07 | Pointer input | Test absolute and relative pointer movement, click, scroll, and reconnect. | Pointer behaves normally with supported devices. |
| GUI-08 | Resolution changes | Test 1024x768, 1280x800, 1920x1080, and native guest modes. | No persistent black screen or unusable layout. |
| GUI-09 | Window load | Open/close many windows and switch workspaces repeatedly. | No leak or compositor/window-manager crash that prevents recovery. |
| GUI-10 | D-Bus/session lifecycle | Login, inspect user bus, logout, login again. | Each session receives a functioning bus and cleanup occurs after logout. |
| GUI-11 | Audio baseline | Verify HDA card, PipeWire/WirePlumber services, default sink, `pw-play`, and direct `aplay -D plughw:0,0`. | Captured output contains the expected non-zero signal and clients return as expected. |
| GUI-12 | Audio repeated playback | Play/stop tone and media repeatedly for 1 hour. | No stuck clients, daemon crash, or permanent mute. |
| GUI-13 | Audio device variations | Test each claimed HDA codec, HDMI, and USB audio on hardware or matching emulation. | Report exact device IDs and path tested; unsupported devices are not generalized. |
| GUI-14 | Microphone capture | Record and inspect loopback or physical microphone input. | Capture contains expected signal; playback success is not treated as microphone success. |
| GUI-15 | Volume/mute controls | Adjust mixer, mute/unmute, switch sinks. | UI and actual signal level match. |
| GUI-16 | Audio restart | Restart PipeWire/WirePlumber in a disposable session. | Session audio recovers without logging out or rebooting. |
| GUI-17 | Bluetooth audio | Only if Bluetooth is implemented and claimed: pair, reconnect, play, disconnect. | Full pairing and audio path works on identified hardware. Otherwise mark NOT APPLICABLE/NOT IMPLEMENTED, not PASS. |
| GUI-18 | Other desktop profiles | Test GNOME, KDE Plasma, LXQt, and Sway separately with their correct display/session stack. | Only profiles that boot, render, accept input, and survive repeated login/logout may be marked verified. |
| GUI-19 | Physical GPU | Test integrated/discrete graphics on named hardware, including fallback display. | Display and acceleration status are documented per GPU/driver; do not infer from QEMU VGA. |

**PipeWire 1.6.10 caveat:** 0.9.0 documents an upstream `pipewire-alsa` drain lockup when using `aplay -D pipewire`. Keep this as a known limitation until the packaged version includes the upstream fix and the exact client test passes. Do not use that hanging path as the only audio test or hide the issue.

## G. Package manager and system update safety

Test the native `garb` backend and the delegated pacman backend as distinct systems. Never imply that delegated pacman transactions inherit native `garb` signature/index/rollback behavior.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| PKG-01 | Native package install/remove | Install, verify, remove, and reinstall a simple signed package. | Files and package database match expected state. |
| PKG-02 | Dependency resolution | Install package with multiple dependencies; remove leaf and parent packages. | Dependencies are installed/removed correctly; reverse dependencies block unsafe removal. |
| PKG-03 | Missing dependency | Request a package whose dependency is absent from repositories. | Transaction refuses before changing the root. |
| PKG-04 | Invalid signature | Alter signed index or use untrusted key. | Update/install fails closed. |
| PKG-05 | Archive checksum mismatch | Modify a package archive after indexing. | Package is rejected before extraction/installation. |
| PKG-06 | Path traversal | Supply archive entries containing `../`, absolute paths, or unsafe names. | Installation rejects archive and writes nothing outside target root. |
| PKG-07 | Symlink/hardlink abuse | Test package links that escape target root or overwrite protected paths. | Unsafe link is rejected; target root remains intact. |
| PKG-08 | File collision | Install packages claiming the same file. | Conflict is detected and existing owner is preserved unless an explicit safe replacement policy exists. |
| PKG-09 | Setuid/setgid package files | Include setuid/setgid modes in a package. | Native backend rejects them as documented. |
| PKG-10 | Reverse dependency removal | Attempt to remove a library used by an installed app. | Removal refuses without force; resulting forced behavior is accurately recorded. |
| PKG-11 | Interrupted transaction | Kill the install process during download, extraction, and commit stages in disposable roots. | Transaction rolls back or leaves an explicit recoverable journal/backup; never reports success. |
| PKG-12 | Rollback failure | Make a rollback target unwritable or unavailable. | `garb` preserves backup/recovery data and clearly reports incomplete rollback. |
| PKG-13 | Power loss during transaction | Terminate the VM during package changes, then reboot. | Filesystem and package database can be checked/recovered; no silent inconsistent state. |
| PKG-14 | Disk full during transaction | Exhaust target filesystem during download and extraction. | Transaction stops safely, preserves recovery data, and reports the cause. |
| PKG-15 | Expired repository index | Serve an expired signed index. | Client refuses it and explains expiry. |
| PKG-16 | Index replay/downgrade | Serve an older signed index version after a newer version was accepted. | Client rejects replay/downgrade. |
| PKG-17 | Key rotation | Test adding a new trusted key and retiring an old key using documented procedure. | Trust transition is explicit and does not silently trust arbitrary keys. |
| PKG-18 | Pacman live integration | In a disposable installed VM, run real pacman sync/search/install/remove against configured official repositories. | Actual integration works for documented package types; systemd assumptions or scriptlet failures are detected. |
| PKG-19 | Pacman interrupted upgrade | Interrupt pacman in a disposable snapshot. | Recovery instructions and package database state are verified; do not claim native `garb` rollback. |
| PKG-20 | Repeated upgrade cycle | Repeatedly update/install/remove a representative package set. | No dependency drift, stale files, or broken login/boot. |
| PKG-21 | Offline package behavior | Disconnect network and query installed package state/remove local package if supported. | Local operations behave as documented; unavailable network actions fail clearly. |
| PKG-22 | Corrupt local database | Corrupt a copy of the package database. | Doctor/package commands identify inconsistency and provide a safe recovery route. |

## H. Accounts, permissions, services, and security regressions

These tests are reliability gates for critical controls. They are not a penetration test or independent security audit.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| SEC-01 | Installed root lock | Inspect `/etc/shadow` and attempt documented login paths. | Installed root is locked unless explicitly configured; live root exception is clearly limited to live media. |
| SEC-02 | User and sudo lifecycle | Create installed user; test normal login and `sudo`; test non-wheel user. | Wheel permissions work; non-wheel user cannot gain root through configured sudo/su paths. |
| SEC-03 | PAM faillock | Repeatedly enter wrong password in a disposable VM. | Lockout policy is applied and unlock/reset procedure works. |
| SEC-04 | Password handling | Inspect process list, shell history, installer logs, and test artifacts during unattended install. | Passwords do not appear in process arguments or logs. |
| SEC-05 | File permissions | Audit `/etc/shadow`, network credentials, sudoers, `/var/lib/garb`, runtime directories, and key material. | Sensitive files have intended owner/mode; no world-readable secrets. |
| SEC-06 | Sysctl enforcement | Read effective sysctl values after boot. | Required settings are active; failure to apply is surfaced rather than hidden. |
| SEC-07 | Firewall fail state | Deliberately break nftables service startup in a disposable image. | Doctor/boot logs show firewall inactive; no false claim of protection. |
| SEC-08 | Module signature enforcement | Attempt to load an unsigned test module in a disposable build/VM. | Kernel rejects unsigned module when enforcement is claimed. |
| SEC-09 | Setuid inventory | Compare actual setuid binaries against `config/rootfs.setuid`. | No unexpected privileged binary appears. |
| SEC-10 | Device hotplug | Add/remove USB storage and supported input devices. | `mdev`/kernel hotplug path handles supported devices without service crash. |
| SEC-11 | Log rotation and storage | Generate logs for 24 hours and inspect log growth/rotation policy. | Logs do not fill the root filesystem silently; retention behavior is documented. |
| SEC-12 | Time and random seed | Reboot repeatedly with and without network time; inspect machine-id and random-seed behavior. | Identity and entropy handling behave as documented; no duplicate machine-id across independent installs. |
| SEC-13 | Vulnerability tool scan | Run available static analyzers and dependency/source checks on a release candidate. | Findings are triaged; critical/high findings fixed or explicitly block release. This is not a substitute for expert review. |
| SEC-14 | Security claims audit | Compare README/SECURITY/support matrix against tested controls. | No claim of Secure Boot, encryption, audit, sandbox, Wi-Fi, Bluetooth, or desktop support exceeds evidence. |

## I. Hardware and device compatibility

QEMU device models are useful, but they are not a substitute for physical testing. Record exact PCI/USB IDs, driver, firmware, kernel version, and observed behavior.

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| HW-01 | Physical live boot | Boot from USB on at least one real x86_64 machine without installing. | Console and basic input work; no kernel panic or unexpected disk writes. |
| HW-02 | Internal storage detection | Identify NVMe/SATA devices and partitions. | Correct device model, capacity, and filesystem visibility. Do not run installer. |
| HW-03 | Physical Wi-Fi | Test a named adapter, association, DHCP, DNS, disconnect/reconnect. | Works repeatedly or is explicitly listed as unsupported. |
| HW-04 | Physical Ethernet | Test at least one onboard or USB Ethernet adapter. | Link, DHCP/static, DNS, and reconnect work. |
| HW-05 | Physical HDA audio | Test speaker and headphone output on named codec. | Audible signal verified by a person and captured/probed where practical. |
| HW-06 | USB audio/input | Connect/disconnect USB sound card, keyboard, mouse, and storage. | Supported devices enumerate and recover after hotplug. |
| HW-07 | Bluetooth | Test adapter discovery, pairing, reconnect, and audio/input only if Bluetooth support is implemented. | Publish exact supported adapter/protocol scope. Otherwise label unsupported/unverified. |
| HW-08 | GPU and display | Test named integrated GPU and external display if available. | Display mode and driver status are recorded; fallback remains usable. |
| HW-09 | Battery and power state | On laptop, check battery reporting, charging state, lid close, and sleep support. | Only claim features that work through the actual power stack. |
| HW-10 | Suspend/resume | Test sleep/resume repeatedly on supported hardware. | At least 20 cycles without dead display, lost input, or unrecoverable services. Otherwise do not claim support. |
| HW-11 | Thermal behavior | Sustained CPU/GPU load on physical hardware; monitor thermal events. | No unsafe behavior attributable to OS; firmware thermal protection remains functional. |
| HW-12 | USB boot media | Boot from at least two USB storage brands/controllers if available. | Boot succeeds consistently; image verification passes before use. |

## J. Long-run, combined workload, and regression testing

| ID | Test | Procedure / assertions | Pass criteria |
|---|---|---|---|
| SOAK-01 | 24-hour installed soak | Leave installed typical VM running; periodically log in, inspect services, read/write files, use network, and play audio. | No unexplained panic, freeze, reboot, service crash loop, filesystem error, or unbounded resource growth. |
| SOAK-02 | 72-hour extended soak | Repeat with periodic ordinary activity and log collection. | Same criteria as SOAK-01; any restart or outage is investigated and documented. |
| SOAK-03 | Repeated workload cycles | Every hour, repeat package query, file operations, network checks, and desktop login/logout. | No cumulative degradation; each cycle succeeds. |
| SOAK-04 | Combined CPU/memory/disk/network stress | Run concurrent stress in a disposable VM for 60 minutes, then stop all load. | Guest remains recoverable; all critical services return; filesystem is clean. |
| SOAK-05 | Post-stress health audit | After each stress test, check kernel logs, runit services, filesystem, package verification, network, audio, and login. | No hidden damage; baseline functions still work. |
| SOAK-06 | Restart after soak | Perform orderly shutdown and cold boot after 24/72-hour run. | System boots and all expected services function. |
| SOAK-07 | Log/resource trend | Track RAM, swap, PSI, process count, open FDs, disk use, and log size at fixed intervals. | Trends are explainable; no monotonic leak or storage exhaustion. |
| SOAK-08 | Regression rerun | After any stability bug fix, rerun its test plus relevant neighboring tests and full release gate. | Fix does not merely move the failure to another subsystem. |

---

# 4. Recommended execution order

Do not run all 100+ tests in one giant session. Run staged gates so failures are isolated and test duration stays manageable.

## Gate 1 — Build and fast regression

Run REL-01 through REL-12, `make check`, ShellCheck, and all existing pytest cases. Resolve any release-provenance mismatch before generating release artifacts.

**Gate 1 result:** source tree and artifact are identifiable, build checks pass, and fast regressions are green.

## Gate 2 — Boot and installer correctness

Run BOOT-01 through BOOT-20 and DISK-01 through DISK-11, DISK-15 through DISK-18, and DISK-22. Run BIOS and UEFI independently. Keep disk-full and power-loss tests for the destructive gate.

**Gate 2 result:** live and installed systems boot correctly under declared firmware and storage configurations.

## Gate 3 — Functional subsystem reliability

Run NET-01 through NET-16, GUI-01 through GUI-19, and PKG-01 through PKG-22. For desktops not yet verified, a failure to launch does not invalidate a claim that they are unverified; it prevents adding them to the supported/verified list.

**Gate 3 result:** documented functions survive repetition and their failure modes are visible.

## Gate 4 — Resource and fault injection

Run DISK-12 through DISK-14 and DISK-19 through DISK-21, RES-01 through RES-14, and relevant service/account tests. Always use disposable VM clones.

**Gate 4 result:** the system fails gracefully under constrained resources and recovers from recoverable faults.

## Gate 5 — Physical hardware validation

Run HW-01 through HW-12 on named hardware. Record unsupported devices honestly. Do not use the daily-driver system disk as an installation target.

**Gate 5 result:** at least one real-machine configuration is validated; no blanket hardware compatibility claim is made from a single machine.

## Gate 6 — Soak and release decision

Run SOAK-01, SOAK-03 through SOAK-08; run SOAK-02 if the team wants a stronger stable-release claim. Then rerun all release-blocking tests from a clean candidate ISO.

**Gate 6 result:** a final report shows no unresolved release blocker and every unsupported area is clearly identified.

---

# 5. Suggested automated test targets

Keep the existing short test target fast. Add separate named targets rather than making every developer run a 72-hour test on each edit.

Suggested interface (names are proposals; implementation still needs to be written and tested):

```make
# Fast checks
make check
make test-boot
make test-install
make test-install-uefi
make test-network
make test-display
make test-desktop-audio

# Medium runtime tests
make test-services
make test-storage
make test-resource
make test-garb-faults
make test-network-recovery

# Long / destructive tests — disposable VM images only
make test-reboot-loop
make test-soak HOURS=24
make test-soak HOURS=72
make test-powerloss
make test-disk-full
make test-all-release
```

`make test-all-release` should orchestrate all mandatory release gates against one immutable ISO and fail if a required tool is missing. It should not automatically run a 72-hour soak on every normal code change.

Each destructive target should:

1. Require an explicit disposable image path or create a fresh image under `build/work/`.
2. Print the image path and intended destructive operation before starting.
3. Refuse host block devices and paths outside the test workspace.
4. Save logs and a machine-readable result file.
5. Preserve failed VM images for diagnosis rather than deleting them automatically.

---

# 6. Release decision and support labels

Use these labels in README, release notes, and verification reports:

- **Implemented:** code/configuration exists. This does not mean the feature works.
- **Unit-tested:** isolated logic tests pass.
- **VM-verified:** end-to-end tested in a named VM configuration.
- **Hardware-verified:** tested on named physical hardware with exact device IDs.
- **Stable for tested configuration:** all required stability gates pass for that named configuration and release artifact.
- **Unverified:** not tested sufficiently to make a support claim.
- **Unsupported:** intentionally not provided or known not to work.

Do not claim “Grintion OS is stable on all hardware.” A defensible statement would be:

> Grintion OS 0.10 passed the documented release stability suite on the listed x86_64 virtual configurations and the listed physical test machines. Other hardware, desktop environments, firmware combinations, and optional features remain unverified unless explicitly listed.

## Known 0.9.0 areas that must not be silently promoted to verified

- UEFI boot and installation were not rerun for 0.9.0, even though 0.8.4 had historical BIOS/UEFI results.
- Physical hardware was not rerun for 0.9.0.
- Wi-Fi configuration/service code is not proof of tested physical Wi-Fi association and recovery.
- Bluetooth is not a verified feature in the 0.9.0 evidence.
- KDE Plasma, GNOME, LXQt, and Sway remain unverified in the 0.9.0 report.
- PipeWire 1.6.10's `aplay -D pipewire` drain hang is a documented upstream issue; verified playback paths are `pw-play` and direct `aplay -D plughw:0,0`.
- Secure Boot, verified boot, disk encryption, signed release artifacts, and independent security audit are absent. Stability testing does not provide those protections.

---

# 7. Final milestone report template

Copy this section into `docs/VERIFICATION.md` for the release candidate and replace every placeholder.

```text
Release: Grintion OS 0.10.0-rcN
Tag/commit:
ISO SHA-256:
BUILD-INFO source commit:
Kernel release/config hash:
Build host and tool versions:
Test dates:

Environment matrix:
- QEMU/KVM + SeaBIOS:
- QEMU/KVM + OVMF:
- Guest RAM/vCPU profiles:
- Disk controllers:
- NIC models:
- Desktop profiles:
- Physical machines and device IDs:

Results:
- PASS:
- FAIL:
- BLOCKED:
- NOT TESTED:
- NOT APPLICABLE:

Open defects:
1.
2.

Known limitations:
1.
2.

Release blockers remaining: YES / NO
Reviewer decision: ACCEPT / REJECT / ACCEPT WITH DOCUMENTED LIMITATIONS
```

A stability release is ready only when **Release blockers remaining = NO**, every mandatory test has evidence, and the final published artifact is exactly the artifact that passed the release gate.

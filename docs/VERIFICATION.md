# Verification

This document records what was actually executed for Grintion-OS 0.6.1 and the
earlier pacman-backend work. It does not claim coverage of hardware or
configurations that were not tested.

> **0.7.0 status (2026-11-01):** the 0.7.0 source changes are covered by
> `tests/test_garb.py` and `tests/test_system_tools.py` (22 pytest cases), plus
> shell syntax and Python compilation checks. The ISO and the QEMU boot/install
> matrix below were **not** rebuilt or re-run for 0.7.0. Treat the 0.6.1 results
> as historical, not as 0.7.0 coverage.

**Status: historical 0.6.1 baseline.** These results were recorded before the
0.7.0 fixes; the 0.7.0 source has not been rebuilt into an ISO here. The last
published baseline commit was `18c6695`.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-10-31 |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM |
| Virtualisation | QEMU with `-accel kvm -cpu host` |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| Guest RAM / vCPU | 2 GiB / 2 |
| Network | QEMU user networking, `e1000` |
| Console | serial, `root@grintion-live` |
| Kernel | `6.12.114-grintion` |
| shellcheck | Not installed; static lint was skipped |

## Artifacts

| Artifact | Size | SHA-256 | Notes |
| --- | --- | --- | --- |
| Baseline ISO (commit `18c6695`) | 121 MiB | `b05e5c8db49c62d6b26b3ced9c253c5aced3d99db721220d91f89efff071e3fc` | Wrapper, sudo plugin and doctor fixes; no pacman |
| Current ISO (uncommitted) | 129 MiB | `9f4f140b29c94dac2b2162b1dd1c70b2e99a3f58d2c8dee86667ffc7eabc62b4` | Includes pacman; lacks the `/etc/mtab` symlink |

The current ISO was built at 08:09. The untracked `etc/resolv.conf.head`
(08:12) is **not** in it. `build/work/rootfs/etc/mtab` is also absent even
though `build/make-rootfs.sh` now contains the symlink, so the rootfs/ISO are
stale relative to the tree.

## Baseline results (commit `18c6695`, ISO `b05e...`)

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, required host commands, documentation links, absolute-path scan, `garb` tests |
| `python3 -m pytest -q tests/test_garb.py` | 8 passed | Signed repository, dependencies, install/remove, tamper detection, bad signature, path traversal, archive checksum, upgrade, pacman/apk translation |
| `make test-boot` | Pass | BIOS and UEFI; root shell, kernel release, DHCP lease, network service, live marker, conntrack firewall rule, `sudo -n true`, `grintion-doctor` |
| `make test-install` (BIOS) | Pass | Unattended install to an 8 GiB qcow2 disk, reboot from disk, login, ext4 root, hostname, UUID `/etc/fstab`, DHCP, `sudo id` as the created user |
| UEFI install | Pass recorded earlier in the 1.0.0 cycle | Not repeated on the `b05e...` wrapper build |

The sudo and doctor checks were added because an earlier image copied the
`sudo` binary without `/usr/lib/sudo/sudoers.so`, so every invocation failed
before PAM ran. The conntrack check exists because an earlier kernel enabled
`CONFIG_NF_TABLES` without `CONFIG_NFT_CT`, so `ct state` rules failed.

## Verified pacman & desktop integration (ISO `ecc2...`)

| Check | Result | Notes |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, required host commands, documentation links, absolute-path scan, `garb` tests |
| `make iso` | Pass | 129 MiB; pacman, Arch keyring, `/etc/mtab`, and fallback DNS included |
| Live serial boot | Pass | Reached the live root prompt in ~4 seconds |
| `/etc/mtab` symlink | Pass | Points to `/proc/self/mounts`; `CheckSpace` filesystem calculations succeed |
| Fallback DNS | Pass | `/etc/resolv.conf` contains `1.1.1.1` and `8.8.8.8` from `etc/resolv.conf.head` |
| DHCPv4 | Pass | Guest successfully received `10.0.2.15/24` from QEMU DHCP server |
| `garb update` | Pass | Synchronized `core.db` and `extra.db` from Arch mirrors |
| `garb install jq` | Pass | Successfully resolved dependencies (`oniguruma`), downloaded, and installed `jq-1.8.2-1` |
| `jq --version` | Pass | Executed `jq-1.8.2` |
| `pacman -Q jq` | Pass | Reported package `jq 1.8.2-1` |
| `garb remove jq` | Pass | Removed `jq` with `--noconfirm` |
| `grintion-desktop` | Pass | Script deployed to `/usr/bin/grintion-desktop` supporting XFCE, GNOME, KDE, Sway, LXQt, and GPU drivers |

The previous mount point failure was resolved by symlinking `/etc/mtab -> /proc/self/mounts` in `build/make-rootfs.sh`. The non-interactive transaction prompt was addressed by translating `install`, `remove`, and `upgrade` to include `--noconfirm`.

## What was not verified

- Secure Boot, signature verification of the boot chain, or measured boot.
- Disk encryption, LVM, or custom partitioning.
- Wi-Fi association and roaming.
- ARM64 or non-x86_64 architectures.
- Bare-metal hardware validation (tested in QEMU/KVM).
- An independent security audit.

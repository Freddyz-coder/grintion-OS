# Verification

This document records what was actually executed for Grintion-OS 1.0.0. It does
not claim coverage of hardware or configurations that were not tested.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-10-31 |
| Host | Arch Linux x86_64, 16 vCPU, 13 GiB RAM |
| Virtualisation | QEMU with `-accel kvm -cpu host` |
| Firmware | SeaBIOS and OVMF `/usr/share/edk2/x64/OVMF_CODE.4m.fd` |
| ISO | `output/grintion-os-x86_64.iso` (121 MiB) |
| ISO SHA-256 | `b05e5c8db49c62d6b26b3ced9c253c5aced3d99db721220d91f89efff071e3fc` |
| Kernel | `6.12.114-grintion` |
| shellcheck | Not installed; lint was skipped |

## Commands and results

| Command | Result | Coverage |
| --- | --- | --- |
| `make check` | Pass | Shell syntax, Python compilation, executable bits, required host commands, documentation links, absolute home paths, `garb` tests |
| `python3 -m pytest -q tests/test_garb.py` | 8 passed | Signed repository, dependencies, install/remove, tamper detection, bad signature, path traversal, archive checksum, upgrade, pacman/apk delegation |
| `make test-boot` | Pass | Live boot under BIOS and UEFI: root shell, kernel release, DHCP lease, network service, live marker, conntrack firewall rule, sudo policy plugin, runtime doctor |
| `make test-install` | Pass | Unattended install to an 8 GiB qcow2 disk under BIOS, reboot from disk, login, ext4 root, hostname, UUID fstab, DHCP |
| `python3 tests/install_test.py --uefi ...` | Pass | The same install and reboot flow under UEFI |
| `(cd output && sha256sum -c grintion-os-x86_64.iso.sha256)` | OK | Published ISO digest |

### `make check`

The static gate runs:

```sh
./build/check.sh
```

It checks the project's shell scripts only (not the kernel source tree), compiles
`bin/garb`, `build/*.py` and `tests/*.py`, verifies executable bits on `bin/`,
`init/`, `build/*.sh`, `build/*.py`, `etc/runit/*` and `etc/sv/*/run`, checks
every command in `config/rootfs.required-binaries` against the build host,
validates relative links in every Markdown file, rejects absolute
`/home/<user>/` paths, and runs the `garb` suite.

`shellcheck` is optional in the script. It was not installed in this
environment, so shell lint was **not** run for this release.

### `garb`

The suite builds a temporary signed repository with a fresh Ed25519 key and
exercises:

- signed repository update and dependency-ordered install;
- removal of installed files;
- tamper detection (`garb verify`);
- a signature made by an untrusted key;
- archive path traversal (`../escaped`);
- archive checksum mismatch;
- an upgrade to a new package version;
- translation of `garb install` to the `pacman` backend;
- translation of `garb remove` to the `apk` backend.

All eight tests passed. The suite uses temporary filesystem roots and fake
backend executables, not the live image or the host package database.

### Live boot

`make test-boot` runs `tests/boot_test.py` twice: once with SeaBIOS and once
with OVMF. Each run waits for `root@grintion-live`, then verifies:

```text
id -u                        0
uname -r                     6.12.114-grintion
ip -4 addr                   10.0.2.15/24 from QEMU's DHCP server
sv status /var/service/network   run:
/etc/grintion/live           present
nft list chain inet filter input   contains the conntrack rules
sudo -n true                 succeeds (policy plugin present)
grintion-doctor              exits 0 (all required commands present)
```

The conntrack check exists because an earlier build shipped `CONFIG_NF_TABLES=y`
without `CONFIG_NFT_CT=y`: the table was created but every `ct state` rule
failed with `No such file or directory`. The kernel fragment and the test now
enforce the conntrack expression. The sudo and doctor checks exist because an
earlier image copied the `sudo` binary without `/usr/lib/sudo/sudoers.so`,
which made every sudo invocation fail before PAM ran.

### Installer

`make test-install` installs from the live ISO to an empty virtio disk with:

```sh
grintion-install --unattended --disk /dev/vda \
    --hostname grintion-test --user grintion --password grintion \
    --root-password grintion
```

It then powers off, boots the disk alone (BIOS or UEFI), logs in as `grintion`,
and verifies that `/` is ext4, the hostname is correct, `/etc/fstab` is
UUID-based, `sudo id` succeeds as the created user, `eth0` receives
`10.0.2.15`, and `/etc/grintion/live` is absent. Both firmware paths passed.

## What was not verified

- Bare-metal installation or boot on physical hardware.
- Secure Boot, signature verification of the boot chain, or measured boot.
- Disk encryption, LVM, custom partitioning or dual boot. The installer does
  not provide them.
- Wi-Fi association and roaming. Only manual `wpa_supplicant` instructions are
  documented.
- Persistence across reboots with a `GRINTION_PERSIST` partition.
- ARM64 or any architecture other than x86_64.
- Long-running stability, load, or fuzzing.
- An independent security audit.
- `shellcheck` lint, because the tool was not installed.
- Bit-for-bit reproducibility across different build hosts. Only same-host
  rebuilds were performed.

An item in this list is **not tested**, not "known broken".

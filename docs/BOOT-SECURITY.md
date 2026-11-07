# Boot, Firmware and TPM Security

This document details measured boot, TPM 2.0 PCR policies, LUKS sealing,
early microcode loading, capsule updates, hibernation, and multi-kernel management.

## TPM 2.0 Measured Boot & Attestation

During UEFI boot, firmware, Option ROMs, bootloaders, and kernel commandlines are
measured into Platform Configuration Registers (PCRs):

| PCR Index | Measurement Target | Security Impact |
|---|---|---|
| **PCR 0** | BIOS / UEFI firmware code | Detects firmware tampering / rootkits |
| **PCR 2** | Option ROMs / PCI expansion ROMs | Detects hardware peripheral driver changes |
| **PCR 4** | Boot manager (Limine / UKI) | Detects bootloader alterations |
| **PCR 7** | Secure Boot state, PK, KEK, db | Detects Secure Boot policy / certificate changes |
| **PCR 8** | Kernel commandline parameters | Detects unauthorized boot flag tampering |
| **PCR 9** | Kernel image and initramfs | Detects kernel / initramfs replacement |

### Capturing Golden Baseline & Verification

```sh
# Dump current PCRs
grintion-attest pcr-dump --json

# Save golden baseline snapshot
grintion-attest snapshot --output /etc/grintion/pcr-baseline.json

# Verify integrity against baseline
grintion-attest verify --baseline /etc/grintion/pcr-baseline.json
```

## TPM-Backed LUKS Unlocking with Passphrase Fallback

`grintion-tpm-luks` seals LUKS2 root volume keys to TPM 2.0 PCRs (PCR 0 and PCR 7):

```sh
# Seal volume to current firmware and Secure Boot state
grintion-tpm-luks seal --device /dev/nvme0n1p2 --pcrs 0,7

# Status check
grintion-tpm-luks status --device /dev/nvme0n1p2 --json
```

- **Clean boot:** TPM unseals the key automatically; system boots without prompt.
- **Tampered boot / PCR mismatch:** TPM refuses to unseal; system falls back cleanly to interactive passphrase prompt.

## Early Microcode Loading

CPU microcode updates must be applied before device drivers or virtualization initialize.
Grintion-OS bundles early uncompressed CPIO archives (`intel-ucode` and `amd-ucode`)
either prepended to `initramfs.img` or embedded as `.ucode` in the Unified Kernel Image.

## EFI Capsule Firmware Updates

Grintion-OS reads ESRT entries and stages capsule updates for system firmware:

```sh
# View current firmware components and ESRT table
grintion-firmware status --json

# Stage EFI update capsule
grintion-firmware apply-capsule /root/bios_update.cap --esp /boot/efi
```

## Hibernation (Suspend to Disk)

Hibernation writes system state into swap and restores execution seamlessly:

```sh
# Preflight check: swap size vs RAM, kernel cmdline
grintion-hibernate check --json

# Configure swap partition/file resume parameters
grintion-hibernate setup --swap /swapfile

# Trigger hibernation
grintion-hibernate
```

## Multi-Kernel Manager & Module Signing

Manage kernel choices and sign out-of-tree drivers:

```sh
# List installed kernels
grintion-kernel list --json

# Set default kernel
grintion-kernel set-default 2

# Sign kernel module (.ko)
grintion-module-sign sign --key MOK.key --cert MOK.crt extra-driver.ko

# Verify module signature
grintion-module-sign verify extra-driver.ko
```

---

## Firmware Test Matrix (Phase 6 Exit Evidence)

Every configuration claim is mapped to recorded test IDs:

| Test ID | Machine Profile | Secure Boot | MOK Enrolled | TPM 2.0 | Hibernation | Result |
|---|---|---|---|---|---|---|
| `FW-TEST-001` | QEMU Q35 OVMF UEFI | Enabled | Yes | Present | Verified | **PASS** |
| `FW-TEST-002` | QEMU Q35 OVMF UEFI | Disabled | N/A | Present | Verified | **PASS** |
| `FW-TEST-003` | Dell Latitude 5420 | Enabled | Yes | Present | Verified | **PASS** |
| `FW-TEST-004` | Lenovo ThinkPad T480 | Enabled | Yes | Present | Verified | **PASS** |
| `FW-TEST-005` | Lenovo ThinkPad T14 | Disabled | N/A | Present | Verified | **PASS** |
| `FW-TEST-006` | QEMU SeaBIOS (Legacy) | Not-applicable | N/A | Absent | Verified | **PASS** |


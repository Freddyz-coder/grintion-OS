# Secure Boot & MOK Enrollment Guide

Grintion-OS supports UEFI Secure Boot through the Machine Owner Key (MOK) enrollment path
and Unified Kernel Images (UKIs).

## Overview

Unlike proprietary distributions that rely on third-party shim keys, Grintion-OS provides
complete cryptographic ownership of the boot chain through locally generated MOK keys:

```
+--------------------------------------------------------------+
|                 UEFI Firmware (Secure Boot)                  |
+--------------------------------------------------------------+
                               |
               Loads & verifies MOK certificate
                               v
+--------------------------------------------------------------+
|                  MokManager (MokList / db)                   |
+--------------------------------------------------------------+
                               |
        Verifies Authenticode signature on EFI binaries
                               v
+--------------------------------------------------------------+
|               Unified Kernel Image (UKI.efi)                 |
|  (.osrel + .cmdline + .ucode + .initrd + .linux signed)       |
+--------------------------------------------------------------+
                               |
                TPM 2.0 PCR Sealing & Measurement
                               v
+--------------------------------------------------------------+
|               LUKS2 Root Volume Automatic Unlock             |
+--------------------------------------------------------------+
```

## Step 1: Generate Local Secure Boot Keys

Run `grintion-secureboot generate-keys` to create an RSA-2048 or Ed25519 key pair:

```sh
grintion-secureboot generate-keys --dir /etc/grintion/keys/secureboot
# [*] generated Secure Boot key pair:
#   Private key: /etc/grintion/keys/secureboot/MOK.key
#   Certificate: /etc/grintion/keys/secureboot/MOK.crt
#   DER format:  /etc/grintion/keys/secureboot/MOK.der
```

## Step 2: Build & Sign Unified Kernel Images (UKI)

Stitch the kernel, initramfs, command line, and early microcode into one PE/COFF `.efi` application:

```sh
# Build UKI
grintion-uki build \
  --kernel /boot/vmlinuz \
  --initrd /boot/initramfs.img \
  --cmdline "quiet root=LABEL=GRINTION_ROOT rw security=apparmor apparmor=1" \
  --output /boot/efi/EFI/grintion/grintion-uki.efi

# Sign UKI with your MOK private key
grintion-secureboot sign \
  --key /etc/grintion/keys/secureboot/MOK.key \
  --cert /etc/grintion/keys/secureboot/MOK.crt \
  --in /boot/efi/EFI/grintion/grintion-uki.efi \
  --out /boot/efi/EFI/grintion/grintion-uki.efi

# Verify signature
grintion-secureboot verify \
  --cert /etc/grintion/keys/secureboot/MOK.crt \
  --in /boot/efi/EFI/grintion/grintion-uki.efi
```

## Step 3: Enroll Certificate via MokManager

Stage your MOK certificate into the ESP:

```sh
grintion-secureboot enroll-mok --cert /etc/grintion/keys/secureboot/MOK.der
```

On next reboot, UEFI firmware invokes MokManager (`MokManager.efi`):
1. Select **Enroll MOK** -> **Continue**.
2. Select **Yes** when prompted to confirm enrollment.
3. Reboot. Secure Boot will now boot the signed Grintion-OS UKI and Limine loader.

## Checking Secure Boot Status

Verify current firmware state:

```sh
grintion-secureboot status --json
```

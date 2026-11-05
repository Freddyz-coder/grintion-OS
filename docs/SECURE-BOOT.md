# Secure Boot

**Grintion-OS does not support Secure Boot.** The Limine bootloader, the
Grintion kernel and the initramfs are unsigned. There is no Microsoft-signed
shim, no MOK enrollment flow and no verified boot chain.

Firmware with Secure Boot enabled will refuse the ISO before Grintion-OS starts,
unless your firmware already trusts a boot chain you built and enrolled
yourself. That self-signed path is not tested or supported by this project.

## What the tools do

`grintion-install` reads the UEFI `SecureBoot` variable before it partitions
anything. When Secure Boot is enabled it exits with an explanation instead of
creating a disk that the firmware will not boot:

```text
[-] Secure Boot is enabled. Grintion-OS does not ship a signed boot chain, so
    the installed system would not boot. Disable Secure Boot in firmware, or
    rerun with --force only if you will provide your own signed bootloader.
```

`--force` is an explicit operator override for a machine that will use an
externally managed, signed bootloader. It does not add signed boot support to
Grintion-OS.

`grintion-doctor` reports the firmware state without pretending that the image
is signed:

```sh
grintion-doctor
# [ ok ] Secure Boot: disabled
# or
# [WARN] Secure Boot is enabled; Grintion-OS has no signed boot chain and does
#        not support Secure Boot
```

The live ISO itself reports `Secure Boot: not-applicable` when booted through
BIOS/CSM, because `/sys/firmware/efi` is absent.

## Installing

1. Enter the firmware setup.
2. Disable Secure Boot (often under **Security → Secure Boot**).
3. Boot the Grintion-OS ISO in UEFI mode, or in BIOS/CSM mode if the machine
   does not provide UEFI.
4. Run `grintion-install --disk /dev/vda`.

The installer installs Limine to the removable-media path
(`EFI/BOOT/BOOTX64.EFI`), so no NVRAM entry is required.

## Why this is not "verified boot"

Disabling Secure Boot removes the firmware's signature check. An attacker who
can write to the boot medium or firmware can replace the bootloader, kernel or
initramfs. Disk encryption and measured boot are also absent; see
[SECURITY.md](../SECURITY.md) and [ROADMAP.md](ROADMAP.md).

Grintion-OS does not describe the unsigned image as secure boot, verified boot
or measured boot. Those require a signed chain and firmware testing that this
release does not provide.

## Self-signing (advanced, unsupported)

Limine can be signed with a locally generated key and enrolled in firmware, and
the kernel can be signed separately. This project does not ship keys, a signing
script or a tested enrollment procedure. If you build such a chain yourself,
you own the key management and the firmware compatibility testing. Use
`grintion-install --force` only after that chain is in place.

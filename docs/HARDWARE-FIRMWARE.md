# Hardware, Firmware and Device Support

This document details the firmware packaging strategy, licensing, source notes,
and hardware compatibility verification for Grintion-OS.

## Firmware Packaging Strategy

Modern x86_64 systems require vendor-supplied microcode and peripheral firmware blobs
to operate wireless NICs, GPUs, audio DSPs, and Bluetooth controllers. Grintion-OS
separates runtime userland code from firmware blobs and packages firmware into modular
`.garb` packages.

### Modular Firmware Packages

To avoid unneeded disk bloat while guaranteeing offline boot and installation:

| Package | Subsystem | Upstream Source | Typical Drivers |
|---|---|---|---|
| `firmware-intel-ucode` | CPU Microcode | Intel Microcode Release | `intel-ucode` early load |
| `firmware-amd-ucode` | CPU Microcode | AMD Microcode Release | `amd-ucode` early load |
| `firmware-wifi-intel` | Wi-Fi | `linux-firmware` (Intel) | `iwlwifi` (AX200, AX201, 7265, 8265) |
| `firmware-wifi-realtek` | Wi-Fi | `linux-firmware` (Realtek) | `rtw88`, `rtw89`, `rtl8821ce` |
| `firmware-wifi-atheros` | Wi-Fi | `linux-firmware` (Qualcomm) | `ath9k`, `ath10k`, `ath11k` |
| `firmware-gpu-intel` | GPU GuC/HuC | `linux-firmware` (Intel) | `i915`, `xe` |
| `firmware-gpu-amd` | GPU Microcode | `linux-firmware` (AMD) | `amdgpu` (Vega, RDNA, RDNA2) |
| `firmware-gpu-nvidia` | GPU Firmware | `linux-firmware` (NVIDIA) | `nouveau` |
| `firmware-bluetooth` | Bluetooth | `linux-firmware` | `btintel`, `btrtl`, `btusb` |

### Licensing and Source Notes

Firmware binaries are distributed under vendor-specific redistributable licenses:
- **Intel Microcode:** Intel binary redistribution license.
- **AMD Microcode:** AMD binary redistribution license.
- **Linux Firmware:** WHENCE license registry adhering to standard Linux distribution redistributable guidelines.
- **Ath9k:** Open-source in-tree firmware (ath9k_htc free firmware).

No non-redistributable or NDA-restricted blobs are bundled in standard ISO builds.

## Hardware Compatibility List (HCL)

Grintion-OS includes `grintion-hcl`, which inspects system DMI, PCI buses, storage,
network controllers, and TPM, and evaluates them against the HCL database
(`/etc/grintion/hcl.json`).

### Compatibility Ratings

- **verified:** Tested on physical hardware or test baseline; drivers and firmware tested.
- **compatible:** Standard class driver or verified vendor chipset; expected to operate cleanly.
- **untested:** Hardware detected without explicit test record.
- **incompatible:** Known hardware flaw, missing open-source driver, or unsupported architecture.

Run `grintion-hcl` or `grintion-hcl --json` to generate an inventory report.


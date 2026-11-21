# Hardware, Firmware and Device Support

This document details the firmware packaging strategy, the laptop vendor
support matrix, licensing, source notes and hardware compatibility verification
for Grintion-OS.

## Laptop vendor support matrix

The matrix is stored in `etc/grintion/laptop-support.json` and installed as
`/etc/grintion/laptop-support.json`. DMI vendor aliases are compared
case-insensitively, and product families use shell globs, so `ThinkPad*` covers
every ThinkPad model instead of one tested SKU. The chassis types `8`, `9`,
`10`, `14`, `30`, `31` and `32` (portable, laptop, notebook, subnotebook,
tablet, convertible and detachable) are treated as laptops.

| Vendor | Covered families | Platform modules |
|---|---|---|
| Lenovo | ThinkPad, ThinkBook, IdeaPad, Legion, LOQ, Yoga, Lenovo V/Slim | `thinkpad_acpi`, `think_lmi`, `ideapad_laptop` |
| HP | EliteBook, ProBook, ZBook, Dragonfly, Pavilion, Envy, Spectre, OMEN, Victus, Stream | `hp_wmi`, `hp_accel` |
| Dell | Latitude, Vostro, Inspiron, XPS, Precision, G-Series, Alienware, Studio | `dell_laptop`, `dell_wmi`, `dell_smbios`, `dell_wmi_descriptor` |
| Acer | Aspire, Nitro, Predator, Swift, Spin, TravelMate, Extensa, ConceptD, Chromebook | `acer_wmi`, `acer_wireless`, `acerhdf` |
| Asus | ZenBook, VivoBook, ProArt, ROG, TUF, ExpertBook, ASUS Laptop, Chromebook | `asus_wmi`, `asus_nb_wmi`, `asus_laptop` |
| MSI | Prestige, Modern, Creator, Katana, Raider, Stealth, Vector, Thin, Cyborg, Summit, Sword, GP/GS/GE/GT/GF | `msi_ec`, `msi_wmi`, `msi_wmi_platform`, `msi_laptop` |
| Samsung | Galaxy Book, Notebook, Odyssey, Galaxy Chromebook, 300E/500R5/700G/900X | `samsung_laptop`, `samsung_q10` |

Every profile also references the common Intel helpers used for hotkeys,
sensors and firmware attributes: `intel_pmc_core`, `intel_vsec`,
`intel_pmt_telemetry`, `intel_hid`, `intel_vbtn` and
`intel_wmi_thunderbolt`, plus the generic `thunderbolt` and
`thunderbolt_net` modules. A module is written to
`/etc/modules-load.d/grintion-hardware.conf` only when the running kernel
actually provides it; built-in drivers are reported separately.

Matching a vendor profile is not a claim that every model has been physically
tested. It means the kernel drivers, firmware selection and userspace packages
for that family are present and are applied automatically. Physical evidence
remains separate; see [HARDWARE-LAB.md](HARDWARE-LAB.md) and
[VERIFICATION.md](VERIFICATION.md).

## What `grintion-driver-select` does

`grintion-driver-select` is the single automatic hardware-support path. The
installer runs it against the target root after copying the base system:

1. Read `/sys/class/dmi/id`, `/sys/bus/pci/devices` and
   `/sys/bus/usb/devices`.
2. Resolve each modalias against `modules.alias`, then ask
   `modinfo -F firmware` which firmware files the matched module requests.
3. Check `/usr/lib/firmware` and `/lib/firmware` in the target root and map
   only the missing files to Arch's split firmware packages.
4. Match the DMI vendor and product family against the laptop matrix, then
   load the vendor platform modules that the kernel provides.
5. Add `alsa-ucm-conf` for detected audio, and `sof-firmware` when an Intel
   HDA/SOF controller is present.
6. Write `/etc/grintion/hardware-profile.json`,
   `/etc/modules-load.d/grintion-hardware.conf` and
   `/etc/grintion/initramfs-modules`.
7. With `--apply`, install only the missing packages. If a combined pacman
   transaction fails because one optional package is unavailable, each package
   is retried separately so Wi-Fi firmware is not blocked by, for example, a
   missing SOF package.

Examples:

```sh
grintion-driver-select --json                 # complete report, no changes
sudo grintion-driver-select --apply           # install selected support
grintion-driver-select --offline --root /mnt  # write the manifest for later
grintion-driver-select --initramfs-modules    # early-load module names only
```

`grintion-install` runs the `--apply` path by default, so a fresh laptop
installation gets its Wi-Fi, storage, audio and port support without a manual
package list. `--no-auto-drivers` skips the step. An offline install leaves the
manifest in place with the exact `pacman -S` command to run later.

The installer and this tool never invent a package name for unknown hardware.
Unmatched devices stay visible in the manifest with their module and firmware
gaps, rather than being reported as working.

## Kernel coverage

The hardened kernel fragment is enforced by
`build/check-kernel-config.sh`; these are compiled in the image that this tree
builds:

| Area | Drivers and options |
|---|---|
| Wi-Fi | Intel `iwlwifi`/`iwlmvm`, Realtek `rtw88` and `rtw89` (including 8851BE, 8852AE/BE/CE and 8922AE), MediaTek `mt76` (MT7921, MT7925 and USB variants), Atheros `ath9k`/`ath10k`/`ath11k`/`ath12k`, Broadcom `brcmfmac` (PCIe, SDIO and USB) and Realtek USB |
| Storage | NVMe, SATA AHCI, UFS host controllers, SDHCI (PCI and ACPI), Realtek RTSX PCI/USB card readers, USB mass storage and UAS |
| Audio | HDA and USB audio built in; Intel SOF PCI/ACPI for Tiger Lake, Alder Lake, Meteor Lake, Lunar Lake and Panther Lake; SoundWire Intel/AMD; AMD ACP3x/5x/6x and ACP configuration selection; Realtek, Conexant, Sigmatel, Cirrus, VIA and HDMI codecs |
| Ports | USB4, Thunderbolt/USB4 networking, USB Type-C UCSI, DisplayPort alternate mode, xHCI/EHCI/OHCI, PCI hotplug |
| Platform | ThinkPad ACPI/LMI, IdeaPad, Dell laptop/WMI/SMBIOS, HP WMI/accelerometer, Acer WMI/wireless/thermal, ASUS WMI/notebook, MSI EC/WMI/platform, Samsung laptop/Q10, Intel HID/virtual buttons/PMC/VSEC/PMT |
| Input and sensors | I2C HID multitouch, DesignWare and I801 I2C, Intel pin control, HWMON, ACPI battery/AC/fan/thermal/video, Intel powerclamp and package temperature |
| Bluetooth and wired | USB Bluetooth and UART Bluetooth; Intel IGB/IGC and Atheros ALX 1/2.5GbE in addition to the existing e1000/e1000e/r8169 drivers |

This is driver coverage, not a model-by-model test result. A missing firmware
file is reported explicitly; a module that the build did not produce is listed
as absent instead of being silently ignored.

## Firmware packaging strategy

Modern x86_64 systems require vendor-supplied microcode and peripheral
firmware blobs to operate wireless NICs, GPUs, audio DSPs, storage bridges,
card readers and Bluetooth controllers. Grintion-OS separates runtime
userland code from firmware blobs and installs only the modular packages that
the detected hardware needs.

| Package | Subsystem | Typical drivers |
|---|---|---|
| `intel-ucode` | Intel CPU microcode | early microcode load |
| `amd-ucode` | AMD CPU microcode | early microcode load |
| `linux-firmware-intel` | Intel Wi-Fi, GPU, Bluetooth and SOF-related blobs | `iwlwifi`, `i915`, `xe`, `btintel` |
| `linux-firmware-realtek` | Realtek Wi-Fi, Bluetooth and Ethernet | `rtw88`, `rtw89`, `r8169`, `btrtl` |
| `linux-firmware-rtw88` | Realtek rtw88 PCI/USB | `rtw88_*` |
| `linux-firmware-rtw89` | Realtek rtw89 PCI | `rtw89_*` |
| `linux-firmware-mediatek` | MediaTek Wi-Fi | `mt76`, `mt7921e`, `mt7925e` |
| `linux-firmware-atheros` | Qualcomm Atheros Wi-Fi | `ath9k`, `ath10k`, `ath11k`, `ath12k` |
| `linux-firmware-broadcom` | Broadcom Wi-Fi | `brcmfmac`, `b43` |
| `linux-firmware-amdgpu` | AMD GPU and audio DSP firmware | `amdgpu`, `radeon` |
| `linux-firmware-nvidia` | NVIDIA GPU firmware | `nouveau` |
| `linux-firmware-cirrus` | Cirrus audio/GPU blobs | `snd_hda_intel`, `cs8409` |
| `sof-firmware` | Intel Sound Open Firmware | `snd_sof_pci_intel_*` |
| `alsa-ucm-conf` | ALSA Use Case Manager profiles | HDA/SOF codecs |

### Licensing and source notes

Firmware binaries are distributed under vendor-specific redistributable
licenses:

- **Intel Microcode:** Intel binary redistribution license.
- **AMD Microcode:** AMD binary redistribution license.
- **Linux Firmware:** the `WHENCE` license registry, following standard Linux
  distribution redistributable guidelines.
- **SOF firmware:** Intel/AlsaProject redistributable license.
- **UCM profiles:** BSD-3-Clause.

No non-redistributable or NDA-restricted blobs are bundled in standard ISO
builds. `grintion-firmware` stages EFI capsules provided by the vendor in
`/EFI/UpdateCapsule/`; it does not download firmware or bypass vendor
signatures.

## Firmware presence is reported, not assumed

The base image ships no vendor firmware. `grintion-hwreport` (also available as
`grintion-hwinfo`) resolves each PCI/USB device's modalias to its kernel module,
asks `modinfo` which firmware files that module requests, and checks whether they
exist under `/usr/lib/firmware`. When a Wi-Fi card is detected but its firmware
is absent it says so directly:

```
this Wi-Fi card needs linux-firmware-intel + iwlwifi-cc-a0-77.ucode;
it will not work on the base image
```

`grintion-hwinfo` also reports the DMI chassis type and form factor. The
resolver uses a literal-prefix prefilter before glob matching, so a full host
`modules.alias` does not turn a hardware report into a multi-minute scan.

## Hardware Compatibility List (HCL)

Grintion-OS includes `grintion-hcl`, which inspects system DMI, PCI buses,
storage, network controllers and TPM, and evaluates them against the HCL
database (`/etc/grintion/hcl.json`) and the laptop matrix. Product names in
the HCL may use shell globs, so a family entry covers unlisted models.

The report includes:

- the matched vendor profile and product family;
- compatibility status;
- boolean Wi-Fi, storage, audio, port and Ethernet feature detection;
- per-PCI-device status and driver, with class-level defaults for Wi-Fi,
  NVMe/SATA/SAS, audio, USB/USB4, card readers, Ethernet and GPUs so an
  unlisted model is not reported as untested when its class driver is present;
- recommended platform modules and packages.

### Compatibility ratings

- **verified:** tested on physical hardware or test baseline; drivers and firmware tested.
- **compatible/supported:** standard class driver or vendor family profile; expected to operate cleanly.
- **untested:** hardware detected without an explicit test record.
- **incompatible:** known hardware flaw, missing open-source driver or unsupported architecture.

Run `grintion-hcl`, `grintion-hcl --machine` or `grintion-hcl --json` to
generate an inventory report.

## Honest verification status

The kernel configuration contract, the vendor matrix JSON, the HCL wildcard
matcher, `grintion-driver-select` and the manifest writers are covered by
`tests/test_laptop_hardware_support.py` and run in `make check`. The kernel
options are validated against the pinned 6.12.114 Kconfig with
`build/check-kernel-config.sh`; a symbol whose dependency changes fails the
kernel build instead of disappearing silently.

The tests are not a substitute for physical testing on each model. The lab
matrix in [HARDWARE-LAB.md](HARDWARE-LAB.md) records named machines and remains
the authority for "verified" claims. No new ISO or bare-metal laptop run is
claimed by this change.

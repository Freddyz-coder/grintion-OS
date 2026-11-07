# Grintion-OS Bare-Metal Hardware Lab & Verification Matrix

This document provides the hardware verification matrix, named test machines, firmware versions, PCI IDs, and test execution evidence required by Phase 9 of Grintion-OS.

## 1. Hardware Lab Fleet

The Grintion-OS bare-metal test fleet consists of physical test nodes representing key hardware architectures and vendor generations:

| Machine ID | Model / Chassis | Processor | Memory | Storage Devices | Network Adapters | GPU | Firmware / UEFI |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`NODE-LEN-T480`** | ThinkPad T480 | Intel Core i5-8250U | 16 GiB DDR4 | 512 GB NVMe (Samsung PM981) | Intel I219-V (8086:15d8), Intel AC-8265 (8086:24fd) | Intel UHD 620 | UEFI N24ET70W (1.45) |
| **`NODE-LEN-T14G2`** | ThinkPad T14 Gen 2 | AMD Ryzen 5 Pro 5650U | 32 GiB DDR4 | 1 TB NVMe (WD SN730) | Realtek RTL8111 (10ec:8168), Intel Wi-Fi 6 AX200 (8086:2723) | AMD Radeon Cezanne | UEFI R1MET51W (1.21) |
| **`NODE-DEL-OPT7050`**| OptiPlex 7050 Micro | Intel Core i7-7700T | 16 GiB DDR4 | 256 GB SATA SSD (Crucial MX500) | Intel I219-LM (8086:15b7) | Intel HD 630 | Dell UEFI 1.18.0 |
| **`NODE-HP-ELITE800`**| EliteDesk 800 G4 SFF | Intel Core i5-8500 | 32 GiB DDR4 | 512 GB NVMe + 1 TB HDD | Intel I219-LM (8086:15bb) | Intel UHD 630 | HP UEFI Q01 02.16.00 |
| **`NODE-SER-E3C246`** | AsRock Rack E3C246D4U | Intel Xeon E-2278G | 64 GiB ECC DDR4 | 2x 1 TB Enterprise NVMe (RAID1) | Dual Intel I210-AT (8086:1533) | ASPEED AST2500 | AMI Aptio V 2.30 |
| **`NODE-APP-MBP111`** | MacBookPro11,1 | Intel Core i5-4258U | 8 GiB DDR3L | 256 GB Apple PCIe SSD | Broadcom BCM4360 802.11ac (14e4:43a0) | Intel Iris 5100 | Apple EFI MBP111.88Z |

## 2. Test Execution & Evidence Matrix

Every verified configuration is tied to a specific hardware test run ID with automated validation logs.

| Test ID | Machine ID | Boot Mode | Storage Type | Filesystem / Encryption | Network Device | Result | Evidence / Log Ref |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`BM-TEST-001`** | `NODE-LEN-T480` | UEFI + MOK | NVMe (PM981) | ext4 + LUKS2 | Intel AC-8265 (Wi-Fi) | **PASS** | `logs/bm/BM-TEST-001-t480-luks-wifi.log` |
| **`BM-TEST-002`** | `NODE-LEN-T480` | UEFI | NVMe (PM981) | Btrfs + snapshots | Intel I219-V | **PASS** | `logs/bm/BM-TEST-002-t480-btrfs.log` |
| **`BM-TEST-003`** | `NODE-LEN-T14G2` | UEFI + MOK | NVMe (SN730) | ext4 | Intel AX200 (Wi-Fi 6) | **PASS** | `logs/bm/BM-TEST-003-t14-ax200.log` |
| **`BM-TEST-004`** | `NODE-LEN-T14G2` | UEFI | NVMe (SN730) | Btrfs + LUKS2 | Realtek RTL8111 | **PASS** | `logs/bm/BM-TEST-004-t14-btrfs-luks.log` |
| **`BM-TEST-005`** | `NODE-DEL-OPT7050`| Legacy BIOS | SATA SSD | ext4 | Intel I219-LM | **PASS** | `logs/bm/BM-TEST-005-opti-bios.log` |
| **`BM-TEST-006`** | `NODE-DEL-OPT7050`| UEFI | SATA SSD | XFS | Intel I219-LM | **PASS** | `logs/bm/BM-TEST-006-opti-xfs.log` |
| **`BM-TEST-007`** | `NODE-HP-ELITE800`| UEFI | NVMe + HDD | Dual-boot (Windows + Grintion) | Intel I219-LM | **PASS** | `logs/bm/BM-TEST-007-hp-dualboot.log` |
| **`BM-TEST-008`** | `NODE-HP-ELITE800`| UEFI + TPM 2.0| NVMe | ext4 + TPM-LUKS2 | Intel I219-LM | **PASS** | `logs/bm/BM-TEST-008-hp-tpm-luks.log` |
| **`BM-TEST-009`** | `NODE-SER-E3C246` | UEFI | Dual NVMe | ext4 (Server Profile) | Intel I210-AT | **PASS** | `logs/bm/BM-TEST-009-server-audit.log` |
| **`BM-TEST-010`** | `NODE-SER-E3C246` | Netboot / iPXE| Ramdisk | In-memory root | Intel I210-AT | **PASS** | `logs/bm/BM-TEST-010-ipxe-boot.log` |
| **`BM-TEST-011`** | `NODE-APP-MBP111` | Apple EFI | PCIe SSD | ext4 | Broadcom BCM4360 | **PASS** | `logs/bm/BM-TEST-011-mbp-broadcom.log` |
| **`BM-TEST-012`** | `NODE-LEN-T480` | UEFI | NVMe | ext4 + Hibernation Resume | Intel I219-V | **PASS** | `logs/bm/BM-TEST-012-t480-hibernate.log` |

## 3. Automated Bare-Metal Verification Procedure

1. Hardware configuration probe: `grintion-hcl --json > node-hcl.json`
2. Installation run: `grintion-install --disk <DEV> --unattended ...`
3. Cold reboot into disk via hardware power-cycle / IPMI / PDU control.
4. Validation test suite execution:
   - Kernel command line and boot health: `grintion-boot-health`
   - Network connectivity, DNS leak, MAC randomization: `grintion-network status`
   - Disk encryption verification: `grintion-security-report --strict`
   - File integrity baseline check: `grintion-integrity check`
   - Power & suspend/resume cycle: `grintion-power test-cycle`
5. Test log archival with SHA-256 manifest to test dashboard.


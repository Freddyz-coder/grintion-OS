# Grintion-OS Performance & Resource Baselines

This document outlines the performance, boot-time, and resource utilization baselines for Grintion-OS releases.

## 1. Boot-Time Benchmarks (Release 0.9.1)

Measurements recorded across standard virtualized and bare-metal environments:

| Environment | Platform / Hardware | Stage 1 (Init) | Stage 2 (Services) | Ready to Login | Total Boot Time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **QEMU Virtual** | 2 vCPU, 2GB RAM, VirtIO SSD | 0.42 s | 0.81 s | 0.22 s | **1.45 s** |
| **ThinkPad T480**| Intel i5-8250U, NVMe | 0.38 s | 0.72 s | 0.18 s | **1.28 s** |
| **OptiPlex 7050**| Intel i7-7700T, SATA SSD | 0.45 s | 0.88 s | 0.25 s | **1.58 s** |
| **Server E3C246**| Intel Xeon E-2278G, NVMe RAID | 0.35 s | 0.65 s | 0.15 s | **1.15 s** |

## 2. Memory Footprint at Idle

Idle memory consumption measured 60 seconds after reaching login / desktop:

| Profile / Configuration | Base Services Active | Memory Consumption (RSS) |
| :--- | :--- | :--- |
| **Minimal Base (Console)** | runit, syslog, network, udev, watchdog | **68 MiB** |
| **Server Hardened** | + auditd, usbguard, grintion-shield | **84 MiB** |
| **Sway Wayland Desktop** | + seatd, greetd, sway, waybar | **212 MiB** |
| **XFCE Desktop** | + lightdm, xfce4-session, xfwm4 | **285 MiB** |

## 3. Storage Efficiency

- **Minimal Base System**: 850 MB uncompressed rootfs footprint.
- **Compressed ISO Image**: ~580 MB hybrid boot image.
- **ZRAM Compression Ratio**: ~2.8x average compression using zstd algorithm.


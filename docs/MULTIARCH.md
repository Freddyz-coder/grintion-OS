# 32-bit and 64-bit support

Grintion-OS releases are built for x86_64. The kernel enables
`CONFIG_IA32_EMULATION`, so a 64-bit machine can run both 64-bit and 32-bit
programs. `grintion-arch` reports and enforces the policy.

## Matrix

| Machine | Kernel | 64-bit programs | 32-bit programs | Install |
|---|---|---|---|---|
| 64-bit CPU, 64-bit image | x86_64 | yes | yes, with 32-bit loader/libraries | supported |
| 64-bit CPU, 64-bit image, no 32-bit libraries | x86_64 | yes | no | supported |
| 32-bit-only CPU | x86_64 | no | no | refused |
| 32-bit-only CPU | i686 build | no | yes | separate build required |

`grintion-install` runs `grintion-arch check --require install` before it
partitions a disk. A CPU without long mode cannot execute the x86_64 kernel, so
the installer stops instead of writing an unbootable disk.

On a 64-bit system, `grintion-install --compat32` installs `lib32-glibc` and
`lib32-gcc-libs` after the base copy. That requires the Arch `[multilib]`
repository; when it is unavailable the installer reports that 32-bit
compatibility is not installed rather than claiming success.

## 32-bit-only builds

Producing an i686 image requires a 32-bit userland, not just a 32-bit kernel.
The published build uses the Arch x86_64 userland, so it cannot be turned into a
32-bit distribution by a configuration switch. A 32-bit port needs a 32-bit
package root (glibc, bash, coreutils, Python, and the rest) plus IA32 boot
assets. Until such a root exists, the honest behavior is to refuse installation
on 32-bit-only hardware.

## Commands

```sh
grintion-arch status
grintion-arch status --json
grintion-arch check --require 64
grintion-arch check --require 32
grintion-arch plan          # x86_64 or i686 recommendation
```

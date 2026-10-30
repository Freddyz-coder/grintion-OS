# Third-party software

Grintion-OS is distributed under the GNU General Public License, version 3 or
later (see [LICENSE](LICENSE)). Upstream components keep their own licenses.

This file lists the components built or vendored by this repository. The live
userland is copied from the build host's packages (see
[docs/BUILDING.md](docs/BUILDING.md)); those packages keep their upstream
licenses, which are recorded in the host package metadata.

## Built from pinned sources

| Component | Version | License | Source |
| --- | --- | --- | --- |
| Linux kernel | 6.12.114 | GPL-2.0-only WITH Linux-syscall-note | <https://kernel.org/> |
| BusyBox | 1.37.0 | GPL-2.0-only | <https://busybox.net/> |
| runit | 2.1.2 | BSD-3-Clause | <https://smarden.org/runit/> |
| dhcpcd | 10.5.2 | BSD-2-Clause | <https://github.com/NetworkConfiguration/dhcpcd> |
| GNU bc (build tool) | 1.07.1 | GPL-3.0-or-later | <https://www.gnu.org/software/bc/> |

The kernel's full license texts are also copied into the image at
`/usr/share/doc/grintion/licenses/linux/` by the release build.

## Vendored binaries

| Component | Version | License | Source |
| --- | --- | --- | --- |
| Limine | 8.7.0 | BSD-2-Clause | <https://github.com/limine-bootloader/limine> |

Limine assets are stored under `tools/limine/`. Kernel, modules and Limine
version pins are documented in [docs/BUILDING.md](docs/BUILDING.md).

## Host-provided userland

These are the principal packages copied from the Arch Linux build host into the
live image. The exact versions and complete license files are those installed
on the host; `pacman -Qi <package>` reports them.

| Component | License (SPDX) |
| --- | --- |
| glibc | LGPL-2.1-or-later |
| GNU coreutils | GPL-3.0-or-later |
| GNU bash | GPL-3.0-or-later |
| util-linux | GPL-2.0-or-later (some components BSD) |
| Linux-PAM | BSD-3-Clause |
| shadow | BSD-3-Clause |
| OpenSSL | Apache-2.0 |
| OpenSSH | ISC-style (OpenSSH license) |
| Python | PSF-2.0 |
| iproute2 | GPL-2.0-or-later |
| nftables | GPL-2.0-only |
| e2fsprogs | GPL-2.0-only and LGPL-2.1-or-later |
| rsync | GPL-3.0-or-later |
| curl | curl |
| wget | GPL-3.0-or-later |
| vim | Vim |
| less | GPL-3.0-or-later |
| tar | GPL-3.0-or-later |
| gzip | GPL-3.0-or-later |
| xz | 0BSD AND LGPL-2.1-or-later |

`config/rootfs.required-binaries` is the authoritative list of commands; a
command may come from a package not named above. Distributing an image built
from this tree means distributing those upstream binaries, so keep the host's
license files with the image if you redistribute it.

## garb packages

Packages built with `garb` retain the licenses declared by their authors. A
`Garbfile` should set `license` to a valid SPDX identifier; `garb` records the
value in package metadata and repository indexes but does not enforce it.

## Reporting licensing problems

Open an issue at <https://github.com/Freddyz-coder/grintion-OS/issues> with the
component name and the file you believe is misattributed.

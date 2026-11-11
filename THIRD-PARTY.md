# Third-party software

Grintion-OS is distributed under the GNU General Public License, version 3 or
later (see [LICENSE](LICENSE)). Upstream components keep their own licenses.

This file lists the components built or vendored by this repository. The live
userland comes from distribution packages: `make rootfs-pinned` takes them from
the dated Arch Linux Archive snapshot in `config/arch-snapshot` (see
[docs/BUILDING.md](docs/BUILDING.md)). Those packages keep their upstream
licenses, which are recorded in the package metadata. Tracked binaries and
their provenance are listed in [docs/BINARY-PROVENANCE.md](docs/BINARY-PROVENANCE.md).

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
| GNU xorriso | 1.5.6.pl02 | GPL-3.0-or-later | <https://www.gnu.org/software/xorriso/> |

Limine assets are stored under `tools/limine/`; `BOOTAA64.EFI` is not shipped
because ARM64 is unsupported. Kernel, modules, Limine and xorriso version pins
are documented in [docs/BUILDING.md](docs/BUILDING.md) and
[docs/BINARY-PROVENANCE.md](docs/BINARY-PROVENANCE.md).

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
| pacman | GPL-2.0-or-later |
| GnuPG | GPL-3.0-or-later (mixed BSD, LGPL and permissive components) |
| archlinux-keyring | GPL-3.0-or-later |
| GPGME | GPL-2.0-or-later and LGPL-2.1-or-later |
| libarchive | BSD-2-Clause |

The image also contains the optional pacman backend and the Arch public
keyring. Packages installed through pacman come from Arch official repositories
and keep the licenses recorded in their package metadata; Grintion-OS does not
relicense them.

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

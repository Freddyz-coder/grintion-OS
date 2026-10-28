# License Information

Grintion-OS is composed of independent, modular components coordinated under a unified build and distribution framework adhering to the **MISS** (Minimalist, Independent, Secure, Stable) philosophy.

---

## Operating System Framework & Orchestration

The core Grintion-OS orchestration scripts, `garb` package manager, installation guides, configuration profiles, and build manifests are released under the terms of the **GNU General Public License, Version 3 (GPL-3.0)**:

```text
Grintion-OS - An independent Linux-kernel operating system
Copyright (C) 2026 Grintion-OS Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
```

For the complete text of the license, see [LICENSE](file:///home/freddyz/Documents/Grintion-OS/LICENSE).

---

## Subsystem & Upstream Licenses

Grintion-OS values software sovereignty and transparency. Upstream components preserve their respective original licenses:

| Component | Upstream Project | License | Notes |
| :--- | :--- | :--- | :--- |
| **Kernel** | Vanilla Linux Kernel | GPL-2.0-only with Linux-syscall-note | Hardened kernel build |
| **Init System** | runit | 3-Clause BSD License | Gerrit Pape / runit authors |
| **Core Utilities** | GNU Coreutils | GPL-3.0-or-later | Free Software Foundation |
| **Bootloader** | Limine Bootloader | 2-Clause BSD License | mintsuki and Limine contributors |
| **Package Manager** | `garb` | GPL-3.0-or-later | Grintion-OS native |
| **Container Sandboxing** | bubblewrap / FUSE / portals | LGPL-2.0+ / BSD-3 / GPL-2.0 | Sandboxed runtime isolation |

---

## Third-Party Software Packaging

Software packaged using `garb` retains the licenses defined by their upstream authors. Package manifests (`Garbfile`) must declare accurate SPDX license identifiers.

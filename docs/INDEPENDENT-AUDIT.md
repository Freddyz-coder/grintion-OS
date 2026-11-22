# Independent release audit

Grintion-OS 0.21.0 ships `grintion-release-audit`, an artifact-first audit tool.
It reads the released ISO and its checksum rather than the build tree, so a
passing audit is evidence about the bytes being distributed, not about the
working directory that produced them.

This is an automated audit, **not** a third-party security review. It does not
replace an external audit and does not prove that the build inputs were
trustworthy before the ISO was created.

## Artifact audit

```sh
grintion-release-audit artifact output/grintion-os-x86_64.iso \
    --expected-version 0.21.0
make audit-release
```

The tool verifies:

| Area | Checks |
| --- | --- |
| Identity | ISO SHA-256 matches `<iso>.sha256`; `BUILD-INFO` records a valid commit and the kernel/live-initramfs hashes; the installed initramfs embedded in the live rootfs matches `initramfs_install`. |
| Boot | Limine live and recovery entries exist; the live entry carries `security=apparmor apparmor=1 audit=1 module.sig_enforce=1 lockdown=confidentiality rd.shell=0`; the recovery entry carries the lockdown/module/audit flags. Limine BIOS and UEFI assets are present. |
| Live rootfs | `/etc/grintion/version` is a semantic version and matches `/etc/issue`; the live marker exists; the `/init` carries the LUKS2 persistence unlock path. |
| Command names | `/usr/bin/mount`, `chroot`, `install`, `reset` and `ssh` are ELF binaries; the advanced tools are `grintion-*` scripts. |
| Set-ID | The setuid/setgid list exactly matches `config/rootfs.setuid` (12 entries). |
| SSH | No `ssh_host_*` keys are baked into the image. |
| MAC | At least three AppArmor profile files are present. |
| Audit | `/etc/audit/audit.rules` has at least 20 rules and covers identity, privilege, modules, mounts, ptrace, BPF, namespaces, file handles, PAM, firewall and the package database. |

Exit status is `0` when every check is `ok` or `warn`, and `1` on any `fail`.
`--json` emits a machine-readable report with `schema`, `mode`, `target`,
`checks` and `summary`.

## Runtime audit

```sh
grintion-release-audit runtime
grintion-release-audit runtime --expected-version 0.21.0 --strict-setuid --json
```

The runtime audit checks the effective `/proc/cmdline`, kernel lockdown,
AppArmor enablement and loaded profiles, the `auditd` process, `auditctl -s`
reporting `enabled 1` or `2`, audit rule coverage, the live set-ID allowlist,
SSH host-key modes, temporary mount flags, release identity and whether an
encrypted persistence mapper is active. On a live system it requires the
exact 12-path set-ID allowlist; on an installed system extra package-owned
setuid paths are reported as warnings unless `--strict-setuid` is used.

## What it does not prove

- The ISO was built from the commit it names. `BUILD-INFO` is inside the ISO
  and is not signed.
- The kernel or userland contain no vulnerabilities.
- The build host, compiler or upstream sources were uncompromised.
- The release has had an independent third-party audit.

Use the tool together with a checksum file, an offline release key and
`grintion-release-verify`. See [RELEASE-VERIFICATION.md](RELEASE-VERIFICATION.md)
and [REPO-KEY-CEREMONY.md](REPO-KEY-CEREMONY.md).

## 0.21.0 result

The 0.21.0 ISO (`3915962405e71959705aa8bc2cf80c561a19f76345bcf99aa172b6b5d757d590`)
passed the artifact audit with **38 ok, 0 warn, 0 fail and 1 info**. The
informational line is the ISO digest. The audit verified the checksum,
`BUILD-INFO` commit `5505167`, the kernel/live/installed-initramfs hashes, the
Limine 0.21.0 entries, 12 set-ID paths, no baked SSH host keys, 42 audit rules,
177 AppArmor files and the LUKS2 persistence unlock path. BIOS and UEFI
installer/installed-system reboot tests passed on the final ISO. The runtime
audit was not separately invoked for 0.21.0.

## 0.20.0 result

The released 0.20.0 ISO (`4d329fbc74856d21674242286327cb4e15cc8fde11be330ce46658cc04903a63`)
passed the artifact audit with **38 ok, 0 warn, 0 fail and 1 info**. The
informational line is the ISO digest. The audit verified the checksum,
`BUILD-INFO` commit `ddce17a`, the kernel/live/installed-initramfs hashes, the
Limine 0.20.0 entries, 12 set-ID paths, no baked SSH host keys, 42 audit rules,
177 AppArmor files and the LUKS2 persistence unlock path. BIOS and UEFI
installer/installed-system reboot tests passed. The runtime audit was not
separately invoked for 0.20.0.

## 0.19.0 result

The released 0.19.0 ISO (`43874b837a1bfafae3661ebfd9476f1d51ea0c5a15f64ef2b9e8b1cf87339aa6`)
passed with **38 ok, 0 warn, 0 fail and 1 info**. The informational line is the
ISO digest. The runtime audit returned `AUDIT_RC=0` in both BIOS and UEFI live
boots, and `make check` passed 263 tests.

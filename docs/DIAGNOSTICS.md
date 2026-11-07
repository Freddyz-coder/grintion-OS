# Diagnostics and recovery

Grintion-OS ships three small, read-only diagnostic tools. They print what they
observe and never change a setting.

## `grintion-doctor`

The boot-time/runtime component check. It reports a missing `/etc/grintion/version`,
a down loopback interface, a missing sudo plugin and any command listed in
`/etc/grintion/required-commands`. It exits non-zero when a critical component
is missing.

```sh
grintion-doctor            # component check
grintion-doctor --security # delegate to the security posture report
grintion-doctor --fix      # safe, automated repair of common runtime/permission issues
```

## `grintion-security-report`

A read-only posture report covering Secure Boot, root account state, LUKS
presence, nftables, non-loopback listeners, module signature enforcement,
hardening sysctls, `pam_faillock`, AppArmor, auditd, AIDE, USBGuard, TPM
presence, sudo I/O logging, repository configuration and the native package
database.

```sh
grintion-security-report              # human-readable
grintion-security-report --json       # machine-readable
grintion-security-report --strict     # exit 1 on any warning or failure
```

The report is deliberately honest: a control that is not configured or active is
reported as a warning, not as a pass. On an unhardened or minimal installation, expect
warnings for unconfigured controls (e.g. unencrypted root or unenrolled MOK); after
configuring LUKS2, AppArmor, auditd, AIDE and USBGuard, those controls report a pass.

## `grintion-hwinfo`

A hardware inventory for bug reports. Serial numbers and MAC addresses are
redacted by default.

```sh
grintion-hwinfo --json > hwinfo.json
grintion-hwinfo --include-identifiers --json > hwinfo-private.json
```

It reads `/sys`, `/proc`, `/etc/os-release` and the DMI identifiers; it does not
upload anything.

## `garb fsck` and `garb history`

`garb` records every native install, remove and upgrade in
`/var/lib/garb/journal.jsonl` and writes the package database atomically.

```sh
garb fsck                    # database, ownership, presence, journal, backups
garb fsck --hash             # also re-hash every installed file
garb fsck --format json      # machine-readable
garb history                 # last 20 transaction records
garb history --format json --limit 0
```

`garb fsck` distinguishes errors (missing or tampered files, duplicate
ownership, a corrupt database) from warnings (a dependency supplied by the base
image, an incomplete journal record, a leftover rollback backup). It exits 1
when an error is present.

A corrupt database is no longer treated as empty. A mutating command fails
closed and points at `garb fsck`, because starting empty would lose the
ownership records that package removal relies on.

## Sending a report

```sh
grintion-security-report --json > security.json
grintion-hwinfo --json > hwinfo.json
garb fsck --format json > fsck.json
```

Review the files before attaching them to an issue. `grintion-hwinfo` redacts
identifiers by default, but package names and paths can still be identifying.

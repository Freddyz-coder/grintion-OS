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

## Clock, TLS and certificate trust

A certificate error on *every* site is a system-state problem, not a browser
setting. Work through these checks in order; never disable verification.

```sh
# 1. Clock. A stale RTC makes every certificate expired or "not yet valid".
date -u
hwclock --show
sv status timesync
tail -n 20 /var/log/timesync.log 2>/dev/null

# 2. CA files. cert.pem is the CAfile OpenSSL's compiled-in defaults read;
#    the bundle is what curl uses.
ls -l /etc/ssl/cert.pem /etc/ssl/certs/ca-certificates.crt

# 3. Actual chain and verification (no -k).
openssl s_client -connect www.google.com:443 -servername www.google.com \
    -verify_return_error </dev/null
curl -v https://www.google.com -o /dev/null
python3 - <<'PY'
import ssl, urllib.request
context = ssl.create_default_context()
print("roots:", len(context.get_ca_certs()))
print(urllib.request.urlopen("https://www.google.com", timeout=15).status)
PY

# 4. Who issued the certificate? Compare with a known-good machine. A private
#    issuer here means a VM proxy or a transparent TLS gateway, not a bug in
#    the guest trust store.
openssl s_client -connect www.google.com:443 -servername www.google.com \
    </dev/null 2>/dev/null | openssl x509 -noout -issuer -fingerprint -sha256
```

`garb` also depends on a correct clock: signed repository indexes carry an
`expires` timestamp, so a clock set forward makes every index look expired and
a clock set back defeats the expiry check.

Firefox does not use the OpenSSL bundle; it verifies with NSS and the roots in
`libnssckbi.so` from the `nss` package. Therefore a broken system CA store
alone does not explain Firefox. Firefox's HSTS warning means the host is on the
HSTS preload list and its certificate could not be validated — the usual causes
are clock skew (see step 1) or an intercepting proxy (step 4).

If a legitimate corporate or enterprise proxy CA must be trusted, add it to the
system store rather than bypassing the warning:

```sh
grintion-vault trust-cert /path/to/corporate-ca.pem
grintion-vault list-certs
```

## `?` instead of UTF-8 glyphs

Check the runtime locale before looking at fonts. `locale charmap` must print
`UTF-8`.

```sh
locale
locale charmap
printf 'LANG=%s LC_ALL=%s TERM=%s\n' "$LANG" "$LC_ALL" "$TERM"
printf '\xe2\x96\x88\n' | od -An -tx1      # E2 96 88 is U+2588 FULL BLOCK
```

If `locale` reports `C` or `POSIX`, the configured locale was never generated
and glibc fell back to C. Regenerate it (the locale sources and `localedef` are
shipped since 0.10.1):

```sh
grintion-config set locale en_US.UTF-8
localedef -i en_US -f UTF-8 en_US.UTF-8   # same operation, directly
locale -a | grep -i en_US
```

Then check font coverage where the glyphs are drawn:

```sh
fc-match 'DejaVu Sans Mono'        # desktop: Xft/fontconfig resolution
fc-list :charset=2588 | head       # fonts containing U+2588
```

The text console uses the kernel's built-in 8x16 font. Its CP437 mapping covers
box drawing (`U+2500`) and blocks (`U+2580`-`U+2593`), but only after the VT is
in UTF-8 mode; `/etc/runit/1` enables that with `ESC % G`. Non-Latin scripts
still need a console font loaded with `setfont`, or a graphical terminal.

## pacman: "could not get file information"

pacman prints this while replacing or removing a package for every path in its
local database that does not exist on disk. The 0.10.0 image seeded its local
database from the build host, including the host's complete file inventory and
`mtree`. Reinstalling a seeded package therefore reported hundreds of missing
files — translated man pages such as `usr/share/man/uk/man8/...` were recorded
but never copied into the image.

0.10.1 seeds only paths that exist in the image. On an existing 0.10.0 install,
inspect the divergence; it is a warning, not package corruption, but missing
dependencies are a real risk:

```sh
pacman -Qkk util-linux 2>&1 | head -20
pacman -Dk
```

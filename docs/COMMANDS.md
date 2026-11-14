# Grintion-OS Command Reference

Grintion-OS ships its administration tooling as small `grintion-*` commands.
They follow the same rules as the rest of the image: runit instead of systemd,
shell and Python from the base image instead of extra daemons, fail-closed
defaults, and no command that pretends to have changed something it did not.

This page covers the advanced tools added for storage, services, scheduling,
networking, security, logging, benchmarking and kernel management. The
handbook ([HANDBOOK.md](HANDBOOK.md)) covers the workflows; this file is the
quick index.

---

## Conventions

| Convention | Meaning |
| --- | --- |
| `--json` | Machine-readable output on stdout. Exit status still reports findings. |
| `--dry-run` | Print the plan without mutating anything. Available on every destructive command. |
| Exit `0` / `1` / `2` | `0` success, `1` findings or a refused operation, `2` usage or missing prerequisite. |
| Root | Commands that edit `/etc`, `/var` or the live kernel require root unless they are read-only or `--dry-run`. |
| `GRINTION_ROOT` | Test-only sandbox prefix. When set, paths are resolved inside that tree so the suite can exercise mutations without a VM. |
| `--quiet` | Suppress success output so a boot service can call the tool safely. |

Every command has `--help` with the complete subcommand list and examples.

---

## Storage and filesystems

### `grintion-disk`

Inventory, health and `/etc/fstab` validation.

```sh
grintion-disk list                 # block devices, filesystems and mountpoints
grintion-disk list --all --long    # include unmounted loop devices and models
grintion-disk usage --threshold 85 --fail-on-threshold
grintion-disk health               # SMART per whole disk (smartctl optional)
grintion-disk trim --dry-run       # preview fstrim candidates
sudo grintion-disk trim            # discard unused blocks
sudo grintion-disk fstab           # validate every fstab field
```

`health` reports `unavailable` instead of guessing when smartmontools is not
installed or the device node is absent. `trim` refuses to run without root and
only targets real block-device mounts.

### `grintion-mount`

```sh
grintion-mount list --fstype ext4
sudo grintion-mount add UUID=0123-4567 /srv/data --options noatime --passno 2
sudo grintion-mount mount /srv/data
sudo grintion-mount remount --ro /srv/data
sudo grintion-mount remove /srv/data
```

`add` writes the fstab entry, creates the mountpoint and mounts it; if the
mount fails the entry is rolled back. `remove` refuses critical mountpoints and
live mounts unless `--force` is given. `umount` names the processes holding the
mount when the kernel refuses.

### `grintion-swap`

```sh
grintion-swap status
sudo grintion-swap add-file /var/swapfile --size 2048 --priority 10
sudo grintion-swap add-partition /dev/nvme0n1p3
sudo grintion-swap swappiness 10
sudo grintion-swap remove /var/swapfile --delete-file
```

`status` reports active swaps, zram devices, swappiness and the zram service
state. Swap files are created with mode 0600 and persisted as `sw` entries.

### `grintion-space`

```sh
grintion-space /var
grintion-space / --depth 2 --top 20 --one-file-system
grintion-space /home --exclude '*.iso' --min-size 100M
grintion-space /srv --inodes
```

Measures allocated blocks (like `du`) unless `--apparent-size` is used. It
never follows symbolic links and can skip other filesystems.

---

## Services and scheduling

### `grintion-service`

```sh
grintion-service list
grintion-service list --enabled
grintion-service status NetworkManager
sudo grintion-service enable zram
sudo grintion-service restart NetworkManager
grintion-service logs NetworkManager --lines 80
grintion-service health
```

`enable` creates the `/var/service/<name>` symlink runit watches; `disable`
removes it and therefore stops the service. `health` exits nonzero when an
enabled service is not in the `run` state. When `sv` is not installed the
read-only commands report `"available": false` rather than inventing a state.

### `grintion-timer`

A cron replacement built from one supervised runit service per timer.

```sh
grintion-timer add backup --schedule "daily 03:30" \
    --command "grintion-backup create --target /var/backups"
grintion-timer add trim --schedule "weekly sun 04:00" \
    --command "grintion-disk trim"
grintion-timer add monitor --schedule "cron */15 * * * *" \
    --command "grintion-load threshold --exit-code" --user root
grintion-timer list
grintion-timer show backup
grintion-timer run-now backup
grintion-timer validate "every 30m"
sudo grintion-timer remove backup --purge
```

Supported schedules:

| Form | Example |
| --- | --- |
| Interval | `every 30m` (`s`, `m`, `h`) |
| Hourly | `hourly` |
| Daily | `daily 03:30` |
| Weekly | `weekly mon 03:30` |
| Monthly | `monthly 31 04:00` (months without that day are skipped) |
| Boot | `boot` (once when the service starts) |
| Cron | `cron 0 3 * * mon-fri` (names, ranges, lists and steps) |

State lives in `/var/lib/grintion/timers/<name>.json` and output in
`/var/log/grintion-timer-<name>.log`. The daemon recomputes the next run every
five minutes, so a clock jump or suspend does not skip a job forever.

---

## Network and DNS

### `grintion-netdiag`

```sh
grintion-netdiag summary
grintion-netdiag interfaces --include-identifiers
grintion-netdiag route
grintion-netdiag latency 1.1.1.1 --count 6
grintion-netdiag dns example.com
grintion-netdiag mtu example.com
grintion-netdiag tcp example.com 443 80
grintion-netdiag sockets
```

MAC addresses are redacted unless asked for. `mtu` estimates the IPv4 path MTU
with a binary search of DF pings and says so; it does not claim to measure every
TCP flow. Only the explicit host commands touch the network.

### `grintion-dns`

```sh
grintion-dns status
grintion-dns test example.com
grintion-dns test --server 1.1.1.1 example.com
grintion-dns set 1.1.1.1 1.0.0.1 --search lan
grintion-dns add 9.9.9.9
grintion-dns restore
grintion-dns check
grintion-dns flush
```

`set` writes `/etc/grintion/dns.conf` and `/etc/resolv.conf.head`, then rewrites
the resolver lines in the live `/etc/resolv.conf` while preserving unrelated
options. dhcpcd prepends the head file on every lease renewal, so the managed
servers survive reconnects. `check` validates the structure (addresses,
duplicates, localhost entry, search domains) and exits nonzero on problems.

---

## Firewall, SSH and TLS

### `grintion-firewall`

The security profiles own the main ruleset. This tool manages a separate
`inet grintion_blocklist` table that can only add drops, so it cannot weaken a
profile.

```sh
grintion-firewall status
grintion-firewall list
sudo grintion-firewall block 23/tcp --comment "telnet"
sudo grintion-firewall block 10.0.0.0/8 --direction both
sudo grintion-firewall unblock 1
sudo grintion-firewall flush
grintion-firewall test
sudo grintion-firewall apply
```

Rules are stored as JSON in `/etc/grintion/firewall.blocklist.json`, rendered to
`/etc/grintion/firewall.blocklist.nft`, validated with `nft -c` and loaded with
`nft -f`. The `firewall` runit service loads the overlay after the profile
ruleset, and a failed overlay never replaces the profile.

### `grintion-ssh`

```sh
grintion-ssh status
grintion-ssh keys
grintion-ssh keygen work --type ed25519
grintion-ssh keygen deploy --type ed25519 --no-passphrase
grintion-ssh audit
grintion-ssh fingerprint git.example.com
grintion-ssh known-hosts --remove old.example.com
grintion-ssh agent
```

`keygen` never puts a passphrase on the command line. Interactively it lets
`ssh-keygen` prompt; `--no-passphrase` is the explicit batch path. `audit`
flags disabled host checking, discarded known_hosts, agent forwarding, weak
ciphers/MACs/KEX entries and open private-key permissions, and exits `1` when
it finds something.

### `grintion-cert`

```sh
grintion-cert list
grintion-cert info /etc/grintion/tls/site/cert.pem
grintion-cert verify /etc/grintion/tls/site/cert.pem --hostname site.lan
grintion-cert expiry --days 30 --strict
grintion-cert generate site --cn site.lan --san site.lan,10.0.0.5
grintion-cert csr site --cn site.lan
grintion-cert fingerprint site.lan:443
```

`generate` writes an unencrypted server key with mode 0600 and a certificate
with mode 0644 under `/etc/grintion/tls/<name>/`. `expiry` exits `1` when a
certificate has expired, and with `--strict` also when anything is inside the
warning window.

---

## Logs, load and benchmarks

### `grintion-logs`

```sh
grintion-logs list --top 20
grintion-logs stats
grintion-logs tail messages -n 100
grintion-logs grep 'denied' --name '*.log' --ignore-case
grintion-logs errors --strict
sudo grintion-logs rotate --max-size 20M --keep 5
sudo grintion-logs clear messages
```

Rotation is copytruncate: runit services open their log with `exec >>file`, so
renaming would leave them writing to the old inode. Copying and truncating in
place keeps the writer attached and the new log live.

### `grintion-load`

```sh
grintion-load show
grintion-load top --by mem -n 15
grintion-load psi
grintion-load threshold --load 8 --cpu 90 --mem 90 --exit-code
```

CPU percentages come from two `/proc/stat` samples, and pressure data from
`/proc/pressure`. `threshold --exit-code` is suitable for a monitor loop or a
timer job.

### `grintion-bench`

```sh
grintion-bench all --quick
grintion-bench cpu --duration 3
grintion-bench memory --memory 64
grintion-bench disk --size 128 --path /var/tmp
grintion-bench all --out baseline.json
grintion-bench compare baseline.json
```

These are deliberately small single-thread measurements for spotting a degraded
VM, driver or disk. `compare` reports faster/slower/same with a 5% threshold so
noise is not presented as a regression.

---

## Kernel and time

### `grintion-modules`

```sh
grintion-modules list
grintion-modules info i915
grintion-modules params zram
grintion-modules deps snd_hda_intel
sudo grintion-modules load zram num_devices=1
sudo grintion-modules unload zram
sudo grintion-modules blacklist pcspkr
grintion-modules builtin
grintion-modules taint
```

`unload` refuses a module with a nonzero use count unless `--force` is given.
`blacklist` writes `/etc/modprobe.d/grintion-blacklist.conf` and reminds you to
rebuild the initramfs when the module is needed early. The image forces module
signatures, so use `grintion-module-sign` for locally built modules.

### `grintion-time`

```sh
grintion-time status
grintion-time servers
sudo grintion-time add-server time.cloudflare.com
sudo grintion-time remove-server pool.ntp.org
sudo grintion-time sync              # RTC -> system clock
sudo grintion-time sync --to-hw      # system clock -> RTC
sudo grintion-time set 2026-11-14T12:00:00 --to-hw
sudo grintion-time tz Europe/Berlin
```

The `timesync` runit service runs busybox `ntpd` against `/etc/ntp.conf`.
`status` shows the peer list, the RTC offset when readable, and the last lines
of `/var/log/timesync.log`. `tz` validates the zone against
`/usr/share/zoneinfo` before touching `/etc/localtime`.

---

## Related existing tools

| Need | Tool |
| --- | --- |
| Packages, generations, rollback | `garb` |
| Wi-Fi, roaming, DNS leak test | `grintion-network` |
| Security profiles and firewall baseline | `grintion-security` |
| System health and secure boot state | `grintion-doctor` |
| Snapshots and boot rollback | `grintion-snapshot`, `grintion-boot-health` |
| Backups and restore | `grintion-backup` |
| Hardware inventory and firmware gaps | `grintion-hwinfo`, `grintion-hcl` |
| Sanitized bug-report bundle | `grintion-report` |
| Error-code lookup | `grintion-help --list` |

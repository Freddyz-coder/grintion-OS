# System Configuration Guide

Grintion-OS provides centralized configuration tools to manage system settings across reboots
without requiring systemd.

## Central Configuration: `grintion-config`

`grintion-config` provides a unified CLI and interactive TUI to manage timezone,
locale, keyboard console maps, hostname, user accounts, runit services, and power policies:

```sh
# View current configuration in JSON
grintion-config show --json

# Set timezone, locale, keyboard, hostname
grintion-config set timezone America/New_York
grintion-config set locale en_US.UTF-8
grintion-config set keyboard us
grintion-config set hostname grintion-host

# Manage user accounts
grintion-config user list --json
grintion-config user add alice --groups wheel,audio,video

# Manage runit services
grintion-config service list
grintion-config service enable bluetoothd
grintion-config service disable bluetoothd

# Power management presets
grintion-config power governor schedutil
grintion-config power thermal balanced
```

All modifications made via `grintion-config` are written to standard `/etc` files
(`/etc/localtime`, `/etc/timezone`, `/etc/locale.conf`, `/etc/vconsole.conf`,
`/etc/hostname`, `/etc/grintion/power.conf`, `/var/service/`) and survive reboot.

### Locales and time

`grintion-config set locale` runs `localedef` before it writes
`/etc/locale.conf`. An unsupported locale fails with the compiler error instead
of being persisted; a locale that glibc cannot load silently falls back to `C`,
which turns UTF-8 output into `?`. `C.UTF-8` is built into glibc and needs no
generation.

The `timesync` runit service keeps the clock correct using the peers in
`/etc/ntp.conf` (busybox `ntpd`, part of the base image). It waits until DHCP
has provided a resolver and at least one peer resolves, logs to
`/var/log/timesync.log`, and backs off between failed starts instead of
printing `bad address` on the login console. This matters beyond
cosmetic timestamps: a wrong clock invalidates TLS certificates and makes
signed `garb` repository indexes look expired.

```sh
sv status timesync
cat /etc/ntp.conf
date -u
```

## Wi-Fi and Network Privacy: `grintion-network`

`grintion-network` manages wired and wireless networking, WPA2/WPA3 Enterprise,
saved network roaming with priority, and privacy controls:

```sh
# Connect to WPA2/WPA3 Enterprise (802.1X)
grintion-network connect-enterprise University-WiFi --identity student1 --password secret --eap-method PEAP

# Save networks with roaming priorities
grintion-network save-network Home-WiFi "passphrase123" --priority 10
grintion-network save-network Office-WiFi "workpass456" --priority 50

# Roam automatically to the highest-priority reachable access point
grintion-network roam

# Reconnect on link drops
grintion-network reconnect

# Privacy: MAC address randomization
grintion-network set-mac-randomization wlan0 enable

# Privacy: DNS leak test
grintion-network dns-leak-test --json

# Mark interface as metered
grintion-network set-metered wlan0 yes

# Network location profiles
grintion-network profile save home
grintion-network profile apply home
```

## Service Supervisor Watchdog: `grintion-watchdog`

`grintion-watchdog` monitors critical runit services (e.g. `udev`, `dbus`, `network`)
configured in `/etc/grintion/watchdog.conf`.

- Restarts killed services automatically.
- Enforces restart limits (e.g. 5 restarts within 60 seconds) to prevent infinite restart loops.
- Marks malfunctioning services as degraded and logs alerts to `/var/log/grintion-watchdog.log`.

```sh
grintion-watchdog status --json
grintion-watchdog check
```

## Power & Thermal Management: `grintion-power`

`grintion-power` controls CPU scaling governors, ACPI platform thermal profiles,
battery longevity charge thresholds, and lid switch actions:

```sh
grintion-power status --json
grintion-power set-governor powersave
grintion-power set-thermal quiet
grintion-power set-charge-limit 80
grintion-power set-lid-action suspend
```

## cgroup v2 Resource Bounds: `grintion-cgroup`

Controls memory, CPU, and PID limits for system and user service slices:

```sh
grintion-cgroup status --json
grintion-cgroup apply myapp --memory 1G --cpu "50000 100000" --pids 200
grintion-cgroup wait-for dbus --timeout 15
```


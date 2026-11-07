# Grintion Package Ecosystem & Release Engineering

This document details package generations, rollbacks, holds, pins, downgrades,
delta updates, mirror ranking, SBOM generation, and release channels in Grintion-OS.

## Package Generations & Rollback

`garb` automatically captures a snapshot of the package database before every mutating
transaction (`install`, `remove`, `upgrade`, `downgrade`), saving it under
`/var/lib/garb/generations/<N>.json`.

### Listing Generations

```sh
garb generations
# Output:
#   Generation 1    | 2026-11-07 10:00:00 | 120 packages | initial installation
#   Generation 2    | 2026-11-07 11:30:00 | 124 packages | install curl vim
# * Generation 3    | 2026-11-07 14:00:00 | 124 packages | upgrade
```

### Rolling Back to a Previous Generation

To restore the system to an exact previous package set:

```sh
garb rollback-generation 1
# [*] removing package vim (absent in generation 1)
# [*] removing package curl (absent in generation 1)
# [+] rolled back system packages to generation 1 (120 packages)
```

## Package Holds and Pins

- **Hold:** Prevents a package from being automatically upgraded by `garb upgrade`:
  ```sh
  garb hold linux-grintion
  garb unhold linux-grintion
  ```
- **Pin:** Locks a package to an exact specified version:
  ```sh
  garb pin openssl=3.0.12
  ```

## Downgrades

To downgrade an installed package to a previous version available in repository or cache:

```sh
garb downgrade demo-app 1.0.0
```

## Delta Updates

To conserve bandwidth on metered or low-speed connections, `garb` computes and applies
binary delta patches between package versions:

```sh
# Create delta between v1 and v2
garb delta-create --old pkg-1.0.0.garb --new pkg-1.1.0.garb --out pkg-delta.garb-delta

# Apply delta to reconstruct v2 from v1
garb delta-apply --old pkg-1.0.0.garb --delta pkg-delta.garb-delta --out pkg-1.1.0.garb
```

## Mirror Ranking

Measure latency across all configured repository mirrors in `/etc/garb/repos.d/*.conf`:

```sh
garb mirror-rank --format json
```

## Security Auditing, SBOM & Provenance: `grintion-audit`

`grintion-audit` inspects installed package metadata, exports Software Bill of Materials,
and scans for security advisories:

```sh
# Generate standard SPDX 2.3 JSON SBOM
grintion-audit sbom --format spdx --output /var/log/system-sbom.spdx.json

# Generate CycloneDX 1.5 JSON SBOM
grintion-audit sbom --format cyclonedx --output /var/log/system-sbom.cdx.json

# Inspect package build provenance and signing authority
grintion-audit provenance openssl

# Scan installed packages against vulnerability feed
grintion-audit scan --feed /etc/grintion/cve-feed.json --json
```

## Release Channels: `grintion-channel`

Switch between stable, beta, and nightly package repositories:

```sh
# Show active channel
grintion-channel get

# Switch release channel
grintion-channel set beta
```


# Repository Key Ceremony & Key Management Guide

This document describes the offline cryptographic key ceremony, key rotation schedule,
and security architecture for Grintion-OS package repositories and releases.

## Trust Hierarchy

Grintion-OS employs a two-tier Ed25519 cryptographic key architecture:

```
+--------------------------------------------------------------+
|            Master Root Key (Offline Air-Gapped)              |
|        (Stored in hardware security tokens / smartcards)     |
+--------------------------------------------------------------+
                               |
               Signs subkeys & revocation certs
                               v
+--------------------------------------------------------------+
|           Package Repository Signing Key (Active Subkey)     |
|              (Signs index.json and release checksums)        |
+--------------------------------------------------------------+
                               |
         Signs package metadata & repository index
                               v
+--------------------------------------------------------------+
|               Client System (garb / grintion-doctor)         |
+--------------------------------------------------------------+
```

## Key Ceremony Protocol

### 1. Root Key Generation

The Master Root Key is created on an air-gapped machine running live memory without network access:

```sh
# Generate Ed25519 Master Root Key
openssl genpkey -algorithm ed25519 -out root-master.key
openssl pkey -in root-master.key -pubout -out root-master.pub

# Generate revocation certificate
openssl pkey -in root-master.key -pubout -out root-revocation.cert
```

### 2. Subkey Delegation

The Master Root Key signs the active Repository Subkey, which has a 1-year validity period:

```sh
# Generate annual repository signing subkey
openssl genpkey -algorithm ed25519 -out repo-2026.key
openssl pkey -in repo-2026.key -pubout -out repo-2026.pub
```

### 3. Key Storage & Protection

- **Root Private Key:** Stored on encrypted offline USB tokens stored in tamper-evident physical safes.
- **Repository Private Key:** Stored in hardware security modules (HSM) or dedicated build orchestrators.
- **Client Public Keys:** Pre-installed in `/etc/garb/keys/` and compiled into `bin/garb`.

## Key Rotation Procedure

1. **Annual Scheduled Rotation:**
   - 30 days before expiration, a new Repository Subkey is generated and signed by the Master Root Key.
   - The new public key is distributed via a signed `garb-keyring` update.
   - For 14 days, repository indexes are dual-signed.
   - The old key is retired.

2. **Emergency Key Revocation:**
   - In case of key compromise, a signed revocation statement is published to the CDN and DNSSEC TXT records.
   - Clients running `garb update` refuse any index signed with the revoked key.


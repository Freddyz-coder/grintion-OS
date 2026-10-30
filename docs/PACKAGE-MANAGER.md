# Package manager

`garb` is Grintion-OS's package manager. It is a single Python 3 program that
operates on a target filesystem root, so the same command manages the live
overlay, an installed disk, or a staging directory:

```sh
garb --root /mnt install demo-hello
```

Version 1.0 provides signed repository indexes, per-file SHA-256 verification,
runtime dependency resolution and transactional installs. It does **not** build
from source, run maintainer scripts, or deliver delta updates.

---

## Commands

| Command | Purpose |
| --- | --- |
| `garb update` | Fetch `index.json` and `index.json.sig` from every configured repository and verify the signature before parsing. |
| `garb search QUERY` | Search available and installed packages. |
| `garb info PACKAGE` | Show version, description, license, architecture, dependencies and file count. |
| `garb install PACKAGE...` | Install packages and their runtime dependencies. Accepts names or a path to a `.garb` archive. |
| `garb install --upgrade PACKAGE` | Replace an installed package with the index version. |
| `garb upgrade [PACKAGE...]` | Upgrade every installed package, or only the named ones. |
| `garb remove PACKAGE...` | Remove packages. Refuses to delete files whose hashes no longer match unless `--force` is used. |
| `garb verify [PACKAGE...]` | Re-hash every installed file and report modifications. `--quick` checks presence only. |
| `garb build GARBFILE [-o DIR]` | Build one package archive from a `Garbfile`. |
| `garb repo-build SRCDIR OUTDIR` | Build every `SRCDIR/*/Garbfile` into `OUTDIR`. |
| `garb repo-index DIR [--key KEY]` | Write `index.json` for the archives in `DIR`, optionally signing it. |
| `garb keygen DIR` | Create an Ed25519 key pair (`private.pem`, `public.pem`). |
| `garb sign-index INDEX --key KEY` | Sign an existing `index.json`. |
| `garb version` | Print the tool version. |

The global `--root` option must appear before the subcommand. All paths below
are relative to that root.

---

## Repository configuration

```text
/etc/garb/repos.d/<name>.conf      repository definition
/etc/garb/keys/<name>.pub          trusted Ed25519 public key
/var/cache/garb/repos/<name>/      verified index and downloads
/var/lib/garb/db.json              installed package database
/var/lib/garb/tmp/                 staging and rollback backups
```

A repository definition is a small key/value file:

```ini
# /etc/garb/repos.d/local.conf
name = local
url = file:///srv/garb
```

`name` defaults to the config file stem. `url` may be `file:///path`, an
absolute path, or an HTTP(S) base URL. The client requests
`<url>/index.json` and `<url>/index.json.sig`, then verifies the signature with
`/etc/garb/keys/<name>.pub`.

There is no built-in repository and no key is trusted by default. An installed
system ships an empty `repos.d` directory.

---

## Repository layout

```text
index.json
index.json.sig
demo-hello-1.0.0-1.garb
demo-lib-1.0.0-1.garb
```

```json
{
  "schema": 1,
  "generated": 1767225600,
  "packages": {
    "demo-hello": {
      "version": "1.0.0",
      "release": 1,
      "description": "Demo executable that depends on demo-lib",
      "license": "GPL-3.0-or-later",
      "arch": ["x86_64"],
      "dependencies": ["demo-lib"],
      "filename": "demo-hello-1.0.0-1.garb",
      "sha256": "<archive digest>",
      "size": 1234
    }
  }
}
```

An index holds **one version per package name**. A repository that needs to
serve multiple versions must use several repositories or distinct names.

The signature is Ed25519 over the exact bytes of `index.json`. `garb` verifies
it with `openssl pkeyutl -verify -rawin` before the index is parsed or trusted.
A missing key, a malformed signature, or a key mismatch is fatal.
`garb update --allow-unsigned` exists for local development only; it disables
the trust check and must not be used for a production repository.

---

## Package format

A `.garb` file is a gzip-compressed tar archive containing:

```text
GARB_METADATA.json
<package files...>
```

`GARB_METADATA.json` records the schema, package identity, declared
dependencies and one entry per file:

```json
{
  "schema": 1,
  "name": "demo-hello",
  "version": "1.0.0",
  "release": 1,
  "description": "...",
  "license": "GPL-3.0-or-later",
  "arch": ["x86_64"],
  "dependencies": ["demo-lib"],
  "files": [
    {"path": "usr/bin/grintion-hello", "type": "file",
     "sha256": "<digest>", "mode": "0755"},
    {"path": "usr/lib/example", "type": "symlink", "target": "../lib/example"}
  ]
}
```

Paths are relative to the filesystem root and must not escape it. Absolute
paths, `..` components and undeclared files are rejected during installation.

Archives are built deterministically: sorted entries, uid/gid 0, a fixed mtime
derived from `SOURCE_DATE_EPOCH`, and gzip mtime 0.

---

## Garbfile

A package is described by a TOML `Garbfile` and a `root/` tree that mirrors the
target filesystem:

```text
packages/demo-hello/
├── Garbfile
└── root/
    └── usr/bin/grintion-hello
```

```toml
[package]
name = "demo-hello"
version = "1.0.0"
release = 1
description = "Demo executable that depends on demo-lib"
license = "GPL-3.0-or-later"
arch = ["x86_64"]

[dependencies]
runtime = ["demo-lib"]
```

`[build]` is parsed for forward compatibility but **not executed** in 1.0; a
warning is printed and the files under `root/` are packaged as-is. There are no
pre/post-install hooks, no conflicts/provides/replaces fields, and no version
constraints in dependency lists.

---

## Building and signing a repository

```sh
# 1. Create a key pair once. Keep private.pem offline.
garb keygen keys

# 2. Build every package.
garb repo-build packages output/packages

# 3. Write and sign the index.
garb repo-index output/packages --key keys/private.pem

# 4. Publish the directory and install the public key on clients.
install -m 0644 keys/public.pem /etc/garb/keys/local.pub
```

To replace the signature on an existing index:

```sh
garb sign-index output/packages/index.json --key keys/private.pem
```

The Makefile target `make packages` performs steps 2 and 3 without a key, so the
resulting index is unsigned and useful only with `--allow-unsigned`.

---

## Install semantics

1. Resolve the requested names and runtime dependencies from the cached,
   verified indexes. Dependencies are installed before their dependents.
2. Download (or copy) the archive and verify its SHA-256 from the index.
3. Extract into a staging directory under `/var/lib/garb/tmp`, rejecting
   absolute paths, `..` traversal and escaping symlinks.
4. Verify every declared file hash and mode, and reject files that the package
   does not declare.
5. Move files into place, backing up any file that is replaced.
6. Write `/var/lib/garb/db.json` atomically with `os.replace`.

If any step fails, files installed so far are removed and the backup is
restored. `remove` deletes the recorded files in reverse order and refuses to
delete a file whose current hash differs from the database, unless `--force` is
given.

A successful upgrade is not reversible: the previous file set is not kept after
the transaction commits.

---

## Limits

- No source builds, build scripts or maintainer scripts.
- No sandbox: installation runs as root and writes directly to the target root.
- No per-package signature. Trust is anchored in the repository index key.
- No delta updates, version pinning, holds or downgrades.
- No automatic updates or background service.
- No hosted repository. `make packages` creates a local unsigned demo
  repository; signing and hosting are operator responsibilities.
- Repository metadata is trusted for package names and dependencies; a
  compromised signing key compromises every client that trusts it.

"""Package database, target-root paths and transaction locking for garb."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

from .common import (
    DEFAULT_CACHE,
    DEFAULT_DB,
    DEFAULT_KEYS,
    DEFAULT_REPOS,
    DEFAULT_TMP,
    GarbError,
    SCHEMA,
    normalise_member,
    warn,
)


class Paths:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.db = self.root / DEFAULT_DB
        self.repos = self.root / DEFAULT_REPOS
        self.keys = self.root / DEFAULT_KEYS
        self.cache = self.root / DEFAULT_CACHE
        self.tmp = self.root / DEFAULT_TMP
        self.lock = self.root / "var/lib/garb/lock"
        self.journal = self.root / "var/lib/garb/journal.jsonl"
        self.generations = self.root / "var/lib/garb/generations"
        self.holds = self.root / "etc/garb/holds.conf"
        self.pins = self.root / "etc/garb/pins.conf"
        self.preferences = self.root / "etc/garb/preferences.conf"

    def ensure_runtime(self) -> None:
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.generations.mkdir(parents=True, exist_ok=True)

    def inside(self, rel: str) -> Path:
        rel = normalise_member(rel)
        target = (self.root / rel).resolve()
        if target != self.root and self.root not in target.parents:
            raise GarbError(f"path escapes the root: {rel}")
        return target


class Database:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.data = self._load()

    def _load(self) -> dict:
        if not self.paths.db.exists():
            return {"schema": SCHEMA, "packages": {}}
        try:
            with open(self.paths.db, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            # Starting empty would forget which files belong to which package
            # and let a later install overwrite them. Fail closed and point at
            # fsck instead; the database is the only ownership record.
            raise GarbError(
                f"package database is corrupt or unreadable: {self.paths.db}: {exc}; "
                "run 'garb fsck --format json' before mutating packages"
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("packages"), dict):
            raise GarbError(
                f"package database has an unexpected structure: {self.paths.db}; "
                "run 'garb fsck --format json' before mutating packages"
            )
        return data

    def save(self) -> None:
        self.paths.db.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.paths.db.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.paths.db)
        try:
            directory = os.open(self.paths.db.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError:
            return
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def installed(self, name: str) -> dict | None:
        return self.data["packages"].get(name)

    def add(self, name: str, entry: dict) -> None:
        self.data["packages"][name] = entry

    def remove(self, name: str) -> None:
        self.data["packages"].pop(name, None)


class TransactionLock:
    """One mutating native transaction per target root.

    Package installation moves files into place and then updates the database.
    Two concurrent garb processes can therefore interleave ownership records.
    The lock is advisory but every native mutating path takes it, and it names
    the holder so a blocked operator can find the other process.
    """

    def __init__(self, paths: Paths, command: str) -> None:
        self.paths = paths
        self.command = command
        self.handle = None

    def __enter__(self) -> "TransactionLock":
        self.paths.lock.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.paths.lock, "a+", encoding="utf-8")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.seek(0)
            holder = self.handle.read().strip() or "unknown holder"
            self.handle.close()
            self.handle = None
            raise GarbError(
                f"another garb transaction is running ({holder}); wait for it to finish"
            )
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()} command={self.command}\n")
        self.handle.flush()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self.handle is None:
            return
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def journal_append(paths: Paths, record: dict) -> None:
    """Append one durable transaction record.

    A crash between "started" and the final record is visible to fsck. The
    journal is append-only and mode 0600; it never stores file contents.
    """
    paths.journal.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(
        paths.journal,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_journal(paths: Paths) -> list[dict]:
    if not paths.journal.exists():
        return []
    records = []
    try:
        lines = paths.journal.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warn(f"cannot read transaction journal {paths.journal}: {exc}")
        return []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            warn(f"ignoring malformed journal line in {paths.journal}")
            continue
        if isinstance(record, dict):
            records.append(record)
    return records

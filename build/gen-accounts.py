#!/usr/bin/env python3
"""Generate account databases from config/accounts.toml.

The live image previously copied /etc/passwd, /etc/shadow and /etc/group from
the build host, which leaked Arch-specific service IDs and host-only accounts.
This generator makes the account set explicit, portable and reproducible.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path

NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]*$")
MAX_ID = 65535


def fail(message: str) -> "NoReturn":
    print(f"[-] {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        fail(f"{field} must be an absolute path")
    if ":" in value or "\n" in value:
        fail(f"{field} contains an invalid character")
    return value


def load_manifest(path: Path) -> tuple[list[dict], list[dict]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")

    users = data.get("user", [])
    groups = data.get("group", [])
    if not isinstance(users, list) or not users:
        fail("manifest defines no [[user]] entries")
    if not isinstance(groups, list) or not groups:
        fail("manifest defines no [[group]] entries")

    seen_names: set[str] = set()
    seen_ids: set[int] = set()
    for user in users:
        if not isinstance(user, dict):
            fail("user entry is not a table")
        name = user.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            fail(f"invalid user name: {name!r}")
        if name in seen_names:
            fail(f"duplicate user name: {name}")
        seen_names.add(name)
        for field in ("uid", "gid"):
            value = user.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_ID:
                fail(f"{name}: {field} must be an integer between 0 and {MAX_ID}")
        if user["uid"] in seen_ids:
            fail(f"duplicate user id: {user['uid']}")
        seen_ids.add(user["uid"])
        validate_path(user.get("home"), f"{name}: home")
        validate_path(user.get("shell"), f"{name}: shell")
        gecos = user.get("gecos", "")
        if not isinstance(gecos, str) or ":" in gecos or "\n" in gecos:
            fail(f"{name}: gecos must be a single line without ':'")
        password = user.get("password", "!")
        if not isinstance(password, str) or ":" in password or "\n" in password:
            fail(f"{name}: password must not contain ':' or a newline")
        lastchg = user.get("lastchg", 19000)
        if not isinstance(lastchg, int) or isinstance(lastchg, bool) or lastchg < 0:
            fail(f"{name}: lastchg must be a non-negative integer")

    group_names: set[str] = set()
    group_ids: set[int] = set()
    for group in groups:
        if not isinstance(group, dict):
            fail("group entry is not a table")
        name = group.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            fail(f"invalid group name: {name!r}")
        if name in group_names:
            fail(f"duplicate group name: {name}")
        group_names.add(name)
        gid = group.get("gid")
        if not isinstance(gid, int) or isinstance(gid, bool) or not 0 <= gid <= MAX_ID:
            fail(f"{name}: gid must be an integer between 0 and {MAX_ID}")
        if gid in group_ids:
            fail(f"duplicate group id: {gid}")
        group_ids.add(gid)
        members = group.get("members", [])
        if not isinstance(members, list):
            fail(f"{name}: members must be a list")
        for member in members:
            if not isinstance(member, str) or member not in seen_names:
                fail(f"{name}: unknown member {member!r}")

    for user in users:
        if user["gid"] not in group_ids:
            fail(f"{user['name']}: primary gid {user['gid']} is not in the manifest")

    return users, groups


def render(users: list[dict], groups: list[dict]) -> dict[str, str]:
    passwd = []
    shadow = []
    for user in users:
        passwd.append(
            f"{user['name']}:x:{user['uid']}:{user['gid']}:{user.get('gecos', '')}:"
            f"{user['home']}:{user['shell']}"
        )
        shadow.append(
            f"{user['name']}:{user.get('password', '!')}:{user.get('lastchg', 19000)}:"
            "0:99999:7:::"
        )
    group_lines = []
    gshadow = []
    for group in groups:
        members = ",".join(group.get("members", []))
        group_lines.append(f"{group['name']}:x:{group['gid']}:{members}")
        gshadow.append(f"{group['name']}:!::{members}")
    return {
        "passwd": "\n".join(passwd) + "\n",
        "shadow": "\n".join(shadow) + "\n",
        "group": "\n".join(group_lines) + "\n",
        "gshadow": "\n".join(gshadow) + "\n",
    }


def write_outputs(etc: Path, files: dict[str, str]) -> None:
    etc.mkdir(parents=True, exist_ok=True)
    modes = {"passwd": 0o644, "group": 0o644, "shadow": 0o600, "gshadow": 0o600}
    for name, content in files.items():
        target = etc / name
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.chmod(tmp, modes[name])
        os.replace(tmp, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="generate account databases from a manifest")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--etc", type=Path, help="target /etc directory")
    parser.add_argument("--check", action="store_true", help="validate the manifest only")
    args = parser.parse_args()

    users, groups = load_manifest(args.manifest)
    files = render(users, groups)
    if args.check:
        print(f"[+] account manifest valid: {len(users)} users, {len(groups)} groups")
        return 0
    if args.etc is None:
        fail("--etc is required unless --check is used")
    write_outputs(args.etc, files)
    print(f"[+] generated accounts in {args.etc}: {len(users)} users, {len(groups)} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Dependency and version resolution for garb."""
from __future__ import annotations

import re

from .common import GarbError
from .store import Database


def parse_dep_spec(dep: str) -> tuple[str, str, str]:
    for op in (">=", "<=", "!=", ">", "<", "="):
        if op in dep:
            parts = dep.split(op, 1)
            return parts[0].strip(), op, parts[1].strip()
    return dep.strip(), "", ""


def safe_version_tuple(val: str) -> tuple:
    parts = []
    for token in re.split(r"[._-]", str(val)):
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token))
    return tuple(parts)


def match_version(actual: str, op: str, req: str) -> bool:
    if not op or not req:
        return True
    a = safe_version_tuple(actual)
    r = safe_version_tuple(req)
    if op == ">=":
        return a >= r
    elif op == "<=":
        return a <= r
    elif op == ">":
        return a > r
    elif op == "<":
        return a < r
    elif op == "=":
        return a == r
    elif op == "!=":
        return a != r
    return True


def resolve_dependencies(names: list[str], index: dict, db: Database, upgrading: bool = False) -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in visiting:
            raise GarbError(f"dependency cycle involving {name}")
        entry = index.get(name)
        if entry is None:
            raise GarbError(f"package not found in any repository: {name}")
        if db.installed(name) and not upgrading:
            done.add(name)
            return

        for conf in entry.get("conflicts", []) or []:
            if db.installed(conf):
                raise GarbError(f"package {name} conflicts with installed package {conf}")

        visiting.add(name)
        for raw_dep in entry.get("dependencies", []) or []:
            dep_name, op, req_ver = parse_dep_spec(raw_dep)
            if dep_name not in index:
                for cand_name, cand_entry in index.items():
                    if dep_name in (cand_entry.get("provides") or []):
                        dep_name = cand_name
                        break
            if dep_name in index:
                cand = index[dep_name]
                if op and req_ver and not match_version(cand.get("version", "0"), op, req_ver):
                    raise GarbError(f"{name} requires {raw_dep}, but available version is {cand.get('version')}")
            visit(dep_name)
        visiting.remove(name)
        done.add(name)
        if not (db.installed(name) and not upgrading):
            order.append(name)

    for name in names:
        visit(name)
    return order


def version_tuple(value: str) -> tuple:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"[._-]", value))

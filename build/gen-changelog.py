#!/usr/bin/env python3
"""gen-changelog.py - automated Keep a Changelog generator for Grintion-OS.

Extracts git commit messages and tags, groups changes into Added, Changed, Fixed,
and Security categories, and formats release notes.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def get_git_commits(since_tag: str | None = None) -> list[str]:
    cmd = ["git", "log", "--oneline", "--no-merges"]
    if since_tag:
        cmd.append(f"{since_tag}..HEAD")
    else:
        cmd.extend(["-n", "50"])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.splitlines()
    except subprocess.CalledProcessError:
        return []


def categorize_commits(commits: list[str]) -> dict[str, list[str]]:
    categories = {
        "Added": [],
        "Changed": [],
        "Fixed": [],
        "Security": [],
    }
    for line in commits:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        msg = parts[1]
        lower = msg.lower()
        if any(w in lower for w in ("security", "cve", "auth", "tpm", "encrypt", "luks")):
            categories["Security"].append(msg)
        elif any(w in lower for w in ("fix", "bug", "repair", "correct")):
            categories["Fixed"].append(msg)
        elif any(w in lower for w in ("add", "feat", "new", "support", "implement")):
            categories["Added"].append(msg)
        else:
            categories["Changed"].append(msg)
    return categories


def format_changelog(version: str, categories: dict[str, list[str]]) -> str:
    lines = [
        f"## [{version}] - 2026-11-07",
        "",
    ]
    for section, items in categories.items():
        if items:
            lines.append(f"### {section}")
            for item in sorted(set(items)):
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Changelog from Git commits")
    parser.add_argument("--version", default="0.11.0")
    parser.add_argument("--since", help="git tag to diff against")
    parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    commits = get_git_commits(args.since)
    cats = categorize_commits(commits)
    changelog = format_changelog(args.version, cats)

    if args.output:
        args.output.write_text(changelog, encoding="utf-8")
        print(f"[*] wrote changelog to {args.output}")
    else:
        print(changelog)


if __name__ == "__main__":
    main()


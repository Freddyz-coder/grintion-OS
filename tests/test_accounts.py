from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GEN = REPO_ROOT / "build" / "gen-accounts.py"


def test_account_manifest_generates_portable_ids(tmp_path: Path) -> None:
    manifest = tmp_path / "accounts.toml"
    manifest.write_text(
        """
[[user]]
name = "root"
uid = 0
gid = 0
gecos = "root"
home = "/root"
shell = "/bin/bash"
password = "*"
lastchg = 19000

[[user]]
name = "daemon"
uid = 101
gid = 101
gecos = "daemon"
home = "/var/lib/daemon"
shell = "/bin/false"
password = "!"

[[group]]
name = "root"
gid = 0

[[group]]
name = "wheel"
gid = 998
members = ["root"]

[[group]]
name = "daemon"
gid = 101
""".strip()
        + "\n",
        encoding="utf-8",
    )
    etc = tmp_path / "etc"
    result = subprocess.run(
        [sys.executable, str(GEN), "--manifest", str(manifest), "--etc", str(etc)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    passwd = (etc / "passwd").read_text()
    assert "daemon:x:101:101:daemon:/var/lib/daemon:/bin/false" in passwd
    assert "spice-webdavd" not in passwd
    assert (etc / "group").read_text().count("wheel:x:998:root") == 1
    assert (etc / "shadow").stat().st_mode & stat.S_IRWXG == 0
    assert (etc / "shadow").stat().st_mode & stat.S_IRWXO == 0
    assert (etc / "gshadow").stat().st_mode & stat.S_IRWXO == 0


def test_account_manifest_rejects_duplicate_ids(tmp_path: Path) -> None:
    manifest = tmp_path / "accounts.toml"
    manifest.write_text(
        """
[[user]]
name = "root"
uid = 0
gid = 0
gecos = "root"
home = "/root"
shell = "/bin/bash"

[[user]]
name = "other"
uid = 0
gid = 0
gecos = "other"
home = "/"
shell = "/bin/false"

[[group]]
name = "root"
gid = 0
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(GEN), "--manifest", str(manifest), "--check"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "duplicate user id" in result.stderr

from __future__ import annotations

import json
import os
import subprocess
import tarfile
from pathlib import Path
import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
ETC_DIR = Path(__file__).resolve().parent.parent / "etc"


def run_bin(cmd: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    executable = BIN_DIR / cmd
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        [str(executable), *args],
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def test_grintion_tour_steps():
    res = run_bin("grintion-tour", "--json")
    assert res.returncode == 0
    stops = json.loads(res.stdout)
    assert len(stops) == 6
    assert stops[0]["step"] == 1
    assert "Garb" in stops[1]["title"]


def test_grintion_help_lookup_and_search():
    # Lookup specific error code
    res_code = run_bin("grintion-help", "E-BOOT-001", "--json")
    assert res_code.returncode == 0
    data = json.loads(res_code.stdout)
    assert "E-BOOT-001" in data
    assert "Limine" in data["E-BOOT-001"]["title"]

    # Search keyword
    res_search = run_bin("grintion-help", "--search", "DNS", "--json")
    assert res_search.returncode == 0
    search_data = json.loads(res_search.stdout)
    assert "E-NET-002" in search_data

    # Topic lookup
    res_topic = run_bin("grintion-help", "packages", "--json")
    assert res_topic.returncode == 0
    assert "garb" in res_topic.stdout.lower()


def test_grintion_report_bundle_generation_and_redaction(tmp_path: Path):
    bundle_target = tmp_path / "test-report.tar.gz"
    res = run_bin("grintion-report", "--out", str(bundle_target), "--json")
    assert res.returncode == 0
    assert bundle_target.is_file()

    # Open tarball and inspect contents
    with tarfile.open(bundle_target, "r:gz") as tar:
        names = tar.getnames()
        assert any("system.txt" in n for n in names)
        assert any("cmdline.txt" in n for n in names)


def test_boot_optimizations_and_zram_config():
    boot_opt = ETC_DIR / "grintion/boot-optimizations.conf"
    zram_conf = ETC_DIR / "grintion/zram.conf"
    zram_svc = ETC_DIR / "sv/zram/run"

    assert boot_opt.is_file()
    assert zram_conf.is_file()
    assert zram_svc.is_file()
    assert os.access(zram_svc, os.X_OK)

    content = boot_opt.read_text(encoding="utf-8")
    assert "parallel_startup=true" in content
    assert "zstd_level=19" in content


def test_handbook_and_translations():
    handbook = DOCS_DIR / "HANDBOOK.md"
    handbook_es = DOCS_DIR / "HANDBOOK-ES.md"
    baselines = DOCS_DIR / "PERFORMANCE-BASELINES.md"

    assert handbook.is_file()
    assert handbook_es.is_file()
    assert baselines.is_file()

    hb_text = handbook.read_text(encoding="utf-8")
    assert "Decision Tree" in hb_text
    assert "grintion-install" in hb_text


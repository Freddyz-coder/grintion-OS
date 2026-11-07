from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest

BUILD_DIR = Path(__file__).resolve().parent.parent / "build"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    target = BUILD_DIR / script_name
    return subprocess.run(
        [str(target), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_install_matrix_runner():
    res = run_script("test-install-matrix.py", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["matrix_permutations_tested"] >= 8
    assert data["passed"] == data["matrix_permutations_tested"]


def test_fault_injection_suite():
    res = run_script("test-fault-injection.py", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["total_faults_injected"] >= 4
    assert data["passed"] == data["total_faults_injected"]


def test_soak_test_trend_monitoring():
    res = run_script("test-soak.py", "--iterations", "10", "--delay-ms", "1", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["iterations"] == 10
    assert not data["leak_detected"]


def test_performance_benchmark_runner():
    res = run_script("benchmark-performance.py", "--runs", "1", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert len(data["benchmarks"]) >= 4
    assert data["total_avg_ms"] > 0


def test_mutation_fuzzing_parsers():
    res = run_script("fuzz-parsers.py", "--iterations", "25", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["total_crashes"] == 0


def test_gen_test_dashboard(tmp_path: Path):
    res = run_script("gen-test-dashboard.py", "--outdir", str(tmp_path))
    assert res.returncode == 0
    assert (tmp_path / "dashboard.json").is_file()
    assert (tmp_path / "junit.xml").is_file()
    assert (tmp_path / "dashboard.html").is_file()


def test_hardware_lab_matrix_documentation():
    hw_lab = DOCS_DIR / "HARDWARE-LAB.md"
    assert hw_lab.is_file()
    content = hw_lab.read_text(encoding="utf-8")
    for test_id in ["BM-TEST-001", "BM-TEST-005", "BM-TEST-012"]:
        assert test_id in content


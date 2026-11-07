#!/usr/bin/env python3
"""build/benchmark-performance.py - performance regression and boot-time benchmark tool."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS_DIR = REPO_ROOT / "benchmarks"


def benchmark_tool(cmd: list[str], runs: int = 5) -> dict:
    durations = []
    for _ in range(runs):
        t0 = time.perf_counter()
        res = subprocess.run(cmd, capture_output=True, check=False)
        t1 = time.perf_counter()
        durations.append(t1 - t0)

    avg_ms = round((sum(durations) / len(durations)) * 1000, 2)
    min_ms = round(min(durations) * 1000, 2)
    max_ms = round(max(durations) * 1000, 2)
    return {
        "command": " ".join(cmd),
        "runs": runs,
        "avg_ms": avg_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
    }


def run_benchmarks(runs: int = 3) -> dict:
    targets = [
        [str(REPO_ROOT / "bin/garb"), "--help"],
        [str(REPO_ROOT / "bin/grintion-security"), "list"],
        [str(REPO_ROOT / "bin/grintion-hcl"), "--json"],
        [str(REPO_ROOT / "bin/grintion-privacy"), "--json"],
        [str(REPO_ROOT / "bin/grintion-usb"), "status"],
    ]

    benchmarks = []
    for t in targets:
        benchmarks.append(benchmark_tool(t, runs=runs))

    # Calculate overall baseline stats
    total_avg_ms = round(sum(b["avg_ms"] for b in benchmarks), 2)

    return {
        "timestamp": int(time.time()),
        "host": os.uname().nodename,
        "total_avg_ms": total_avg_ms,
        "benchmarks": benchmarks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark-performance",
        description="Benchmark tool execution latencies and capture performance baselines.",
    )
    parser.add_argument("--save", action="store_true", help="Save baseline to benchmarks/baseline.json")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark iterations")
    parser.add_argument("--json", action="store_true", help="Output in JSON")
    args = parser.parse_args()

    data = run_benchmarks(runs=args.runs)

    if args.save:
        BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
        baseline_file = BENCHMARKS_DIR / "baseline.json"
        baseline_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved benchmark baseline to {baseline_file}")

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print("================================================================================")
    print("                    GRINTION-OS PERFORMANCE REGRESSION BENCHMARK                ")
    print("================================================================================")
    print(f"{'COMMAND':50} {'AVG (ms)':10} {'MIN (ms)':10} {'MAX (ms)':10}")
    print("-" * 80)
    for b in data["benchmarks"]:
        short_cmd = Path(b["command"].split()[0]).name + " " + " ".join(b["command"].split()[1:])
        print(f"{short_cmd:50} {b['avg_ms']:10.2f} {b['min_ms']:10.2f} {b['max_ms']:10.2f}")

    print(f"\nTotal Suite Latency: {data['total_avg_ms']} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


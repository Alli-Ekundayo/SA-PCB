#!/usr/bin/env python3
"""
Robust multi-start launcher for SA-PCB.

Supports deterministic seeding, worker pools, timeout handling,
JSON configuration, and structured result reporting.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclasses.dataclass
class RunResult:
    run_id: int
    seed: int
    returncode: Optional[int]
    cost: Optional[float]
    runtime_sec: float
    status: str
    command: List[str]
    stdout: str
    stderr: str
    output_placement: Optional[str]


@dataclasses.dataclass
class MultistartConfig:
    binary: str = "./sa"
    placement: str = "designs/bm1"
    iterations_outer: int = 2500
    iterations_inner: int = 25
    initial_temperature: float = 0.025
    runs: int = 8
    workers: int = max(1, os.cpu_count() or 1)
    timeout_sec: int = 900
    seed: int = 0
    seed_option: str = ""
    extra_args: List[str] = dataclasses.field(default_factory=list)
    output_dir: str = "cache/multistart"


def _parse_cost(stdout: str, stderr: str) -> Optional[float]:
    text = f"{stdout}\n{stderr}"
    for line in text.splitlines():
        if "cost" in line.lower():
            vals = _FLOAT_RE.findall(line)
            if vals:
                return float(vals[-1])
    vals = _FLOAT_RE.findall(text)
    return float(vals[-1]) if vals else None


def _load_config(path: Optional[str]) -> MultistartConfig:
    cfg = MultistartConfig()
    if not path:
        return cfg

    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    ms = data.get("multistart", data)
    for field in dataclasses.fields(MultistartConfig):
        if field.name in ms:
            setattr(cfg, field.name, ms[field.name])
    return cfg


def _build_command(cfg: MultistartConfig, run_id: int, run_seed: int, output_dir: Path) -> List[str]:
    out_base = output_dir / f"run_{run_id:03d}"
    cmd = [
        cfg.binary,
        "-p",
        cfg.placement,
        "-i",
        str(cfg.iterations_outer),
        "-j",
        str(cfg.iterations_inner),
        "-t",
        str(cfg.initial_temperature),
        "-x",
        str(run_id),
    ]
    if cfg.seed_option:
        cmd.extend([cfg.seed_option, str(run_seed)])
    cmd.extend([
        "-f",
        str(out_base),
    ])
    cmd.extend(cfg.extra_args)
    return cmd


def _run_once(cfg: MultistartConfig, run_id: int, run_seed: int) -> RunResult:
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_command(cfg, run_id, run_seed, output_dir)

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_sec,
            check=False,
        )
        cost = _parse_cost(proc.stdout, proc.stderr)
        status = "ok" if proc.returncode == 0 else "failed"
        out_pl = str(output_dir / f"run_{run_id:03d}.pl")
        if not Path(out_pl).exists():
            out_pl = None
        return RunResult(
            run_id=run_id,
            seed=run_seed,
            returncode=proc.returncode,
            cost=cost,
            runtime_sec=time.time() - started,
            status=status,
            command=cmd,
            stdout=proc.stdout,
            stderr=proc.stderr,
            output_placement=out_pl,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            run_id=run_id,
            seed=run_seed,
            returncode=None,
            cost=None,
            runtime_sec=time.time() - started,
            status="timeout",
            command=cmd,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            output_placement=None,
        )


def _choose_best(results: List[RunResult]) -> Optional[RunResult]:
    valid = [r for r in results if r.cost is not None and r.status == "ok"]
    if not valid:
        return None
    return min(valid, key=lambda r: r.cost)


def run_multistart(cfg: MultistartConfig) -> Dict[str, Any]:
    random.seed(cfg.seed)
    seeds = [random.randint(0, 2**31 - 1) for _ in range(cfg.runs)]

    results: List[RunResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=cfg.workers) as pool:
        fut_to_run = {
            pool.submit(_run_once, cfg, i, seeds[i]): i
            for i in range(cfg.runs)
        }
        for fut in concurrent.futures.as_completed(fut_to_run):
            results.append(fut.result())

    results.sort(key=lambda r: r.run_id)
    best = _choose_best(results)

    summary = {
        "config": dataclasses.asdict(cfg),
        "completed": len(results),
        "ok": sum(1 for r in results if r.status == "ok"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "timed_out": sum(1 for r in results if r.status == "timeout"),
        "best": dataclasses.asdict(best) if best else None,
        "results": [dataclasses.asdict(r) for r in results],
    }

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "multistart_results.json", "w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic parallel multistart placements.")
    parser.add_argument("--config", default=None, help="Path to JSON config file")
    parser.add_argument("--runs", type=int, default=None, help="Override number of starts")
    parser.add_argument("--workers", type=int, default=None, help="Override worker pool size")
    parser.add_argument("--seed", type=int, default=None, help="Override base seed")
    parser.add_argument("--timeout-sec", type=int, default=None, help="Override per-run timeout")
    args = parser.parse_args()

    cfg = _load_config(args.config)
    if args.runs is not None:
        cfg.runs = args.runs
    if args.workers is not None:
        cfg.workers = args.workers
    if args.seed is not None:
        cfg.seed = args.seed
    if args.timeout_sec is not None:
        cfg.timeout_sec = args.timeout_sec

    summary = run_multistart(cfg)
    best = summary["best"]
    if best:
        print(f"best run={best['run_id']} seed={best['seed']} cost={best['cost']}")
        return 0

    print("no successful runs")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

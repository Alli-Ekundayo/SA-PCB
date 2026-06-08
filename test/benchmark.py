#!/usr/bin/env python3
"""Benchmark utility for SA-PCB multistart outputs."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "py_utils"))

import load_bookshelf  # noqa: E402
import utils  # noqa: E402


def compute_overlap_area(components):
    polys = list(components.values())
    overlap = 0.0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j])
            if not inter.is_empty:
                overlap += inter.area
    return overlap


def compute_hpwl(components, board_pins, nets):
    hpwl = 0.0
    comp2rot = {name: "N" for name in components.keys()}
    for net in nets:
        xs = []
        ys = []
        for pin in net:
            if pin[0] in components:
                x, y = utils.pin_pos2(pin, components, comp2rot)
            else:
                x, y = pin[1].x, pin[1].y
            xs.append(math.floor(x))
            ys.append(math.floor(y))
        if xs and ys:
            hpwl += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return hpwl


def evaluate_placement(design_base: Path, pl_file: Path):
    nodes = load_bookshelf.read_nodes(str(design_base.with_suffix(".nodes")))
    components, _, _, board_pins, _ = load_bookshelf.read_pl2(str(pl_file), nodes)
    nets, _ = load_bookshelf.read_nets2(str(design_base.with_suffix(".nets")), components, board_pins)
    return {
        "hpwl": compute_hpwl(components, board_pins, nets),
        "overlap": compute_overlap_area(components),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark SA-PCB outputs")
    parser.add_argument("--design", required=True, help="Design base path without extension")
    parser.add_argument("--results", required=True, help="multistart_results.json path")
    parser.add_argument("--out", default="benchmark_summary.json", help="Output summary path")
    args = parser.parse_args()

    t0 = time.time()
    with open(args.results, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    best = data.get("best")
    if not best or not best.get("output_placement"):
        print("No best placement found in results")
        return 1

    metrics = evaluate_placement(Path(args.design), Path(best["output_placement"]))

    summary = {
        "runtime_sec": time.time() - t0,
        "best_run_id": best["run_id"],
        "best_cost": best.get("cost"),
        "metrics": metrics,
    }
    with open(args.out, "w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

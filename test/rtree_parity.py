#!/usr/bin/env python3
"""Parity check between brute-force and STRtree overlap computation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shapely.strtree import STRtree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "py_utils"))

import load_bookshelf  # noqa: E402


def brute_force_overlap(polys):
    total = 0.0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j])
            if not inter.is_empty:
                total += inter.area
    return total


def strtree_overlap(polys):
    total = 0.0
    tree = STRtree(polys)
    for i, p in enumerate(polys):
        for j in tree.query(p):
            if j <= i:
                continue
            inter = p.intersection(polys[j])
            if not inter.is_empty:
                total += inter.area
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True, help="Design base path without extension")
    parser.add_argument("--pl", required=True, help="Placement file path")
    parser.add_argument("--tol", type=float, default=1e-6)
    args = parser.parse_args()

    nodes = load_bookshelf.read_nodes(args.design + ".nodes")
    comps, _, _, _, _ = load_bookshelf.read_pl2(args.pl, nodes)
    polys = list(comps.values())

    b = brute_force_overlap(polys)
    r = strtree_overlap(polys)
    diff = abs(b - r)
    print(f"bruteforce={b} strtree={r} diff={diff}")
    return 0 if diff <= args.tol else 2


if __name__ == "__main__":
    raise SystemExit(main())

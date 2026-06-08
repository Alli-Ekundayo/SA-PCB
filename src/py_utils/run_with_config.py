#!/usr/bin/env python3
"""Run SA-PCB with JSON config and CLI overrides."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_update(dst[k], v)
        else:
            dst[k] = v
    return dst


def apply_cli_overrides(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    placer = cfg.setdefault("placer", {})
    if args.rtree is not None:
        placer["rtree"] = args.rtree
    if args.rotation_mode is not None:
        placer["rotation_mode"] = args.rotation_mode
    if args.outer_iter is not None:
        placer["num_iterations"] = args.outer_iter
    if args.inner_iter is not None:
        placer["iterations_moves"] = args.inner_iter
    if args.temperature is not None:
        placer["initial_temperature"] = args.temperature
    return cfg


def validate(cfg: Dict[str, Any]) -> None:
    if "placer" not in cfg:
        raise ValueError("Missing required top-level 'placer' configuration section")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply JSON algorithm parameters.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--override", action="append", default=[], help="Additional override JSON file")
    parser.add_argument("--rtree", type=lambda x: x.lower() in {"1", "true", "yes"}, default=None)
    parser.add_argument("--rotation-mode", choices=["90", "45", "free"], default=None)
    parser.add_argument("--outer-iter", type=int, default=None)
    parser.add_argument("--inner-iter", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--print-effective", action="store_true")
    args = parser.parse_args()

    cfg = load_json(args.config)
    for ov in args.override:
        deep_update(cfg, load_json(ov))
    cfg = apply_cli_overrides(cfg, args)
    validate(cfg)

    if args.print_effective:
        print(json.dumps(cfg, indent=2))

    # This script intentionally focuses on validated config handling.
    # Execution can be delegated to multistart.py or a SWIG runner.
    effective_path = Path(cfg.get("output", {}).get("effective_config", "cache/effective_config.json"))
    effective_path.parent.mkdir(parents=True, exist_ok=True)
    with open(effective_path, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

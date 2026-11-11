"""Command line: python -m data_generator {generate,validate,reproduce} ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_SEED, PROFILES, config_for
from .pipeline import generate, reproduce
from .validate import validate

ROOT = Path(__file__).resolve().parents[1]


def data_dir_for(profile: str) -> Path:
    return ROOT / "data" / profile


def main(argv=None):
    p = argparse.ArgumentParser(prog="data_generator", description="Synthetic performance-management data")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "validate", "reproduce"):
        s = sub.add_parser(name)
        s.add_argument("--profile", default="starter", choices=sorted(PROFILES))
        if name != "validate":
            s.add_argument("--seed", type=int, default=DEFAULT_SEED)
            s.add_argument("--scale", type=float, default=None, help="override profile scale")
    a = p.parse_args(argv)

    if a.cmd == "generate":
        cfg = config_for(a.profile, a.scale, a.seed)
        generate(cfg, data_dir_for(a.profile))
    elif a.cmd == "validate":
        s = validate(data_dir_for(a.profile))
        print(f"  validation {s['overall_status']}: {s['checks_passed']}/{s['checks_total']} checks passed")
        for r in s["checks"]:
            print(f"   [{r['status']}] {r['check']:<40} violations={r['violations']:<5} unexplained={r['unexplained']}")
        if s["overall_status"] != "PASS":
            sys.exit(1)
    elif a.cmd == "reproduce":
        cfg = config_for(a.profile, a.scale, a.seed)
        r = reproduce(cfg, data_dir_for(a.profile).parent / f"reproducibility_{a.profile}.json")
        print(f"  identical={r['identical']} files_compared={r['files_compared']} mismatched={len(r['mismatched_files'])}")
        if not r["identical"]:
            sys.exit(1)


if __name__ == "__main__":
    main()

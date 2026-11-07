"""Run the pipeline on every tune id in data/split.csv.

Holdout ids are never read unless --holdout is passed, which runs the 12 holdout
ids instead of tune.

Usage:
  .venv\\Scripts\\python.exe scripts\\run_batch.py [--holdout]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.main import load_split, run_ids  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--holdout", action="store_true", help="run the holdout ids instead of tune")
    args = ap.parse_args()
    want = "holdout" if args.holdout else "tune"
    ids = sorted(i for i, s in load_split().items() if s == want)
    print(f"[batch] {len(ids)} {want} ids")
    _, failures = run_ids(ids, allow_holdout=args.holdout)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

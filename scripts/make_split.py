"""Lock the stratified tune/holdout split.

Holdout: 2 per gold intent (12 total). Within each class, T01-T10 (human-labeled)
are taken first, then the rest is filled from the other cases. Both picks use one
seeded RNG. Tune: the remaining 28. T38 stays in; it is skipped only at scoring.

Writes data/split.csv (id, split). Deterministic: rerunning produces the same file.
"""
import csv
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "labels.csv"
OUT = ROOT / "data" / "split.csv"

SEED = 20261028
CLASSES = ["NR", "WA", "UN", "CNP", "NAD", "ESC"]
PER_CLASS = 2
HUMAN_LABELED = {f"T{i:02d}" for i in range(1, 11)}


def main():
    with open(LABELS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_class = {c: [] for c in CLASSES}
    for r in rows:
        intent = r["confirmed_intent"].strip().upper()
        if intent not in by_class:
            sys.exit(f"{r['id']}: unknown gold intent {intent!r}")
        by_class[intent].append(r["id"].strip())

    rng = random.Random(SEED)
    holdout = set()
    for c in CLASSES:
        ids = sorted(by_class[c])
        if len(ids) < PER_CLASS:
            sys.exit(f"{c}: only {len(ids)} cases, need {PER_CLASS}")
        human = [i for i in ids if i in HUMAN_LABELED]
        rest = [i for i in ids if i not in HUMAN_LABELED]
        picked = rng.sample(human, min(PER_CLASS, len(human)))
        picked += rng.sample(rest, PER_CLASS - len(picked))
        holdout.update(picked)

    all_ids = sorted(r["id"].strip() for r in rows)
    if len(set(all_ids)) != len(all_ids):
        sys.exit("duplicate ids in labels.csv")

    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "split"])
        for i in all_ids:
            w.writerow([i, "holdout" if i in holdout else "tune"])

    intent_of = {r["id"].strip(): r["confirmed_intent"].strip().upper() for r in rows}
    counts = Counter((intent_of[i], "holdout" if i in holdout else "tune") for i in all_ids)
    print(f"{'class':<6}{'tune':>6}{'holdout':>9}")
    for c in CLASSES:
        print(f"{c:<6}{counts[(c, 'tune')]:>6}{counts[(c, 'holdout')]:>9}")
    print(f"{'total':<6}{len(all_ids) - len(holdout):>6}{len(holdout):>9}")


if __name__ == "__main__":
    main()

"""Score a pipeline run against data/labels.csv.

Usage:
  .venv\\Scripts\\python.exe scripts\\score.py runs\\<timestamp> [--holdout]
  .venv\\Scripts\\python.exe scripts\\score.py --self-test

Few-shot cases (is_fewshot_example) are excluded from every metric. T38 is scored
on intent only (labeling_notes.md rule 3). Holdout labels are used only with
--holdout. Dollar costs are illustrative, on the spec section 4 grid.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "labels.csv"
SPLIT = ROOT / "data" / "split.csv"
SPEC = ROOT / "spec" / "intake_spec.md"
FEWSHOT = ROOT / "backend" / "prompts" / "classify_fewshot.json"

INTENTS = ["NR", "WA", "UN", "CNP", "NAD", "ESC"]
GRID_INTENTS = ["NR", "WA", "UN", "CNP", "NAD"]
DISPUTES = {"NR", "WA", "UN", "CNP"}
COST = {"C": 5, "H": 50, "X": 500}  # illustrative; finance would set real ones
GOLD_FIELDS = ["amount_disputed", "within_60_days", "temp_credit_eligible", "notice_link_sent"]
INTENT_ONLY = {"T38"}  # labeling_notes.md rule 3
CHECK_TYPES = [
    ("gendered pronoun in note", r"^note uses gendered pronouns"),
    ("next_action not allowed for intent", r"^next_action \S+ is not allowed"),
    ("next_action not a spec code", r"is not a spec code$"),
    ("policy_ids outside retrieved set", r"^policy_ids outside"),
    ("within_60_days disagrees with statement_date", r"^within_60_days:"),
    ("payload missing fields", r"^payload missing"),
    ("intent/escalate_reason overwritten", r"^(intent|escalate_reason): model wrote"),
    ("escalate_reason on non-ESC intent", r"^classifier gave escalate_reason"),
]


def norm(v):
    """Booleans -> 'true'/'false'; numbers and numeric strings -> float; other strings lowercased."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if v is None:
        return "null"
    s = str(v).strip().lower()
    try:
        return round(float(s.replace("$", "").replace(",", "")), 2)
    except ValueError:
        return s


def load_labels(allow_holdout):
    with open(SPLIT, encoding="utf-8", newline="") as f:
        split = {r["id"]: r["split"] for r in csv.DictReader(f)}
    with open(LABELS, encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)
                if allow_holdout or split[r["id"]] == "tune"}


def load_grid():
    """Spec section 4: actual intent -> predicted intent -> ok | C | H | X."""
    grid = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| \*\*(NR|WA|UN|CNP|NAD)\*\* \|(.+)\|$", line)
        if m:
            grid[m[1]] = dict(zip(GRID_INTENTS, (c.strip() for c in m[2].split("|"))))
    if list(grid) != GRID_INTENTS or any(len(row) != 5 for row in grid.values()):
        sys.exit("could not read the 5x5 cost grid from spec section 4")
    return grid


def check_type(text):
    for name, pattern in CHECK_TYPES:
        if re.search(pattern, text):
            return name
    return "other"


def score(results, labels, title):
    fewshot = sorted(i for i, r in results.items() if r["is_fewshot_example"])
    ids = sorted(i for i in results if i not in fewshot)
    unknown = [i for i in ids if i not in labels]
    if unknown:
        sys.exit(f"no usable labels for {unknown} (holdout ids need --holdout)")
    gold_ids = [i for i in ids if i not in INTENT_ONLY]
    grid = load_grid()

    actual = {i: labels[i]["confirmed_intent"].strip().upper() for i in ids}
    pred = {i: str(results[i]["intent"]).strip().upper() for i in ids}
    payload = {i: results[i].get("payload") or {} for i in ids}
    misses = []

    # Intent, cost tiers
    confusion = Counter((actual[i], pred[i]) for i in ids)
    tiers = Counter()
    for i in ids:
        if norm(actual[i]) == norm(pred[i]):
            continue
        misses.append((i, "intent", actual[i], pred[i]))
        tiers["n/a" if "ESC" in (actual[i], pred[i]) else grid[actual[i]][pred[i]]] += 1
    dollars = sum(COST[t] * n for t, n in tiers.items() if t in COST)

    # Next action and gold fields (T38 skipped)
    next_hits = 0
    for i in gold_ids:
        g, p = labels[i]["expected_next_action"], payload[i].get("next_action")
        if norm(g) == norm(p):
            next_hits += 1
        else:
            misses.append((i, "next_action", g, p))
    field_hits = Counter()
    for f in GOLD_FIELDS:
        for i in gold_ids:
            g, p = labels[i][f"gold_{f}"], payload[i].get(f)
            if norm(g) == norm(p):
                field_hits[f] += 1
            else:
                misses.append((i, f, g, p))

    # Policy-id recall (report only; T38 skipped). Kept apart from decision misses.
    policy_rows, policy_misses = [], []
    for i in gold_ids:
        expected = [p.strip().upper() for p in labels[i]["expected_policy_ids"].split(";") if p.strip()]
        predicted = [str(p).strip().upper() for p in payload[i].get("policy_ids") or []]
        missing = [p for p in expected if p not in predicted]
        policy_rows.append((i, expected, predicted, len(expected) - len(missing)))
        if missing:
            policy_misses.append((i, missing, predicted))

    pred_true = [i for i in gold_ids if norm(payload[i].get("temp_credit_eligible")) == "true"]
    temp_tp = sum(norm(labels[i]["gold_temp_credit_eligible"]) == "true" for i in pred_true)
    actual_un = [i for i in ids if actual[i] == "UN"]
    disputes = [i for i in ids if actual[i] in DISPUTES]
    escalated = [i for i in ids if pred[i] == "ESC"]
    checks = Counter(check_type(c) for i in ids for c in results[i].get("checks", []))
    cost = sum(sum((u or {}).get("cost") or 0 for u in (results[i].get("usage") or {}).values()) for i in ids)
    latency = sum(sum((results[i].get("latency_s") or {}).values()) for i in ids)

    n = len(ids)
    out = [f"# Score: {title}", "",
           f"Clean cases: {n} (few-shot excluded: {', '.join(fewshot) or 'none'})",
           f"Gold-field cases: {len(gold_ids)} ({', '.join(sorted(INTENT_ONLY & set(ids))) or 'none'} scored on intent only)",
           "", "## 1. Intent confusion (actual rows, predicted columns)", "",
           "| actual \\ predicted | " + " | ".join(INTENTS) + " | total |",
           "|---|" + "---|" * (len(INTENTS) + 1)]
    for a in INTENTS:
        row = [confusion[(a, p)] for p in INTENTS]
        out.append(f"| **{a}** | " + " | ".join(str(c) for c in row) + f" | {sum(row)} |")
    out += ["", "## 2. Cost-weighted errors (illustrative: C=$5, H=$50, X=$500)", "",
            f"C: {tiers['C']}, H: {tiers['H']}, X: {tiers['X']}, n/a (ESC, outside the grid): {tiers['n/a']}",
            f"Total: ${dollars:,}",
            "", "## 3. Per class", "", "| class | cases | correct |", "|---|---|---|"]
    for c in INTENTS:
        out.append(f"| {c} | {sum(actual[i] == c for i in ids)} | {confusion[(c, c)]} |")
    out += ["", "## 4-8. Headline counts", "",
            f"- UN caught: {sum(pred[i] == 'UN' for i in actual_un)} of {len(actual_un)}",
            f"- Disputes caught (NR/WA/UN/CNP not predicted NAD): "
            f"{sum(pred[i] != 'NAD' for i in disputes)} of {len(disputes)}",
            f"- Temp-credit precision: {temp_tp} of {len(pred_true)} predicted true",
            f"- Escalations: {len(escalated)} predicted ESC, "
            f"{sum(actual[i] != 'ESC' for i in escalated)} on clear cases (gold not ESC)",
            f"- Next action: {next_hits} of {len(gold_ids)}",
            "", "## 9. Gold fields", "", "| field | matches |", "|---|---|"]
    for f in GOLD_FIELDS:
        out.append(f"| {f} | {field_hits[f]} of {len(gold_ids)} |")
    out += ["", "## 10. Checks fired", ""]
    out += [f"- {name}: {count}" for name, count in checks.most_common()] or ["- none"]
    out += ["", "## 11. Cost and latency", "",
            f"- Cost: ${cost:.4f} total, ${cost / n:.4f} per case" if n else "- Cost: n/a",
            f"- Latency: {latency:.1f}s total, {latency / n:.1f}s per case" if n else "- Latency: n/a",
            "", "## 12. Policy-id recall (report only)", "",
            f"All expected ids present: {len(policy_rows) - len(policy_misses)} of {len(policy_rows)}", "",
            "| id | expected | predicted | found |", "|---|---|---|---|"]
    out += [f"| {i} | {', '.join(e)} | {', '.join(p) or '-'} | {k} of {len(e)} |"
            for i, e, p, k in policy_rows]
    out += ["", "## Misses", ""]
    if misses:
        out += ["| id | field | gold | predicted |", "|---|---|---|---|"]
        out += [f"| {i} | {f} | {g} | {p} |" for i, f, g, p in sorted(misses)]
    else:
        out.append("none")
    if any(i in INTENT_ONLY and f == "intent" for i, f, _, _ in misses):
        out += ["", "T38: rule 3 also accepts WA or NR when the note names the other issue. Check the note by hand."]
    out += ["", "## Policy-id misses", ""]
    if policy_misses:
        out += ["| id | missing | predicted |", "|---|---|---|"]
        out += [f"| {i} | {', '.join(m)} | {', '.join(p) or '-'} |" for i, m, p in policy_misses]
    else:
        out.append("none")
    return "\n".join(out) + "\n", misses, policy_misses


def as_model_value(v):
    """Turn a gold CSV string into the type the model emits, to exercise norm()."""
    s = v.strip()
    if s.upper() in ("TRUE", "FALSE"):
        return s.upper() == "TRUE"
    try:
        return float(s)
    except ValueError:
        return s


def self_test():
    labels = load_labels(allow_holdout=False)
    fewshot = {s["id"] for s in json.loads(FEWSHOT.read_text(encoding="utf-8"))["examples"]}
    results = {}
    for i, r in labels.items():
        payload = {"next_action": r["expected_next_action"],
                   "policy_ids": r["expected_policy_ids"].lower().split(";")}
        payload.update({f: as_model_value(r[f"gold_{f}"]) for f in GOLD_FIELDS})
        results[i] = {"intent": r["confirmed_intent"], "payload": payload,
                      "is_fewshot_example": i in fewshot, "checks": []}
    report, misses, policy_misses = score(results, labels, "self-test (predictions = tune gold labels)")
    print(report)
    failed = len(misses) + len(policy_misses)
    print("SELF-TEST PASSED" if not failed else f"SELF-TEST FAILED: {failed} misses")
    return 0 if not failed else 1


def main():
    ap = argparse.ArgumentParser(description="Score a pipeline run against gold labels.")
    ap.add_argument("run_folder", nargs="?")
    ap.add_argument("--holdout", action="store_true", help="allow holdout labels")
    ap.add_argument("--self-test", action="store_true", help="score gold against itself; must be perfect")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.run_folder:
        ap.error("run_folder is required unless --self-test")
    folder = Path(args.run_folder)
    results = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("T*.json"))}
    if not results:
        sys.exit(f"no T*.json results in {folder}")
    report, _, _ = score(results, load_labels(args.holdout), folder.name)
    (folder / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

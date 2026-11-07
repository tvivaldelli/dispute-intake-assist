"""Dispute intake pipeline: classify -> retrieve -> note + payload.

Usage:
  .venv\\Scripts\\python.exe backend\\main.py T01 T12 [--holdout]

Only the transcript turns and call_date are sent to a model. Every other field in
the transcript file (id, hard_case, seed_intent, seed_reason_code, ...) is stripped.
Holdout ids are refused unless --holdout is passed.
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SPEC = ROOT / "spec" / "intake_spec.md"
TRANSCRIPTS = ROOT / "data" / "transcripts"
SPLIT = ROOT / "data" / "split.csv"
PROMPTS = Path(__file__).resolve().parent / "prompts"
RUNS = ROOT / "runs"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
# Empty .env values load as "", so fall back with `or`, not a getenv default.
CLASSIFY_MODEL = os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL
NOTE_MODEL = os.getenv("NOTE_MODEL") or CLASSIFY_MODEL

SENT_FIELDS = {"transcript", "call_date"}
INTENTS = {"NR", "WA", "UN", "CNP", "NAD", "ESC"}
ESCALATE_REASONS = {"SOP_GAP", "LOW_CONFIDENCE", "CUSTOMER_RISK"}
NEXT_ACTIONS = {"OPEN_DISPUTE", "FRAUD_TRANSFER", "CNP_WAIT", "RESOLVE_ON_CALL",
                "CLAIMS_DEFENSES", "SUPERVISOR", "CHARGEBACK_REVIEW"}
PAYLOAD_FIELDS = ["intent", "escalate_reason", "merchant", "transaction_date", "statement_date",
                  "amount_posted", "amount_disputed", "customer_contacted_merchant", "within_60_days",
                  "notice_link_sent", "written_notice_received", "temp_credit_eligible",
                  "next_action", "policy_ids"]
# Spec section 2 next-action codes, read by intent.
ALLOWED_NEXT_ACTIONS = {
    "NR": {"OPEN_DISPUTE", "CHARGEBACK_REVIEW"},
    "WA": {"OPEN_DISPUTE", "CHARGEBACK_REVIEW"},
    "CNP": {"CNP_WAIT", "OPEN_DISPUTE", "CHARGEBACK_REVIEW"},
    "UN": {"FRAUD_TRANSFER"},
    "NAD": {"RESOLVE_ON_CALL", "CLAIMS_DEFENSES"},
    "ESC": {"SUPERVISOR"},
}
GENDERED_PRONOUN = r"\b(?:he|she|him|her|his|hers)\b"
POLICY_ID = r"(?:REG|POL)-\d{2}"
TOP_K = 3


class PipelineError(Exception):
    pass


# --- inputs ---

def load_split():
    with open(SPLIT, encoding="utf-8", newline="") as f:
        return {r["id"]: r["split"] for r in csv.DictReader(f)}


def load_case(case_id):
    """Return the model-visible case and the names of the fields stripped from it."""
    raw = json.loads((TRANSCRIPTS / f"{case_id}.json").read_text(encoding="utf-8"))
    turns = []
    # Blank lines between turns (T12, T36) are dropped; a line with no speaker
    # continues the previous turn.
    for line in raw["transcript"].splitlines():
        line = line.strip()
        if not line:
            continue
        if turns and not re.match(r"^(Agent|Customer):", line):
            turns[-1] += " " + line
        else:
            turns.append(line)
    case = {"call_date": raw["call_date"], "turns": turns}
    return case, sorted(set(raw) - SENT_FIELDS)


def case_message(case):
    return f"Call date: {case['call_date']}\n\nTranscript:\n" + "\n".join(case["turns"])


def load_prompt(name):
    """Prompt files start with a 'version: <v>' line, then a '---' line."""
    head, body = (PROMPTS / name).read_text(encoding="utf-8").split("\n---\n", 1)
    return head.removeprefix("version:").strip(), body.strip()


def load_corpus():
    """The 20 policy snippets from spec section 3."""
    corpus = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(rf"^- \*\*({POLICY_ID}) (.+?)\.\*\* (.+)$", line)
        if m:
            corpus[m[1]] = f"{m[2]}. {m[3]}"
    if len(corpus) != 20:
        raise PipelineError(f"expected 20 policy snippets in spec section 3, found {len(corpus)}")
    return corpus


def load_taxonomy():
    """Spec section 1 rows: intent -> definition plus correct next action."""
    rows = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (NR|WA|UN|CNP|NAD|ESC) \| [^|]+ \| (.+?) \| (.+?) \|$", line)
        if m:
            rows[m[1]] = f"{m[2]} {m[3]}"
    if set(rows) != INTENTS:
        raise PipelineError(f"spec section 1 taxonomy rows found: {sorted(rows)}")
    return rows


# --- retrieval ---

STOPWORDS = set("""a an and are as at be been but by can could did do does for from had has
have he her his how i if in into is it its just me my no not of on or our she so that the
their them then there they this to was we were what when which who will with would you your
yes okay""".split())


def tokens(text):
    out = []
    for w in re.findall(r"[a-z]+", re.sub(POLICY_ID, " ", text).lower()):
        if len(w) < 3 or w in STOPWORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 4:
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


def retrieve(case, intent, corpus, taxonomy):
    """Top-k snippets by keyword overlap, weighted by IDF across the 20 snippets.

    Query: transcript turns plus the spec section 1 row for the predicted intent.
    Snippet ids that the row names (e.g. POL-04 for NR) rank first.
    """
    query = set(tokens(" ".join(case["turns"]) + " " + taxonomy[intent]))
    docs = {pid: set(tokens(text)) for pid, text in corpus.items()}
    df = {}
    for terms in docs.values():
        for t in terms:
            df[t] = df.get(t, 0) + 1
    scores = {pid: sum(math.log(1 + len(docs) / df[t]) for t in query & terms)
              for pid, terms in docs.items()}
    cited = set(re.findall(POLICY_ID, taxonomy[intent]))
    ranked = sorted(corpus, key=lambda pid: (pid not in cited, -scores[pid], pid))
    return [{"id": pid, "score": round(scores[pid], 3), "cited_by_intent": pid in cited,
             "text": corpus[pid]} for pid in ranked[:TOP_K]]


# --- model calls ---

def chat(model, messages, max_tokens):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise PipelineError("OPENROUTER_API_KEY not set")
    t0 = time.perf_counter()
    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens},
        timeout=120,
    )
    latency = round(time.perf_counter() - t0, 3)
    if r.status_code != 200:
        raise PipelineError(f"{model}: HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    choice = data["choices"][0]
    text = choice["message"].get("content")
    if choice.get("finish_reason") == "length" or not text:
        usage = data.get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        raise PipelineError(f"{model}: no complete answer (finish_reason={choice.get('finish_reason')}, "
                            f"completion_tokens={usage.get('completion_tokens')}, reasoning_tokens={reasoning})")
    return text, {"requested": model, "served": data.get("model"),
                  "latency_s": latency, "usage": data.get("usage")}


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise PipelineError(f"no JSON object in model output: {text[:300]!r}")
    try:
        return json.loads(m[0])
    except json.JSONDecodeError as e:
        raise PipelineError(f"bad JSON from model ({e}): {text[:300]!r}")


def classify(case, split):
    version, system = load_prompt("classify.md")
    shots = json.loads((PROMPTS / "classify_fewshot.json").read_text(encoding="utf-8"))
    messages = [{"role": "system", "content": system}]
    for s in shots["examples"]:
        if split.get(s["id"]) != "tune":
            raise PipelineError(f"few-shot {s['id']} is not a tune case")
        example, _ = load_case(s["id"])
        answer = {k: s[k] for k in ("intent", "escalate_reason", "rationale")}
        messages.append({"role": "user", "content": case_message(example)})
        messages.append({"role": "assistant", "content": json.dumps(answer)})
    messages.append({"role": "user", "content": case_message(case)})

    text, call = chat(CLASSIFY_MODEL, messages, max_tokens=2000)
    out = parse_json(text)
    intent, reason, checks = out.get("intent"), out.get("escalate_reason"), []
    if intent not in INTENTS:
        raise PipelineError(f"classifier returned intent {intent!r}")
    if intent == "ESC" and reason not in ESCALATE_REASONS:
        raise PipelineError(f"classifier returned ESC with escalate_reason {reason!r}")
    if intent != "ESC" and reason is not None:
        checks.append(f"classifier gave escalate_reason {reason!r} for {intent}; set to null")
        reason = None
    return {"intent": intent, "escalate_reason": reason, "rationale": out.get("rationale"),
            "fewshot_ids": [s["id"] for s in shots["examples"]],
            "versions": {"classify": version, "fewshot": shots["version"]},
            "call": call, "checks": checks}


def generate(case, cls, retrieved):
    version, system = load_prompt("note.md")
    esc = f" ({cls['escalate_reason']})" if cls["escalate_reason"] else ""
    snippets = "\n".join(f"{r['id']}: {r['text']}" for r in retrieved)
    user = f"{case_message(case)}\n\nIntent: {cls['intent']}{esc}\n\nPolicy snippets:\n{snippets}"
    text, call = chat(NOTE_MODEL, [{"role": "system", "content": system},
                                   {"role": "user", "content": user}], max_tokens=4000)
    out = parse_json(text)
    if not isinstance(out.get("note"), str) or not isinstance(out.get("payload"), dict):
        raise PipelineError(f"generator output missing note or payload: {text[:300]!r}")
    return out["note"], out["payload"], version, call


# --- checks ---

def within_60_days(statement_date, call_date):
    try:
        days = (date.fromisoformat(call_date) - date.fromisoformat(str(statement_date))).days
    except ValueError:
        return None
    return days <= 60


def check_payload(payload, cls, retrieved, call_date):
    """Enforce what code can enforce; record everything changed or doubted."""
    checks = []
    missing = [k for k in PAYLOAD_FIELDS if k not in payload]
    if missing:
        checks.append(f"payload missing fields: {missing}")
    for k in ("intent", "escalate_reason"):
        if payload.get(k) != cls[k]:
            checks.append(f"{k}: model wrote {payload.get(k)!r}, set to classifier's {cls[k]!r}")
            payload[k] = cls[k]
    allowed = {r["id"] for r in retrieved}
    ids = payload.get("policy_ids") or []
    dropped = [p for p in ids if p not in allowed]
    if dropped:
        checks.append(f"policy_ids outside the retrieved set, dropped: {dropped}")
        payload["policy_ids"] = [p for p in ids if p in allowed]
    if payload.get("next_action") not in NEXT_ACTIONS:
        checks.append(f"next_action {payload.get('next_action')!r} is not a spec code")
    elif payload["next_action"] not in ALLOWED_NEXT_ACTIONS[cls["intent"]]:
        checks.append(f"next_action {payload['next_action']} is not allowed for intent {cls['intent']}")
    computed = within_60_days(payload.get("statement_date"), call_date)
    if computed is not None and payload.get("within_60_days") != computed:
        checks.append(f"within_60_days: model wrote {payload.get('within_60_days')!r}, "
                      f"computed {computed} from statement_date")
    return checks


# --- runs ---

def run_case(case_id, split, out_dir, allow_holdout=False):
    if case_id not in split:
        raise PipelineError(f"{case_id} is not in split.csv")
    if split[case_id] == "holdout" and not allow_holdout:
        raise PipelineError(f"{case_id} is holdout; pass --holdout to run it")

    case, stripped = load_case(case_id)
    cls = classify(case, split)
    retrieved = retrieve(case, cls["intent"], load_corpus(), load_taxonomy())
    note, payload, note_version, note_call = generate(case, cls, retrieved)
    checks = cls["checks"] + check_payload(payload, cls, retrieved, case["call_date"])
    pronouns = sorted({p.lower() for p in re.findall(GENDERED_PRONOUN, note, re.I)})
    if pronouns:
        checks.append(f"note uses gendered pronouns: {pronouns}")

    result = {
        "id": case_id,
        "split": split[case_id],
        "call_date": case["call_date"],
        "intent": cls["intent"],
        "escalate_reason": cls["escalate_reason"],
        "classifier_rationale": cls["rationale"],
        "retrieved": retrieved,
        "note": note,
        "payload": payload,
        "checks": checks,
        "is_fewshot_example": case_id in cls["fewshot_ids"],
        "stripped_fields": stripped,
        "models": {"classify": cls["call"]["requested"], "classify_served": cls["call"]["served"],
                   "note": note_call["requested"], "note_served": note_call["served"]},
        "prompt_versions": {**cls["versions"], "note": note_version},
        "latency_s": {"classify": cls["call"]["latency_s"], "note": note_call["latency_s"]},
        "usage": {"classify": cls["call"]["usage"], "note": note_call["usage"]},
    }
    (out_dir / f"{case_id}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def run_ids(ids, allow_holdout=False):
    """Run each id into runs/<timestamp>/. Failures are logged and the run continues."""
    split = load_split()
    out_dir = RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    failures = []
    for case_id in ids:
        try:
            run_case(case_id, split, out_dir, allow_holdout)
            print(f"[ok]   {case_id}")
        except Exception as e:
            failures.append({"id": case_id, "error": f"{type(e).__name__}: {e}"})
            print(f"[fail] {case_id}: {type(e).__name__}: {e}")
    (out_dir / "_failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
    print(f"{len(ids) - len(failures)} written, {len(failures)} failed -> {out_dir}")
    return out_dir, failures


def main():
    ap = argparse.ArgumentParser(description="Run the intake pipeline on transcript ids.")
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--holdout", action="store_true", help="allow holdout ids")
    args = ap.parse_args()
    _, failures = run_ids(args.ids, allow_holdout=args.holdout)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

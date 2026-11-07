"""
Generate the 40 seeded synthetic transcripts described in spec/intake_spec.md section 6.

Every case is fixed in MANIFEST (seed label, hard-case tag, names, amounts,
which facts get said aloud), so the class and hard-case mix is reproducible.
Only the transcript wording comes from the model.

The generator never sees the seed label. It gets the scenario and the facts,
and writes a call that stops before the agent decides anything.

Outputs:
  data/transcripts/T01.json .. T40.json
  data/labels.csv  (written only if absent; Tom fills in the confirmed, expected, and gold columns)

Usage:
  .venv\\Scripts\\python.exe scripts\\gen_transcripts.py
  .venv\\Scripts\\python.exe scripts\\gen_transcripts.py --ids T05 T12 --force
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# The classifier is anthropic/claude-haiku-5.5; spec section 6 requires a
# different model family for generation.
CLASSIFIER_FAMILY = "anthropic/"
OUT_DIR = ROOT / "data" / "transcripts"
LABELS_PATH = ROOT / "data" / "labels.csv"
LABEL_COLUMNS = ["id", "seed_intent", "seed_reason_code", "confirmed_intent",
                 "confirmed_reason_code", "expected_policy_ids", "expected_next_action",
                 "gold_amount_disputed", "gold_within_60_days", "gold_temp_credit_eligible",
                 "gold_notice_link_sent", "changed", "change_reason"]
MAX_ATTEMPTS = 3

# All calls happen on this date; statement dates are counted back from it.
CALL_DATE = date(2026, 10, 15)


class Case(NamedTuple):
    id: str
    intent: str
    reason: str | None
    hard_case: str | None
    customer: str
    merchant: str
    amount: float
    days_since_statement: int | None  # None: charge not on a statement yet
    says_statement_date: bool
    says_amount: bool
    scenario: str


MANIFEST = [
    # --- NR ---
    Case("T01", "NR", None, "broken_vs_dislike", "Dana Whitcombe", "Larkspur Home Goods", 89.00, 12, True, True,
         "Ordered a ceramic table lamp online. It arrived shattered in the box; the customer never used it."),
    Case("T02", "NR", None, "window_day_55_60", "Marcus Ellery", "BrightBench Assembly Co", 340.00, 57, True, True,
         "Paid in advance for a furniture assembly visit. The technician never showed and never rescheduled. The customer put off calling for weeks."),
    Case("T03", "NR", None, "broken_vs_dislike", "Priya Castellan", "Ridgeline Cycle Supply", 612.40, 20, False, True,
         "A bike was delivered with a cracked frame. The customer refused the delivery and the driver took it back."),
    Case("T04", "NR", None, None, "Owen Taggart", "StagePass Tix", 275.00, 18, False, False,
         "Bought two concert tickets. They were never emailed or mailed, and the show has already happened."),
    Case("T05", "NR", None, None, "Lena Mortimer", "Northfold Outfitters", 148.99, 9, True, True,
         "Ordered a winter coat in size medium. Received a size extra-large coat in a different style."),
    Case("T06", "NR", None, None, "Felix Arango", "Giftwell Express", 64.50, 25, False, True,
         "Paid for guaranteed delivery by a birthday. The gift arrived a week after the promised date."),
    Case("T07", "NR", None, None, "Rosa Quintero", "Halvorsen Audio", 420.00, 30, True, False,
         "Tracking shows the speakers were delivered to an address on another street. The customer never got them."),
    # --- WA ---
    Case("T08", "WA", None, "window_past_60", "Gideon Park", "Harborlight Inn", 512.80, 62, True, True,
         "A two-night hotel stay was charged twice. The customer only noticed while doing their budget."),
    Case("T09", "WA", None, "two_issues", "Tessa Brannigan", "Copper Kettle Bistro", 98.00, 14, False, True,
         "The customer wrote a $12 tip but was charged a $42 tip. Partway through, they also ask why their annual fee went up. The tip is why they called."),
    Case("T10", "WA", None, None, "Ivan Delacroix", "QuickFuel 214", 61.20, 6, False, True,
         "One fill-up at a gas station shows as two identical charges."),
    Case("T11", "WA", None, None, "Harriet Osei", "Millbrook Auto Care", 1480.00, 22, True, True,
         "A repair shop quoted $1,150 in writing for brake work and charged $1,480 without calling first."),
    Case("T12", "WA", None, None, "Cal Hendricks", "IronGate Fitness", 79.00, 11, False, False,
         "Signed up for a gym at a $39 promotional monthly rate. Was charged about double."),
    Case("T13", "WA", None, None, "Mei Lindqvist", "Paperloom Studio", 267.00, 16, True, True,
         "Ordered and received one print, but was charged for three."),
    Case("T14", "WA", None, None, "Rafael Sutter", "Skyward Air", 189.00, 33, False, True,
         "Bought one seat upgrade and was charged for it twice. The customer keeps calling it fraud."),
    # --- UN ---
    Case("T15", "UN", None, "family_member", "Joanna Prentiss", "PixelForge Games", 230.00, 8, False, True,
         "The customer's teenage son took the card from their wallet and bought in-game items. The customer never let him use the card."),
    Case("T16", "UN", None, "unrecognized_descriptor", "Desmond Achebe", "QPX*NOVALINE 8842", 349.99, 4, False, True,
         "The customer has never heard of this merchant, never shopped there, and still has the card in their wallet."),
    Case("T17", "UN", None, "family_member", "Beatrix Holloway", "VoltWorks Electronics", 899.00, 10, False, True,
         "The customer's adult brother was staying with them and bought a laptop with the card. The customer never let him use it."),
    Case("T18", "UN", None, None, "Nikhil Varga", "several stores in Tallow Creek", 1240.55, 3, False, False,
         "The customer lost the card on a trip. Several charges then showed up at stores in a city they never visited."),
    Case("T19", "UN", None, None, "Corinne Abara", "StreamNest Plus", 4.99, 15, True, True,
         "A small monthly subscription charge for a service the customer never signed up for."),
    Case("T20", "UN", None, None, "Theo Marchetti", "Gadgetry Direct", 1875.00, None, False, True,
         "The customer got a text alert about an online purchase while the card was in their hand at home."),
    Case("T21", "UN", None, None, "Wendell Ashby", "Coastline Car Rental", 412.30, 21, True, True,
         "A car rental charge from a state the customer has never been to. The customer calls it a billing mistake."),
    # --- CNP ---
    Case("T22", "CNP", None, "return_refund_missing", "Ingrid Solano", "Fernway Footwear", 135.00, 18, True, True,
         "Returned shoes in store and has a return receipt from 16 business days ago. No refund on the account, and a statement has closed since."),
    Case("T23", "CNP", None, "return_refund_missing", "Barnaby Coyle", "KitchenCraft Online", 79.95, 5, False, True,
         "Mailed back a blender. The merchant emailed 'return accepted, refund issued' 4 business days ago."),
    Case("T24", "CNP", None, None, "Yusra Haddad", "Lakeview Suites", 460.00, 27, True, True,
         "Cancelled a hotel booking inside the free-cancellation window, has a cancellation number, and was told the credit would post. That was three weeks ago."),
    Case("T25", "CNP", None, None, "Aldo Fenwick", "Clearview TV Outlet", 50.00, 40, False, True,
         "The store agreed to a $50 price adjustment on a TV after a price drop. It hasn't shown up after two statements."),
    Case("T26", "CNP", None, None, "Simone Okafor", "Peakform Gym", 59.00, 35, False, False,
         "Cancelled a gym membership. The gym said it would refund the last month's dues. Nothing after over a month."),
    Case("T27", "CNP", None, None, "Elliot Raskin", "ByteBarn Computers", 1099.00, 9, True, True,
         "Returned a laptop in store and got a refund slip 7 business days ago. The refund isn't on the account yet."),
    Case("T28", "CNP", None, None, "Grace Mbeki", "Skyward Air", 388.40, 44, False, True,
         "The airline cancelled the flight and promised a refund to the card six weeks ago. The customer says they 'never got their flight'."),
    # --- NAD ---
    Case("T29", "NAD", None, "unrecognized_descriptor", "Hollis Dunmore", "SQ *BLUE HERON PROV", 42.00, 7, False, True,
         "The customer doesn't recognize the descriptor. When the agent gives the date and town, the customer realizes it was a candle stall at a farmers' market."),
    Case("T30", "NAD", None, "family_member", "Patricia Lowell", "Juniper & Vine Apparel", 318.75, 12, False, True,
         "The customer gave their daughter the card for back-to-school shopping. She spent more than the customer expected, and the customer is upset."),
    Case("T31", "NAD", None, "broken_vs_dislike", "Kenji Aldridge", "Restwell Furniture", 1350.00, 30, False, True,
         "The sofa arrived as ordered and undamaged. After a month of use the customer finds it uncomfortable and wants their money back."),
    Case("T32", "NAD", None, None, "Lorraine Vick", "Summit Office Supply", 214.60, 10, True, True,
         "The customer needs a copy of the receipt for an expense report. Nothing is wrong with the charge."),
    Case("T33", "NAD", None, None, "Dmitri Sorensen", "The Gilded Fork", 76.40, 5, False, True,
         "The customer ate the meal, paid, and thought the food was bad. They want the charge removed."),
    Case("T34", "NAD", None, None, "Abigail Treadway", "StreamNest Plus", 119.88, 13, True, True,
         "The customer says a streaming charge is 'wrong', then realizes on the call that they chose the annual plan themselves and forgot."),
    Case("T35", "NAD", None, None, "Rupert Calloway", "Brightcoat Painting", 2400.00, 26, False, True,
         "A contractor painted the house. The customer accepted the job and paid, and now dislikes how it looks."),
    # --- ESC ---
    Case("T36", "ESC", "SOP_GAP", None, "Nathaniel Greer (son of the late cardholder, Walter Greer)", "Elmstead Pharmacy", 180.00, 15, False, True,
         "The caller is the adult son of a cardholder who recently died. He wants to dispute a charge on his father's card."),
    Case("T37", "ESC", "SOP_GAP", None, "Monica Faraday (office manager, Faraday & Pell LLC)", "Corvid Office Systems", 2950.00, 19, True, True,
         "An office manager calls about a charge on the company's business card, billed for equipment they say the company never ordered."),
    Case("T38", "ESC", "LOW_CONFIDENCE", "two_issues", "Leon Abernathy", "Harvest Table Market and Trailhead Gear", 220.00, 23, False, True,
         "The customer raises two problems with equal urgency: a $220 grocery charge that appears twice, and a $145 backpack order that never arrived."),
    Case("T39", "ESC", "LOW_CONFIDENCE", "return_refund_missing", "Sabrina Kowalczyk", "Lumen & Loft Decor", 310.00, 28, False, True,
         "The customer says they sent a mirror back but has no tracking number and no confirmation the merchant got it. They aren't sure anyone ever promised a refund."),
    Case("T40", "ESC", "CUSTOMER_RISK", None, "Edna Pruitt", "Valuemax Home Shopping", 600.00, 9, False, False,
         "An elderly caller sounds confused about which charge is wrong and repeats themselves. They mention that a man on the phone earlier helped them 'fix' their account."),
]

SYSTEM_PROMPT = """You write realistic synthetic phone transcripts between a credit card company's customer service agent and a cardholder. Everything is fictional.

Format:
- One turn per line, each starting with "Agent:" or "Customer:". No headings, narration, or stage directions.
- 14 to 30 turns. The agent greets the caller, verifies them briefly, and asks questions to understand what happened.
- End the call while the agent is still gathering facts, or right after the agent sums up what the customer said. The agent never says what kind of problem this is, what process it goes to, who the caller will be transferred to, or what happens next.

The customer:
- Describes what happened in plain, everyday words, the way a real caller would. They may be vague, ramble, or use the wrong terms.
- States only the facts marked [said aloud]. Facts marked [not said] must not appear in any form, from either speaker. The agent does not read them off the account either.

Neither speaker ever uses:
- The words "unauthorized", "billing error", "not as agreed", "wrong amount", "credit not posted", "not a dispute", or any form of "escalate".
- Regulation or policy references (Reg Z, section numbers, codes like REG-01 or POL-01).
- Real company, brand, or person names. Use only the names given."""

LEAK_PATTERNS = [
    re.compile(r"\b(NR|WA|UN|CNP|NAD|ESC)\b"),
    re.compile(r"\b(REG|POL)-?\d+", re.IGNORECASE),
    re.compile(r"unauthori[sz]ed|billing error|not as agreed|wrong amount|credit not posted|not a dispute|escalat",
               re.IGNORECASE),
]


def check_manifest() -> None:
    """Fail fast if MANIFEST drifts from spec section 6."""
    errors = []
    ids = [c.id for c in MANIFEST]
    if ids != [f"T{i:02d}" for i in range(1, 41)]:
        errors.append("ids must be T01..T40 in order")
    counts = Counter(c.intent for c in MANIFEST)
    if counts != Counter({"NR": 7, "WA": 7, "UN": 7, "CNP": 7, "NAD": 7, "ESC": 5}):
        errors.append(f"class counts wrong: {dict(counts)}")
    reasons = Counter(c.reason for c in MANIFEST if c.intent == "ESC")
    if reasons != Counter({"SOP_GAP": 2, "LOW_CONFIDENCE": 2, "CUSTOMER_RISK": 1}):
        errors.append(f"ESC reason counts wrong: {dict(reasons)}")
    if any(c.reason for c in MANIFEST if c.intent != "ESC"):
        errors.append("reason code set on a non-ESC case")
    hard = Counter(c.intent for c in MANIFEST if c.hard_case)
    for intent in counts:
        if hard[intent] < 2:
            errors.append(f"{intent} has {hard[intent]} hard cases, needs 2")
    tags = {c.hard_case for c in MANIFEST}
    for tag in ("window_day_55_60", "two_issues"):
        if tag not in tags:
            errors.append(f"missing hard case {tag}")
    if not any(c.amount < 250 for c in MANIFEST) or not any(c.amount >= 250 for c in MANIFEST):
        errors.append("amounts must fall on both sides of $250")
    if errors:
        sys.exit("MANIFEST check failed:\n  " + "\n  ".join(errors))


def build_prompt(c: Case) -> str:
    if c.days_since_statement is None:
        txn = CALL_DATE - timedelta(days=2)
        statement = "Statement: the charge has not appeared on a statement yet."
    else:
        stmt = CALL_DATE - timedelta(days=c.days_since_statement)
        txn = stmt - timedelta(days=10)
        said = "said aloud" if c.says_statement_date else "not said"
        statement = f"Statement date: {stmt:%B %d, %Y} [{said}]"
    lines = [
        f"Call date: {CALL_DATE:%B %d, %Y}",
        f"Caller: {c.customer}",
        f"Merchant: {c.merchant}",
        f"Charge date: {txn:%B %d, %Y}",
        f"Amount: ${c.amount:,.2f} [{'said aloud' if c.says_amount else 'not said'}]",
        statement,
        f"What happened: {c.scenario}",
    ]
    return "Write the transcript for this call.\n\n" + "\n".join(lines)


def generate(model: str, api_key: str, c: Case) -> str:
    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(c)},
            ],
            "temperature": 0.9,
            "max_tokens": 3000,
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"].strip()


def problems(text: str, c: Case) -> list[str]:
    found = [f"leak: {m.group(0)!r}" for p in LEAK_PATTERNS for m in p.finditer(text)]
    if c.days_since_statement is not None:
        day_count = re.compile(rf"\b{c.days_since_statement}[\s-]days?\b")
        found += [f"leak: {m.group(0)!r}" for m in day_count.finditer(text)]
    bad = [line for line in text.splitlines() if line.strip() and not line.startswith(("Agent:", "Customer:"))]
    if bad:
        found.append(f"format: {len(bad)} line(s) without a speaker, first: {bad[0][:60]!r}")
    return found


def write_labels() -> None:
    rel = LABELS_PATH.relative_to(ROOT)
    if LABELS_PATH.exists():
        print(f"[labels] {rel} exists, left untouched")
        return
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LABELS_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(LABEL_COLUMNS)
        for c in MANIFEST:
            w.writerow([c.id, c.intent, c.reason or ""] + [""] * (len(LABEL_COLUMNS) - 3))
    print(f"[labels] wrote {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate seeded intake transcripts")
    parser.add_argument("--ids", nargs="+", help="only these case ids, e.g. T05 T12")
    parser.add_argument("--force", action="store_true", help="overwrite existing transcript files")
    args = parser.parse_args()

    check_manifest()

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("GEN_MODEL")
    if not api_key:
        print(f"FAIL: OPENROUTER_API_KEY not set (looked in {ENV_PATH})")
        return 1
    if not model:
        print(f"FAIL: GEN_MODEL not set (looked in {ENV_PATH})")
        return 1
    if model.startswith(CLASSIFIER_FAMILY):
        print(f"FAIL: GEN_MODEL {model!r} is the classifier's family. Spec section 6 requires a different one.")
        return 1

    known = {c.id for c in MANIFEST}
    if args.ids and set(args.ids) - known:
        print(f"FAIL: unknown ids {sorted(set(args.ids) - known)}")
        return 1
    cases = [c for c in MANIFEST if not args.ids or c.id in args.ids]

    write_labels()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[gen] model: {model}")

    failed = []
    for c in cases:
        path = OUT_DIR / f"{c.id}.json"
        if path.exists() and not args.force:
            print(f"[{c.id}] exists, skipped (use --force to overwrite)")
            continue
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                text = generate(model, api_key, c)
            except (requests.RequestException, RuntimeError, KeyError) as e:
                print(f"[{c.id}] attempt {attempt}: {type(e).__name__}: {e}")
                continue
            issues = problems(text, c)
            if not issues:
                break
            print(f"[{c.id}] attempt {attempt}: {'; '.join(issues)}")
        else:
            failed.append(c.id)
            continue
        record = {
            "id": c.id,
            "transcript": text,
            "seed_intent": c.intent,
            "seed_reason_code": c.reason,
            "hard_case": c.hard_case,
            "call_date": CALL_DATE.isoformat(),
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[{c.id}] wrote {path.relative_to(ROOT)}")

    if failed:
        print(f"\nFAILED after {MAX_ATTEMPTS} attempts: {', '.join(failed)}")
        return 1
    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

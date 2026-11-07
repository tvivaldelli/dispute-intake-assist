"""Review screen for committed result runs.

Usage:
  .venv\\Scripts\\python.exe review\\server.py [--port 8765] [--log PATH]

Serves review/index.html and a read-only JSON API over results/ and data/transcripts/.
Only agent-visible fields leave the server: gold labels, seed fields and run metadata stay on disk.
Approve and override decisions are appended to a JSONL log (default review/review_log.jsonl).
"""
import argparse
import json
import re
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.main import ESCALATE_REASONS, INTENTS, NEXT_ACTIONS  # noqa: E402

RESULTS = ROOT / "results"
TRANSCRIPTS = ROOT / "data" / "transcripts"
PAGE = Path(__file__).resolve().parent / "index.html"
DEFAULT_LOG = Path(__file__).resolve().parent / "review_log.jsonl"

# Source: spec/intake_spec.md §2. Pipeline does not validate this field.
TEMP_CREDIT = {True, False, "n/a"}
OVERRIDE_FIELDS = {
    "intent": INTENTS,
    "escalate_reason": ESCALATE_REASONS | {None},
    "next_action": NEXT_ACTIONS,
    "temp_credit_eligible": TEMP_CREDIT,
}

# Whitelist, not a blacklist: a field added to the files later stays off the page.
CASE_FIELDS = ["id", "call_date", "intent", "escalate_reason", "classifier_rationale",
               "payload", "note", "checks", "retrieved"]
SAFE_ID = re.compile(r"[\w-]+")
CASE_ID = re.compile(r"T\d+")  # skips _failures.json and report.md


def run_dir(run):
    if not SAFE_ID.fullmatch(run) or not (RESULTS / run).is_dir():
        return None
    return RESULTS / run


def list_runs():
    return sorted(p.name for p in RESULTS.iterdir() if p.is_dir())


def list_cases(run):
    cases = []
    for path in sorted(run_dir(run).glob("T*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        cases.append({"id": r["id"], "intent": r["intent"],
                      "next_action": r["payload"].get("next_action"), "checks": len(r["checks"])})
    return cases


def load_result(run, case_id):
    """Return one case's result file as the pipeline wrote it, or None if it doesn't exist."""
    if not run_dir(run) or not CASE_ID.fullmatch(case_id):
        return None
    path = run_dir(run) / f"{case_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_case(run, case_id):
    """Return the agent-visible view of one case, or None if it doesn't exist."""
    result = load_result(run, case_id)
    if result is None:
        return None
    raw = json.loads((TRANSCRIPTS / f"{case_id}.json").read_text(encoding="utf-8"))
    case = {k: result[k] for k in CASE_FIELDS}
    case["run"] = run
    case["transcript"] = raw["transcript"]
    return case


def allowed(value, values):
    # Type-strict: True == 1 in Python, so plain `in` would accept 1 for temp_credit_eligible.
    return any(value == v and type(value) is type(v) for v in values)


def log_entry(body):
    """Validate a review decision and build its log line. Original values come from disk, not the page."""
    run, case_id = str(body.get("run", "")), str(body.get("case", ""))
    result = load_result(run, case_id)
    if result is None:
        raise ValueError("unknown run or case")
    original = {"intent": result["intent"], "escalate_reason": result["escalate_reason"],
                "next_action": result["payload"]["next_action"],
                "temp_credit_eligible": result["payload"]["temp_credit_eligible"]}
    action = body.get("action")
    if action == "approve":
        override, reason = None, None
    elif action == "override":
        override, reason = body.get("override"), body.get("reason")
        if not isinstance(override, dict) or set(override) != set(OVERRIDE_FIELDS):
            raise ValueError(f"override must set exactly {sorted(OVERRIDE_FIELDS)}")
        bad = [k for k, v in override.items() if not allowed(v, OVERRIDE_FIELDS[k])]
        if bad:
            raise ValueError(f"values not allowed for {bad}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("override needs a reason")
        reason = reason.strip()
    else:
        raise ValueError("action must be approve or override")
    return {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_id": run, "case_id": case_id, "action": action,
            "original": original, "override": override, "reason": reason}


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, obj):
        self.send_body(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if parts == [""]:
            return self.send_body(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        if parts == ["api", "runs"]:
            return self.send_json(HTTPStatus.OK, list_runs())
        if parts == ["api", "enums"]:
            return self.send_json(HTTPStatus.OK, {k: sorted(v, key=json.dumps)
                                                  for k, v in OVERRIDE_FIELDS.items()})
        if len(parts) == 3 and parts[:2] == ["api", "run"] and run_dir(parts[2]):
            return self.send_json(HTTPStatus.OK, list_cases(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "case"] and run_dir(parts[2]):
            case = load_case(parts[2], parts[3])
            if case:
                return self.send_json(HTTPStatus.OK, case)
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/log":
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            entry = log_entry(body)
        except ValueError as e:  # includes json.JSONDecodeError
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        with self.server.log_lock, open(self.server.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.send_json(HTTPStatus.OK, entry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.log_path = args.log.resolve()
    server.log_lock = threading.Lock()
    print(f"Review screen: http://127.0.0.1:{args.port}/")
    print(f"Log: {server.log_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()

# Dispute Intake Assist

Two-day prototype. Spec: `spec/intake_spec.md`. LLM: OpenRouter only, model `anthropic/claude-haiku-5.5`.
Retrieval: keyword matching over the policy snippets, on purpose (no embeddings).
Run Python through `.venv\Scripts\python.exe`. Smoke test: `scripts/smoke_test.py`.

## How we work

- Show a plan before running anything.
- One logical change per commit.
- Run `git status` and `git log --oneline -3` before describing repo state. Never describe it from memory.
- Don't modify files outside the stated scope.
- Don't paste or print API keys.
- Stop at each gate and wait for approval.

## Rules from here on

- No prompt or retrieval changes. Prompts frozen at 9f64749.
- The holdout is never rerun. It was run once at 21c7a93.

## Current state

- 40 transcripts and gold labels committed. Split locked 28/12 (`data/split.csv`).
- Pipeline done: `backend/main.py` (classify, retrieve, note + payload), prompts in `backend/prompts/`.
- Batch runner done: `scripts/run_batch.py` (tune by default, `--holdout` for holdout).
- Scorer done: `scripts/score.py <run_folder>`, with `--self-test`.
- Committed results: `results/tune-A/` and `results/holdout/`. `runs/` is ignored.
- Holdout notes hand-scored (`results/holdout/note_scores.md`): Complete 12/12, Correct next step 12/12, Grounded 12/12, Usable handoff 10/12.
- Review screen done: `.venv\Scripts\python.exe review\server.py`, then http://127.0.0.1:8765/. Log: `review/review_log.jsonl` (ignored).
- Honest limits are tracked in `data/labeling_notes.md`.

## Next

1. Write-up.
2. Loom.

## Known issues

- `.gitignore` ignores `docs/` and `*.png`. Files there won't be committed.
- Empty `.env` values override defaults: python-dotenv loads `KEY=` as `""`, so `os.getenv(KEY, default)` returns `""`.
- Dependencies are mostly unpinned. `requirements.lock.txt` was frozen on Windows / Python 3.12.10.
- `backend/requirements.txt` still lists packages from the old app that the pipeline doesn't use, and `.env.example` comments are stale. Left as is until asked.
- T16 and T20 contain `�` replacement characters in the source text. Left as is.

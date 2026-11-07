# Dispute Intake Assist

**Synthetic data. Prototype, not production.** The transcripts are generated, and the issuer policy snippets (POL-\*) are invented for this project. The regulation snippets (REG-\*) paraphrase public Reg Z, 12 CFR 1026.12 and 1026.13. See [Errata](#errata).

## What it does

It reads a card billing-dispute call transcript and classifies the intent (not received, wrong amount, unauthorized, credit not posted, not a dispute, or escalate). It then retrieves the relevant policy snippets and drafts an after-call note and a structured payload of proposed next steps. **The model proposes and never acts.** A human approves or overrides every proposal in the review screen.

## Eval design

- **Models.** Classifier and note generator: `anthropic/claude-haiku-5.5`. Transcript generator: `google/gemini-3.8-flash`. Both through OpenRouter.
- **40 labeled transcripts.** Split 28 tune / 12 holdout, stratified 2 per class in the holdout, and locked in [`data/split.csv`](data/split.csv) before the prompts were first committed. Labeling rules and honest limits are in [`data/labeling_notes.md`](data/labeling_notes.md). The full spec is in [`spec/intake_spec.md`](spec/intake_spec.md).
- **Order of events** (from the private working repo this was published from, 2026-10-28, -0500):
  - split locked: commit a5cbc78, 16:20:46
  - prompts first committed: commit 2cde1cf, 17:07:15 (unchanged after this)
  - prompts frozen: commit 9f64749, 17:28:10 (adds the scorer only; marks the freeze, no prompt change)
  - holdout run: commit 21c7a93, 17:30:07 (adds report-only policy-id recall to the scorer); run folder `20261028-173014` (17:30:14)
  - The holdout ran once and nothing was changed after seeing it.
- **Cost-weighted error grid** (spec section 4). Errors are priced by who gets hurt, not counted equally.
  - *UNAUTHORIZED row, all customer harm:* missed fraud lets more charges land, so UN is tuned for recall. Over-routing a real purchase to fraud costs only a card reissue.
  - *NOT A DISPUTE column, all customer harm:* telling a customer with a real billing error that it isn't one strips a legal protection. It's the worst common mistake.
  - The idea of pricing each error by who gets hurt comes from Steve Yegge's essay "The Counting House" (https://yegge.ai/essays/the-counting-house/). The grid applies it to Reg Z card disputes.
- **Grounding check.** Every fact in the note and payload must appear in the transcript. A single invented fact fails the note outright, whatever else it gets right.
- **Note scoring.** Notes are hand-scored by the author (12). An LLM judge was planned and not built.

## Results (holdout)

**12 cases is a smoke signal, not a benchmark.** Two cases per class can't separate a good classifier from a lucky one. The holdout is there to catch overfitting to the 28 tune cases, not to make a performance claim.

| Measure | Holdout |
|---|---|
| Intent correct, by class (NR, WA, UN, CNP, NAD, ESC) | [2 of 2 each](results/holdout/report.md#3-per-class) |
| UN caught | [2 of 2](results/holdout/report.md#4-8-headline-counts) |
| Disputes caught (not predicted NAD) | [8 of 8](results/holdout/report.md#4-8-headline-counts) |
| Temp-credit precision | [3 of 3 predicted true](results/holdout/report.md#4-8-headline-counts) |
| Escalations on clear cases | [0 (2 predicted ESC)](results/holdout/report.md#4-8-headline-counts) |
| Next action | [12 of 12](results/holdout/report.md#4-8-headline-counts) |
| Gold fields: amount_disputed, within_60_days, temp_credit_eligible, notice_link_sent | [12 of 12 each](results/holdout/report.md#9-gold-fields) |
| Cost-weighted errors | [$0](results/holdout/report.md#2-cost-weighted-errors-illustrative-c5-h50-x500) |
| **Policy-id recall, all expected ids present** | [**2 of 12**](results/holdout/report.md#12-policy-id-recall-report-only) |
| Cost / latency | [$0.0018 / 9.4 s per case](results/holdout/report.md#11-cost-and-latency) |

| Note rubric (hand-scored) | Yes |
|---|---|
| Complete | [12/12](results/holdout/note_scores.md) |
| Correct next step | [12/12](results/holdout/note_scores.md) |
| Grounded | [12/12](results/holdout/note_scores.md) |
| Usable handoff | [10/12](results/holdout/note_scores.md#usable-handoff-n) (T30, T37) |

- **Tune vs. holdout.** Tune run A ([report](results/tune-A/report.md)) scored the same as the holdout on its 21 clean cases: intent 21 of 21, UN 4 of 4, disputes 16 of 16. Next action and gold fields were 20 of 20 (T38 is scored on intent only). That means no sign of overfitting. It also means both sets are at the ceiling, and they can't show a gap even if one exists.
- **Few-shot.** 7 tune cases are few-shot examples in the classifier prompt (T03, T14, T17, T22, T29, T39, T40). They're excluded from tune scoring. None is in the holdout.
- **Blind relabel.** The author blind-relabeled 8 holdout cases (IDs not recorded): 6 matched, and T15 and T37 disagreed. Both disagreements sit on the UN boundary and were resolved in favor of the drafted label, per the spec.
- **The weak spot is retrieval, not classification.** The right decisions often cite the wrong basis. [`findings.md`](results/holdout/findings.md) lists the post-run review: wrong or missing citations on T08, T30 and T37, and notes that describe proposed actions as done.

## What I'd change next

- **The model classifies and extracts facts:** the intent plus the payload facts (merchant, dates, amounts, whether the customer contacted the merchant).
- **Rules pick the next action and policy basis**, keyed on intent and those facts, not on keyword retrieval. Next action was already 12 of 12. The gain is in the basis (policy-id recall 2 of 12) and in checks the pipeline skips today, like deriving `within_60_days` from dates and validating `temp_credit_eligible`. Judgment calls such as quality complaint vs. not (T31) move into fact extraction; they don't go away.
- **Retrieval only supplies supporting text for the note**, and the note cites only the ids the rules chose.
- **Write action definitions as proposals** ("propose opening a billing-error dispute"), so notes and payloads say what's proposed, not what's done.

## Errata

These corpus issues were found in a post-run review against the eCFR text (as of 2026-11-05). **The corpus is published as it ran. The corrections below haven't been evaluated.** Sources: [§ 1026.13](https://www.ecfr.gov/current/title-12/part-1026/section-1026.13) and [Supplement I to Part 1026](https://www.ecfr.gov/current/title-12/part-1026/appendix-Supplement%20I%20to%20Part%201026) (official commentary).

- **REG-01 vs REG-11 (contradiction).** REG-01 lists "a request for clarification or documentation" as a billing error, and REG-11 says a bare receipt request is not one. Under § 1026.13(a)(6), documentation counts only as part of a clarification request, and comment 13(a)(6)-1 excludes documentation requests made on their own. In the committed runs REG-11 was never retrieved, and T32 (a receipt request) cited REG-01.
- **REG-09 (overstated).** It says the cardholder never has to contact the merchant first. Comment 13(a)(3)-3 says that only for not-delivered or not-accepted claims under § 1026.13(a)(3).
- **REG-03 (unsourced sentence).** "A phone call alone does not trigger the statutory process" isn't in § 1026.13. It follows from the written-notice rule in § 1026.13(b), and the explicit source is comment 7(a)(9)-2.
- **REG-14 (partly sourced).** Its first two sentences match comment 13(c)-1, which is permissive ("may"). The third, "doesn't mean the issuer agrees an error occurred", comes from comment 13(c)-2, which covers correction without investigation. Giving temporary credit at phone intake is issuer practice (POL-02), not Reg Z.

## How to run

Requires Python 3.12. Tested on Windows. On macOS or Linux, use `.venv/bin/python`.

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.venv\Scripts\python.exe scripts\score.py --self-test   # no key needed
.venv\Scripts\python.exe review\server.py               # review screen over results/: http://127.0.0.1:8765/
```

A full run makes model calls and needs **your own OpenRouter API key**:

1. Copy `.env.example` to `.env` and uncomment `OPENROUTER_API_KEY=` with your key. Leave unused lines commented out: an empty `KEY=` overrides the defaults.
2. `.venv\Scripts\python.exe scripts\smoke_test.py` checks the key.
3. `.venv\Scripts\python.exe scripts\run_batch.py` runs the 28 tune cases into `runs/<timestamp>/` (about $0.04 and 3 minutes). Then score it with `scripts\score.py runs\<timestamp>`.

All model calls go through OpenRouter (`anthropic/claude-haiku-5.5` by default). `run_batch.py --holdout` exists, but the published holdout result is the single run above. A rerun is a new experiment, not a replication.

## Known limits

- **Small set.** 40 transcripts and 12 holdout cases, reported as counts, not percentages.
- **Synthetic transcripts** from one generator model. There's no human baseline, and real calls are messier.
- **Single model.** Classifier and note writer are the same model, and gold labels were drafted with help from a model of the same family, then reviewed by the author.
- **Keyword retrieval**, on purpose (no embeddings). It's the main suspect for the low policy-id recall above.
- One intent per call. Escalation reasons aren't scored. See [`data/labeling_notes.md`](data/labeling_notes.md) for the full list.

`CLAUDE.md` is the working agreement used with Claude Code while building this.

## License

MIT. See [LICENSE](LICENSE).

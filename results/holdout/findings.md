# Holdout findings

Findings from Tom's review of the holdout outputs, not scorer output.

## Right call, wrong or missing basis (3 cases)

- T08: the note cites POL-05 (correct). The payload policy_ids say REG-01. Note and record disagree.
- T30: cites REG-13 though no quality defect was reported. Same stray-snippet pattern as T01. Correct basis is REG-12 apparent authority, which wasn't cited.
- T37: POL-06 names business accounts and was never retrieved. The escalation is right for a reason the record doesn't contain.

## Usable handoff (2 cases, matches note_scores.md)

- T30: the note doesn't say what the customer was told.
- T37: the note doesn't say it's a business account.

## Other findings

- The notes describe proposed actions as done ("dispute opened", notice_link_sent: true). An agent override makes the note false. The review screen's stale-note banner addresses this.
- within_60_days is marked unknown on T10, T15, T18, though the transaction was 13-18 days before the call. A rule could derive it.
- amount_posted on duplicate charges: T08 records one charge, T10 records the sum. The spec doesn't define which.
- The intent enum is copied in scripts/score.py and scripts/make_split.py as well as backend/main.py. Drift risk. Not fixed (frozen code).
- temp_credit_eligible is never validated by the pipeline.
- T31 gold label in doubt: "uncomfortable after a month" may be NAD with RESOLVE_ON_CALL, not CLAIMS_DEFENSES. Not rescored. Also, the note includes a back-pain detail it doesn't need.

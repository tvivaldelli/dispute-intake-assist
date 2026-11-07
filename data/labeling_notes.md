# Labeling notes

Rules, set before labeling:
1. Gold means what the transcript supports, not what the manifest knows. Facts not said aloud are unknown.
2. temp_credit_eligible: false when the amount is unknown. n/a for UN, NAD, ESC, and CNP inside the wait period.
3. T38 (two clear issues, one intent per call): accepted answers are ESC LOW_CONFIDENCE, or WA or NR if the after-call note names the other issue. T38 is scored on intent only. Its row carries the ESC values (amount n/a, temp credit n/a, notice link false, SUPERVISOR) and is excluded from gold-field scoring.
4. Precedence: signs of unauthorized use plus a vulnerable caller label as UN (spec section 1).
5. expected_next_action uses one of the next-action codes defined in spec section 2:
   - OPEN_DISPUTE (billing-error dispute opened, notice link sent)
   - FRAUD_TRANSFER (UN, POL-01)
   - CNP_WAIT (inside the POL-03 wait: set expectation, schedule follow-up)
   - RESOLVE_ON_CALL (NAD: explain descriptor or provide documentation)
   - CLAIMS_DEFENSES (NAD quality complaint, REG-13 path)
   - SUPERVISOR (ESC)
   - CHARGEBACK_REVIEW (outside the 60-day window, POL-05)
6. gold_amount_disputed: the amount the customer contests (for WA, the difference only). n/a when no dispute or fraud claim is opened. unknown when not said.
7. gold_within_60_days: call date is Oct 15, 2026. A statement dated Aug 16, 2026 or later is true; earlier is false; unknown if the statement date isn't said. If the transcript says the charge has not appeared on a statement yet, within_60_days is true: the window has not started.
8. gold_temp_credit_eligible: true if a billing dispute is opened and the amount is under $250. false if $250 or more, or unknown. n/a for UN, NAD, ESC, and CNP inside the wait. CHARGEBACK_REVIEW is not an opened billing-error dispute: temp credit n/a, notice link false. n/a takes precedence: check intent and next action first, amount second.
9. gold_notice_link_sent: true when a billing-error dispute is opened, false otherwise. CHARGEBACK_REVIEW is not an opened billing-error dispute: temp credit n/a, notice link false.
10. expected_policy_ids: 1 to 3, separated by semicolons, e.g. REG-02;POL-04.

Read before labeling (spot checks, not blind): T02, T08, T15, T21, T30, T36, T38, T40.

Honest limits, running list:
- Synthetic transcripts, one generator model. No human baseline.
- One intent per call. A real system would split T38 into two disputes.
- CUSTOMER_RISK has no clean case. The one generated became a fraud case under the precedence rule.
- Generator leaked day counts in 10 cases. Caught before labeling and regenerated (344d064).
- T38 excluded from gold-field scoring: one row can't hold three accepted answers.
- Intent for T01–T10 labeled by me; remaining labels and all gold fields drafted by Claude (same family as the classifier, had seen the generator's scenario seeds), reviewed and corrected by me.
- Holdout blind relabel (Oct 28): 6 of 8 intents matched the drafted labels. Both disagreements (T15, T37) were resolved in favor of the drafted label per the spec. Both sit on the UN boundary.
- Two tune runs, same prompts: 0 of 28 intent or next_action changes. Note wording varied between runs.
- Holdout run once at 21c7a93, prompts frozen at 9f64749. No changes after seeing it.
- Policy-id recall: 6 of 20 tune, 2 of 12 holdout. Retrieval not fixed after the holdout run.
- escalate_reason is not scored. Pronoun flags are not yet checked for who they refer to.

## Review of Claude draft
- My first pass covered intent and next action for T01 to T10. Claude completed the gold fields and corrected two of my rows: T06 (NAD to NR, REG-08 covers late delivery) and T08 (OPEN_DISPUTE to CHARGEBACK_REVIEW, statement before the Aug 16 cutoff).
- I reviewed all 40 rows. Flag decisions: T14 WA, T20 within_60_days true (not on a statement yet), T37 ESC SOP_GAP, T39 ESC LOW_CONFIDENCE.
- Overrides of Claude draft: none.

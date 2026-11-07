# Dispute Intake Assist: Spec v0 (draft for Tom's review)

Scope: card billing-dispute intake calls. Synthetic data only. Regulation snippets paraphrase public Reg Z (12 CFR 1026.12 and 1026.13). Issuer policy snippets (POL-*) are invented for this prototype and labeled that way everywhere.

Before publishing: check every REG-* snippet against the current CFR text. REG-07, REG-12, and REG-13 were checked against Reg Z on Oct 28, 2026.

---

## 1. Intent taxonomy

| ID | Intent | Definition | Correct next action |
|---|---|---|---|
| NR | Not received / not as agreed | Customer was charged for goods or services that never arrived, or arrived not as agreed: wrong item, wrong quantity, late, wrong place. Not a quality complaint about something they accepted. | Open billing-error dispute. Capture merchant, amount, expected delivery date, whether customer contacted merchant. Send notice link (POL-04). |
| WA | Wrong amount | Customer made the purchase, but the posted amount differs from what they agreed to: duplicate charge, overcharge, altered tip. | Open billing-error dispute for the difference only. Capture agreed amount and posted amount. Send notice link (POL-04). |
| UN | Unauthorized | Customer says they did not make or authorize the charge. For charges made by someone else, including a family member, apply the UN labeling rule below. | Transfer to fraud on the same call: block card, reissue, open fraud claim. Do not open as a billing dispute only. |
| CNP | Merchant credit not posted | Merchant promised a refund or credit (return accepted, cancellation, adjustment) that hasn't shown up. | Check credit date against POL-03. Inside the wait period: set expectation and schedule follow-up. Past it, or a statement closed without the credit: open billing-error dispute and send notice link (POL-04). |
| NAD | Not a dispute | No billing error. Examples: customer doesn't recognize the merchant name but made the purchase; quality complaint on goods they accepted; request for a receipt with no claimed error; a charge made by someone the cardholder gave the card or permission to use. | Resolve on the call (explain the descriptor, provide documentation) or route quality complaints to the claims-and-defenses path (REG-13). No dispute opened. |
| ESC | Escalate | Model declines to classify and hands to a human. | Route to supervisor queue with reason code and notes so far. |

UN labeling rule: label UN when the cardholder says they did not make or authorize the charge, including when a family member made it. Apparent authority is decided later under state law (REG-12), not at intake, and POL-01 routes these to fraud. Label NAD only when the transcript shows the cardholder gave that person the card or permission to use it.

Escalate reason codes:
- `SOP_GAP`: the case isn't covered by policy (business card, deceased cardholder, third-party caller without authorization).
- `LOW_CONFIDENCE`: signals point to two intents and the transcript doesn't settle it.
- `CUSTOMER_RISK`: abusive caller, or a customer who sounds confused or vulnerable.

Precedence: when a transcript shows signs of unauthorized use and a confused or vulnerable caller, UN takes precedence over ESC CUSTOMER_RISK. Route to fraud and note the vulnerability in the after-call note so the next agent handles the call with care. Record what was observed, not a guess at a cause. Fine: "caller repeated herself and said a third party had remote access to her computer." Not fine: "caller seems to have memory problems."

Fraud signals take precedence over CUSTOMER_RISK. They do not override SOP_GAP.

Hard cases to include in the transcript set (these are where the eval earns its keep):
- Family member used the card (UN vs NAD). Label by the UN labeling rule above.
- Unrecognized merchant descriptor that turns out to be a real purchase (UN vs NAD).
- Item arrived broken vs item arrived and customer dislikes it (NR vs NAD).
- Returned item, refund promised, nothing posted (CNP vs NR).
- Customer calling around day 55 to 60 after the statement (window flag).
- Customer raises two issues in one call (ESC LOW_CONFIDENCE, or pick the primary and flag the second).
- Vulnerable caller with signs of unauthorized use (UN vs ESC CUSTOMER_RISK). Label by the precedence rule.

## 2. Write-intent payload (what the model proposes, never executes)

```json
{
  "intent": "NR | WA | UN | CNP | NAD | ESC",
  "escalate_reason": "SOP_GAP | LOW_CONFIDENCE | CUSTOMER_RISK | null",
  "merchant": "string",
  "transaction_date": "YYYY-MM-DD | unknown",
  "statement_date": "YYYY-MM-DD | unknown",
  "amount_posted": "number | unknown",
  "amount_disputed": "number | unknown | n/a",
  "customer_contacted_merchant": "true | false | unknown",
  "within_60_days": "true | false | unknown",
  "notice_link_sent": "true | false",
  "written_notice_received": "true | false | unknown",
  "temp_credit_eligible": "true | false | n/a",
  "next_action": "OPEN_DISPUTE | FRAUD_TRANSFER | CNP_WAIT | RESOLVE_ON_CALL | CLAIMS_DEFENSES | SUPERVISOR | CHARGEBACK_REVIEW",
  "policy_ids": ["REG-02", "POL-02"]
}
```

Next-action codes:
- `OPEN_DISPUTE`: billing-error dispute opened, notice link sent.
- `FRAUD_TRANSFER`: UN, POL-01.
- `CNP_WAIT`: inside the POL-03 wait: set expectation, schedule follow-up.
- `RESOLVE_ON_CALL`: NAD: explain descriptor or provide documentation.
- `CLAIMS_DEFENSES`: NAD quality complaint, REG-13 path.
- `SUPERVISOR`: ESC.
- `CHARGEBACK_REVIEW`: outside the 60-day window, POL-05.

Rule: any field the transcript doesn't support is `unknown`. Never inferred.

Classifier input: the transcript plus the call date from call metadata. `within_60_days` is computed from the call date and the statement date when the transcript gives the statement date, and is `unknown` otherwise. If the transcript says the charge has not appeared on a statement yet, within_60_days is true: the window has not started.

## 3. Policy corpus (20 snippets)

Regulation paraphrases (public):

- **REG-01 What counts as a billing error.** A charge the cardholder didn't authorize; a charge that isn't identified properly; goods or services not accepted or not delivered as agreed; a payment or credit not posted properly; a computational error by the issuer; a request for clarification or documentation about a charge; failure to send a statement to the last known address.
- **REG-02 The 60-day window.** The issuer must receive the notice within 60 days after it sent the first statement showing the error. If a statement wasn't sent, the clock runs from when it should have been. For a missing credit, it runs from the statement where the credit should have appeared.
- **REG-03 Notice must be in writing.** A billing-error notice is written. Electronic notice counts if the issuer says in its billing rights statement that it accepts electronic notices and how to send them. A phone call alone does not trigger the statutory process.
- **REG-04 What the notice must contain.** Enough to identify the cardholder and account, the cardholder's belief that an error exists and why, and to the extent possible the type, date, and amount of the error.
- **REG-05 Acknowledgment.** The issuer must send written acknowledgment within 30 days of receiving the notice, unless it resolves the error within that time.
- **REG-06 Resolution deadline.** The issuer must resolve the error within two complete billing cycles after receiving the notice, and no later than 90 days.
- **REG-07 While the dispute is open.** The issuer can't collect the disputed amount or related finance charges, can't report them as delinquent, and can't accelerate the debt or restrict the account because the cardholder used these rights. The issuer can still collect the undisputed balance, report the account as "in dispute," and hold the disputed amount against the credit limit.
- **REG-08 Not delivered as agreed.** Includes refusing delivery of nonconforming goods, delivery of something different from what was agreed, wrong quantity, late delivery, and delivery to the wrong place. Does not cover the quality of goods or services the cardholder accepted.
- **REG-09 No need to contact the merchant first.** The cardholder does not have to try to resolve it with the merchant before sending a billing-error notice.
- **REG-10 Missing payment or credit.** Failure to post a payment or other credit issued to the account is a billing error.
- **REG-11 Documentation requests.** A request for a receipt or sales slip, without claiming an error or asking for clarification of a charge, does not start the billing-error process.
- **REG-12 Unauthorized use.** A charge is unauthorized if someone other than the cardholder made it without actual, implied, or apparent authority, and the cardholder got no benefit from it. State law decides authority. Cardholder liability is capped at the lesser of $50 or the charges made before they notified the issuer. Notice of unauthorized use can be by phone or in writing.
- **REG-13 Quality disputes (claims and defenses).** A complaint about the quality of goods the cardholder accepted isn't a billing error. It may qualify as a claim against the issuer if the cardholder tried in good faith to resolve it with the merchant, the purchase was over $50, and it happened in the cardholder's state or within 100 miles of their address. The $50 and location limits don't apply when the merchant and issuer are related.
- **REG-14 Temporary correction.** The issuer may temporarily credit the account while it investigates. It still has to complete the process on time. A temporary credit doesn't mean the issuer agrees an error occurred.

Issuer policy (synthetic, for this prototype only):

- **POL-01 Fraud routing.** Any charge the cardholder says they didn't make or authorize goes to the fraud team on the same call. Block the card, reissue, open a fraud claim. Agents do not open these as billing disputes only.
- **POL-02 Temporary credit.** Open billing-error disputes under $250 get temporary credit at intake. $250 and over go to dispute review before any credit.
- **POL-03 Merchant credit wait period.** If the merchant's credit or refund is dated less than 10 business days ago, set the expectation and schedule a follow-up. If it's older, or a statement closed without it, open a billing-error dispute.
- **POL-04 Written notice link.** After a billing-error intake by phone, send the cardholder a link the same day to submit or confirm the dispute electronically. The cardholder's submission is the written notice under REG-03. The call alone is not. POL-04 does not apply to UN, because notice of unauthorized use can be by phone (REG-12).
- **POL-05 Outside the window.** If the 60-day window has passed, still log the claim and route to network chargeback review. Don't promise statutory protections.
- **POL-06 Escalation.** Business accounts, deceased cardholders, third-party callers without authorization on file, and abusive callers go to a supervisor with a reason code.

## 4. Cost grid (actual intent by row, predicted intent by column)

Tiers:
- **C, cheap:** stays in the right workflow with the wrong reason code. Rework.
- **H, company harm:** money moves or cost is incurred that shouldn't be. Needless reissue, temporary credit on a valid charge, chargeback fees.
- **X, customer harm:** the customer loses a protection or keeps getting hit. Regulatory exposure.

| Actual \ Predicted | NR | WA | UN | CNP | NAD |
|---|---|---|---|---|---|
| **NR** | ok | C | H | C | X |
| **WA** | C | ok | H | C | X |
| **UN** | X | X | ok | X | X |
| **CNP** | C | C | H | ok | X |
| **NAD** | H | H | H | H | ok |

Illustrative costs for the note (finance would set real ones): C about $5 in rework, H about $25 to $75, X $500 or more plus regulatory exposure.

Reading the grid:
- **UN row is all X.** Missed fraud means more charges land. Optimize UNAUTHORIZED for recall. Target close to 100 percent. Over-routing a real purchase to fraud costs a reissue (H), which is acceptable.
- **NAD column is all X.** Telling a customer with a real billing error that it isn't one is the worst common mistake. Optimize recall on "is this a dispute at all."
- **NAD row is all H.** Opening a dispute on a valid charge can trigger temporary credit under POL-02. Watch precision on the dispute classes, especially for amounts under $250.
- Mixups among NR, WA, and CNP are mostly cheap. Don't spend tuning time there.
- ESC sits outside the grid. Report escalation rate, and how many escalations were on clear cases (cheap but wasteful).

## 5. After-call note rubric

Four yes/no questions, scored per case. Report each rate separately.

1. **Complete.** Every required field for the intent is present or marked unknown.
2. **Correct next step.** The note states the next action that matches policy for the intent.
3. **Grounded.** Every fact in the note and payload appears in the transcript. Nothing invented. Any "no" here fails the case outright.
4. **Usable handoff.** A second agent could pick up the case from the note alone, without the transcript. Plain language, no speculation about the customer.

Judge calibration: Tom scores 10 notes first. The judge scores the same 10. Report agreement on each question.

Judge model: the LLM judge uses a third model family, different from the classifier (anthropic/claude-haiku-5.5) and from the transcript generator (section 6). Model: TBD.

## 6. Labeling plan

- 40 transcripts: 7 each for NR, WA, UN, CNP, NAD (35), plus 5 ESC.
- Transcripts are generated by a different model family than the classifier (anthropic/claude-haiku-5.5). Generator model: TBD.
- Each transcript is seeded with a target label. Tom then reads it and confirms or changes the label. Every changed label is logged with a one-line reason.
- At least 2 hard cases per class from the list in section 1.
- Each labeled with: intent, escalate reason (if any), expected policy IDs (1 to 3), expected next action, gold values for four payload fields: amount_disputed, within_60_days, temp_credit_eligible, notice_link_sent. These are the fields where money moves or a protection depends on the answer. The other payload fields are scored through the rubric (complete and grounded), not against gold.
- Split before writing any prompt: 28 tune, 12 holdout, stratified with 2 per class in holdout, including ESC.
- The holdout is a leakage check, run once at the end. It is not a performance claim.
- Report per-class results as counts (for example, "UN recall 7 of 7"), not percentages.

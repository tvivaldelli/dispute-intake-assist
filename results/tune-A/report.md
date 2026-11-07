# Score: 20261028-170724

Clean cases: 21 (few-shot excluded: T03, T14, T17, T22, T29, T39, T40)
Gold-field cases: 20 (T38 scored on intent only)

## 1. Intent confusion (actual rows, predicted columns)

| actual \ predicted | NR | WA | UN | CNP | NAD | ESC | total |
|---|---|---|---|---|---|---|---|
| **NR** | 4 | 0 | 0 | 0 | 0 | 0 | 4 |
| **WA** | 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| **UN** | 0 | 0 | 4 | 0 | 0 | 0 | 4 |
| **CNP** | 0 | 0 | 0 | 4 | 0 | 0 | 4 |
| **NAD** | 0 | 0 | 0 | 0 | 4 | 0 | 4 |
| **ESC** | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

## 2. Cost-weighted errors (illustrative: C=$5, H=$50, X=$500)

C: 0, H: 0, X: 0, n/a (ESC, outside the grid): 0
Total: $0

## 3. Per class

| class | cases | correct |
|---|---|---|
| NR | 4 | 4 |
| WA | 4 | 4 |
| UN | 4 | 4 |
| CNP | 4 | 4 |
| NAD | 4 | 4 |
| ESC | 1 | 1 |

## 4-8. Headline counts

- UN caught: 4 of 4
- Disputes caught (NR/WA/UN/CNP not predicted NAD): 16 of 16
- Temp-credit precision: 4 of 4 predicted true
- Escalations: 1 predicted ESC, 0 on clear cases (gold not ESC)
- Next action: 20 of 20

## 9. Gold fields

| field | matches |
|---|---|
| amount_disputed | 20 of 20 |
| within_60_days | 20 of 20 |
| temp_credit_eligible | 20 of 20 |
| notice_link_sent | 20 of 20 |

## 10. Checks fired

- gendered pronoun in note: 2

## 11. Cost and latency

- Cost: $0.0364 total, $0.0017 per case
- Latency: 186.7s total, 8.9s per case

## 12. Policy-id recall (report only)

All expected ids present: 6 of 20

| id | expected | predicted | found |
|---|---|---|---|
| T01 | REG-08, POL-04, POL-02 | POL-04, REG-08 | 2 of 3 |
| T02 | REG-08, REG-02, POL-04 | POL-04, REG-08 | 2 of 3 |
| T04 | REG-08, POL-04 | POL-04, REG-08 | 2 of 2 |
| T06 | REG-08, POL-04, POL-02 | POL-04, REG-08 | 2 of 3 |
| T09 | REG-01, POL-04, POL-02 | POL-04 | 1 of 3 |
| T11 | REG-01, POL-04 | POL-04 | 1 of 2 |
| T12 | REG-01, POL-04 | REG-01, POL-04 | 2 of 2 |
| T13 | REG-01, POL-04, POL-02 | POL-04, REG-01 | 2 of 3 |
| T16 | REG-12, POL-01 | POL-01, REG-12 | 2 of 2 |
| T19 | REG-12, POL-01 | POL-01, REG-01 | 1 of 2 |
| T20 | REG-12, POL-01 | POL-01, REG-12 | 2 of 2 |
| T21 | REG-12, POL-01 | POL-01, REG-12 | 2 of 2 |
| T23 | REG-10, POL-03 | POL-03, REG-01 | 1 of 2 |
| T24 | REG-10, POL-03, POL-04 | POL-03, POL-04, REG-02 | 2 of 3 |
| T27 | REG-10, POL-03 | POL-03 | 1 of 2 |
| T28 | REG-10, POL-03, POL-04 | POL-03, POL-04, REG-07 | 2 of 3 |
| T32 | REG-11 | REG-01 | 0 of 1 |
| T33 | REG-13, REG-08 | REG-13, REG-01 | 1 of 2 |
| T34 | REG-01 | REG-01, REG-13 | 1 of 1 |
| T35 | REG-13, REG-08 | REG-13 | 1 of 2 |

## Misses

none

## Policy-id misses

| id | missing | predicted |
|---|---|---|
| T01 | POL-02 | POL-04, REG-08 |
| T02 | REG-02 | POL-04, REG-08 |
| T06 | POL-02 | POL-04, REG-08 |
| T09 | REG-01, POL-02 | POL-04 |
| T11 | REG-01 | POL-04 |
| T13 | POL-02 | POL-04, REG-01 |
| T19 | REG-12 | POL-01, REG-01 |
| T23 | REG-10 | POL-03, REG-01 |
| T24 | REG-10 | POL-03, POL-04, REG-02 |
| T27 | REG-10 | POL-03 |
| T28 | REG-10 | POL-03, POL-04, REG-07 |
| T32 | REG-11 | REG-01 |
| T33 | REG-08 | REG-13, REG-01 |
| T35 | REG-08 | REG-13 |

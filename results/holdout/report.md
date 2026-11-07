# Score: 20261028-173014

Clean cases: 12 (few-shot excluded: none)
Gold-field cases: 12 (none scored on intent only)

## 1. Intent confusion (actual rows, predicted columns)

| actual \ predicted | NR | WA | UN | CNP | NAD | ESC | total |
|---|---|---|---|---|---|---|---|
| **NR** | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| **WA** | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| **UN** | 0 | 0 | 2 | 0 | 0 | 0 | 2 |
| **CNP** | 0 | 0 | 0 | 2 | 0 | 0 | 2 |
| **NAD** | 0 | 0 | 0 | 0 | 2 | 0 | 2 |
| **ESC** | 0 | 0 | 0 | 0 | 0 | 2 | 2 |

## 2. Cost-weighted errors (illustrative: C=$5, H=$50, X=$500)

C: 0, H: 0, X: 0, n/a (ESC, outside the grid): 0
Total: $0

## 3. Per class

| class | cases | correct |
|---|---|---|
| NR | 2 | 2 |
| WA | 2 | 2 |
| UN | 2 | 2 |
| CNP | 2 | 2 |
| NAD | 2 | 2 |
| ESC | 2 | 2 |

## 4-8. Headline counts

- UN caught: 2 of 2
- Disputes caught (NR/WA/UN/CNP not predicted NAD): 8 of 8
- Temp-credit precision: 3 of 3 predicted true
- Escalations: 2 predicted ESC, 0 on clear cases (gold not ESC)
- Next action: 12 of 12

## 9. Gold fields

| field | matches |
|---|---|
| amount_disputed | 12 of 12 |
| within_60_days | 12 of 12 |
| temp_credit_eligible | 12 of 12 |
| notice_link_sent | 12 of 12 |

## 10. Checks fired

- gendered pronoun in note: 3

## 11. Cost and latency

- Cost: $0.0215 total, $0.0018 per case
- Latency: 113.1s total, 9.4s per case

## 12. Policy-id recall (report only)

All expected ids present: 2 of 12

| id | expected | predicted | found |
|---|---|---|---|
| T05 | REG-08, POL-04, POL-02 | POL-04, REG-08 | 2 of 3 |
| T07 | REG-08, POL-04 | POL-04, REG-08 | 2 of 2 |
| T08 | REG-02, POL-05 | REG-01 | 0 of 2 |
| T10 | REG-01, POL-04, POL-02 | POL-04, REG-01 | 2 of 3 |
| T15 | REG-12, POL-01 | POL-01, REG-12 | 2 of 2 |
| T18 | REG-12, POL-01 | POL-01 | 1 of 2 |
| T25 | REG-10, POL-03, POL-04 | POL-03, POL-04 | 2 of 3 |
| T26 | REG-10, POL-03, POL-04 | POL-03, POL-04 | 2 of 3 |
| T30 | REG-12 | REG-01, REG-13 | 0 of 1 |
| T31 | REG-13, REG-08 | REG-13 | 1 of 2 |
| T36 | POL-06, REG-12 | POL-06, POL-01 | 1 of 2 |
| T37 | POL-06, REG-12 | POL-01, REG-01 | 0 of 2 |

## Misses

none

## Policy-id misses

| id | missing | predicted |
|---|---|---|
| T05 | POL-02 | POL-04, REG-08 |
| T08 | REG-02, POL-05 | REG-01 |
| T10 | POL-02 | POL-04, REG-01 |
| T18 | REG-12 | POL-01 |
| T25 | REG-10 | POL-03, POL-04 |
| T26 | REG-10 | POL-03, POL-04 |
| T30 | REG-12 | REG-01, REG-13 |
| T31 | REG-08 | REG-13 |
| T36 | REG-12 | POL-06, POL-01 |
| T37 | POL-06, REG-12 | POL-01, REG-01 |

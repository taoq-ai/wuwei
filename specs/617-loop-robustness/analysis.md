# Specification Analysis Report: 617-loop-robustness

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 5.5 (steward), 5.6 (outcome metrics) and 5.11 (tracker), issue #617 and the
code on `main` at 082e1c6 (v0.23.0 plus #602).

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Fail closed | HIGH | spec FR-003, constitution II | Catching a tracker failure per ticket could turn an adapter defect into a quiet partial metric. | Resolved: only a lookup that could not run (exit nonzero or an error-shaped body, the `_Unavailable` raised by `_port`) is caught, and it is named with its reason under `lead_time.unmeasured`; malformed data still raises `ADAPTER_DATA`; no reading at all stays `unmeasured`, never zero (T005). |
| A2 | Security | HIGH | spec FR-002, constitution VII, #602 | Putting GitHub's error message into a reason adds provider text to stderr, doctor and the report. | Resolved: only the first GraphQL `errors[].message`, collapsed to one line, through `redact.redact` (known credential values and secret patterns) and cut at 160 characters; gh stderr and HTTP error bodies stay out; the gh test keeps a private marker in stderr and asserts it is absent (T003). |
| A3 | Correctness | MEDIUM | plan `steward.review` | Dropping `metrics.collect` from `review` also drops its incidental validation (traces, transcripts, adapters) on the gate path. | Accepted: that validation belongs to `metrics` and `steward run`, which still collect; the gate path only needs fix rounds (SC-001). |
| A4 | Coverage | MEDIUM | FR-001 | A balance test on recorded queries covers only what the port contract sends. | Resolved: the contract exercises all seven operations on both transports, plus the board and close transitions already tested; the checker also runs on Linear's GraphQL. |
| A5 | Behaviour | MEDIUM | FR-005 | Hiding the due row while a steward runs could lose a review. | Resolved: the due flag is not cleared; it stays until the next `steward.run`, so the row returns when the seat stops (T009). |
| A6 | Behaviour | LOW | FR-005 | Older unlaunched briefs stay on disk. | Accepted: they are records of what was due; never launched. |
| A7 | Scope | LOW | spec Assumptions | A ticket with no In Progress entry still makes `lead_time` unmeasured. | Accepted: not a lookup failure; out of the request. |
| A8 | Invariants | LOW | design 9.2 | No guard or decision rule changes. | No 9.2 row. |

No CRITICAL finding. HIGH findings A1 and A2 are resolved above.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T002 |
| FR-002 | T003, T004 |
| FR-003 | T005, T006 |
| FR-004 | T007, T008 |
| FR-005 | T009, T010 |
| FR-006 | T011, T012 |

# Specification analysis: canary-guard

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | MEDIUM | spec.md How this fails 2 | `sed -i.bak` passes for the canary, as it does for the ledger at main | Out of this item's lines: #1288 rewrites the sed writer test and closes it for both; recorded in the PR |
| A2 | Coverage | LOW | spec.md Clarifications | `guards.leak` still reads the canary strictly, so a broken canary still shuts network calls | Held by the promise's scope (hook.py) and the brief (guards.py: the ledger door's path list); follow-up candidate |
| A3 | Inconsistency | LOW | plan.md Constitution Check | Runtime +6 against the item's budget of 3 | Recorded in the spec and PR under Size; the total stays far below 4,000 |
| A4 | Ambiguity | LOW | spec.md | Acceptance 2 lists `%xx`, which sh never decodes | Resolved in Clarifications: the probe input keeps the escape in a folder that `..` leaves; the encoded name passes for both files |
| A5 | Coverage | LOW | tasks.md | The brief adds `sudo -D` to acceptance 2's wrappers | Covered in T003 and the probe |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 the reader never raises | yes | T001, T002, T006 | test_ledger covers missing, folder, FIFO, blank, text |
| FR-002 every hook read goes through it | yes | T007, T013 | a mutant per site |
| FR-003 the canary on the ledger door | yes | T003, T008, T012 | |
| FR-004 only the new canary routes move | yes | T011 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first.

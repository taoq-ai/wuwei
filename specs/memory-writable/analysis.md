# Specification analysis: memory-writable

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | HIGH (closed) | spec.md How this fails 1 | A link staged in memory by ln, mv, cp or python and followed in the same Bash call passes if every writer gets the memory pass | Resolved: only tee, sed, truncate, rm and redirects get it; tests T004, mutant "keep for every writer", probe mutant with 236 holes |
| A2 | Coverage | HIGH (closed) | spec.md How this fails 2 | A working directory in or below memory lets a relative write climb out to a transcript | Resolved: the hold never takes the pass; tests T004, mutants "held with keep" and "cd with keep" |
| A3 | Inconsistency | LOW | spec.md, promise | The promise says "every spelling records() reads"; globs, braces and `%` stay refused for memory | Recorded as an assumption: those spellings fail closed, and the refusal names the routes that pass |
| A4 | Coverage | LOW | spec.md Assumptions | A hard link from a memory file to a transcript, made outside the guards' sight | Residual risk, listed in SECURITY.md with the symlinks already there |
| A5 | Inconsistency | LOW | spec.md How this fails 3 | The guard expands `~` with the hook's HOME; a command that sets HOME first could differ | Residual risk, needs a link staged outside the guards' sight; listed in SECURITY.md |
| C1 | Coverage | LOW | tasks.md | `cp`, `dd`, `chmod`, `shred` into memory are refused | Recorded as an assumption: the issue needs Edit and a Bash append, both pass |

No open finding above LOW. A1 and A2 were HIGH and are closed before the first gate round.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 harness keep | yes | T006 | |
| FR-002 Edit, redirect and writer words | yes | T001, T002, T007 | |
| FR-003 the hold never keeps | yes | T004 | |
| FR-004 refusal names the routes | yes | T008 | |
| FR-005 runtime budget | yes | T010 | tests/test_setup.py size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.

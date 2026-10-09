# Specification Analysis Report: 614-fix-round-fresh-launch

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 5.3, 5.10 and 9.2, issue #614 (the owner's report of 2026-10-09) and the code
on `main` at 082e1c6.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Security | HIGH | plan, `reserve` | Accepting a brief reuse without `resume` could let any used brief launch a second seat. | Resolved: the reuse binds only the pending continue of the brief's own stopped seat (builder: build `ready`, action `continue`, its `seat`; sentinel: `dispatch.delta_due`, the same rule `dispatch next` offers); every other reuse stays refused (US1.5, T001, T003 and the existing sentinel test). |
| A2 | Correctness | HIGH | plan, `build.stopped` | Dropping the recorded agent id lets a late stop of the replaced agent complete the fresh round. | Resolved: the bind keeps the replaced id and `stopped` ignores a stop from it (FR-003, US1.3, T001). |
| A3 | Correctness | MEDIUM | plan, `build.started` | The replaced agent's `completion` (index and hash of a line in its own transcript) can equal the fresh agent's last line in a synthetic transcript and silence its stop. | Resolved: the fresh bind drops `completion` with the agent id; the replay guard is the replaced id (A2). |
| A4 | Design contract | HIGH | design 5.3, step loop amendment, 9.2 | The design assumes the harness resumes an agent, and a changed guard rule adds a 9.2 row; the table is the owner's. | Resolved by raising: the spec's Design spec conflict section carries proposed text for both; the property is asserted in the feature's tests, not in `tests/test_invariants.py`, whose table check pins the design. |
| A5 | Single source | MEDIUM | `dispatch._seats`, `reserve` | Two copies of the delta-continue condition would drift. | Resolved: `dispatch.delta_due` is used by both (FR-002). |
| A6 | Usability | MEDIUM | specmode step text | `{item}` is lowercased in step commands while day state keys keep their case. | Resolved: the command matches the item case-insensitively when exactly one item matches. |
| A7 | Security | MEDIUM | `spec analysis` | A symlinked spec directory or `analysis.md` could redirect the write outside the worktree. | Resolved: both refused; the directory must resolve inside the worktree (US2.2, T007). |
| A8 | Guards | LOW | US2.3 | A guard could refuse the seat's Bash call (heredoc input, the CLI word). | Covered by T007 through the real PreToolUse hook. |
| A9 | Latency | LOW | `reserve` | Importing `dispatch` on the hook path costs time (#346). | Imported lazily, only for a brief reuse without `resume` by a non-builder. |

No CRITICAL finding. HIGH findings A1, A2 and A4 are resolved above.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001 to T004 |
| FR-002 | T003, T004 |
| FR-003 | T001, T002 |
| FR-004 | T001, T003 |
| FR-005 | T005, T006 |
| FR-006 | T007, T008 |
| FR-007 | T007, T008 |

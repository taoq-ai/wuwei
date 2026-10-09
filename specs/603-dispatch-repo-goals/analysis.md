# Specification Analysis Report: 603-dispatch-repo-goals

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md`, the
item (#603) and its Acceptance section. Read-only pass; the resolutions below were applied
to the artifacts after the pass.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Constitution (IV, test first) | HIGH | tasks.md, first draft | The fresh-day walk test (goals), the park exit test and the multi-repository walk were ordered after their implementation tasks. | Resolved: tasks reordered; T001 and T002 precede T003, T004 and T005 precede T006, every test task now comes before its implementation task. |
| A2 | Inconsistency | HIGH | spec.md, plan.md line references | `_start` line range and the `launch_set` lines were off by one to two lines against `main`. | Resolved: verified with grep (`dispatch.py:399-409`, `:402-404`, `:329`, `:393`; `test_plan.py:280`). |
| A3 | Coverage | MEDIUM | tasks.md T005 | The two-repository walk needs the second repository's directory and interview answers, or a setup card or config warning can stop the walk before dispatch. | Resolved: T005 names both fixture steps. |
| A4 | Deviation from the item | MEDIUM | spec.md, Design decision | The item offers two fixes for defect 2 (goals edit before approve, or approve records the goals); the spec picks a third (approve reads the day's draft). | Accepted: each listed option breaks a rule (the gate allowance refuses an early `goals edit`; approve writing memory bypasses strict); the third is the shorter diff, adds no prompt and meets the Acceptance scenario. Rationale recorded in spec.md. |
| A5 | Ambiguity | MEDIUM | spec.md FR-006 | The unresolved-repository start parks an item the owner approved; for `plan add` and imported items without a worktree in a multi-repository workspace this is the only path. | Accepted: the park is a two-way seat record and lets the day close; a refused or waiting entry would hold the close. `plan add --repo` is listed under Deferred for a follow-up issue. |
| A6 | Acceptance wording | MEDIUM | spec.md US1 scenario 6 | Remediation reasons (for example `dispatch.py:543`) name `bin/wuwei worktree add {item}` without `--repo`; the Acceptance asks every `worktree add` command `next` returns to carry `--repo`. | Accepted: those are reason texts, not returned commands; the `worktree add` fallback (FR-007) makes them exit 0 whenever the proposal names the repository, without editing eight messages. Returned start commands carry `--repo` (FR-001). |
| A7 | Constitution (VII) | LOW | spec.md Edge Cases | Under strict, approve now passes on the gate-confirmed draft before the owner records memory. | Accepted: approve never writes owner memory; `goals edit` stays the owner's under strict; no guard changes. |
| A8 | Underspecification | LOW | plan.md section 4 | Derivation stats lead-supplied paths (`..` or absolute paths could match). | Accepted: existence only, never read; it can only pick among configured repositories, and several matches leave it unresolved. |
| A9 | Duplication | LOW | plan.md sections 2 and 3 | `_start` passes `--repo` and `worktree add` also falls back to the proposal row. | Accepted: the Acceptance requires `--repo` in the returned command; the fallback is the one shared spot that fixes the sibling remediation lines. Both read one helper, `dispatch.candidate`. |
| A10 | Parallel work | LOW | plan.md section 7 | #599, #600 and #601 also add 9.2 rows and `tests/test_invariants.py` checks; ids I26 and I27 may collide. | Accepted: renumber on rebase (spec Assumptions). Edits to `dispatch.py` stay inside `_start` and a new `candidate` function. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 `--repo` in start commands | T004, T005, T006 |
| FR-002 one repository unchanged | T004, T006 (existing tests) |
| FR-003 keep or derive `repo` | T009, T010 |
| FR-004 lint, no refusal | T009, T010 |
| FR-005 `Repository:` plan line | T009, T010 |
| FR-006 park when unresolved | T004, T006 |
| FR-007 `worktree add` fallback | T007, T008 |
| FR-008 lead asked | T011, T012 |
| FR-009 approve reads the draft | T001, T003 |
| FR-010 row order kept | T002, T003 |
| FR-011 invariants | T013, T014 |

Unmapped tasks: T015 (hygiene). No requirement without a task.

## Constitution alignment

Stdlib only, three-state exits unchanged, test first per behaviour, no new refusal below
strict, one helper for the proposal row, invariant rows added: no violation left.

## Metrics

- Requirements: 11; tasks: 15; coverage 100 percent.
- CRITICAL: 0; HIGH: 2 (resolved); MEDIUM: 4 (resolved or accepted with rationale); LOW: 4.

## Next action

No CRITICAL or HIGH finding open; proceed to the checklist and implement.

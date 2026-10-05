# Specification Analysis Report: 533-lint-audience

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
and the code on the worktree base (e447ef8).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Correctness | HIGH | plan sections 3 and 4, spec A2 | A first draft put the client and public hold in `check_lint`. In the hook both `check_tier` and `check_lint` run: after the owner approves a connector draft, `check_tier` spends the one-time allowance and `check_lint` would hold again, a loop of cards. `drafts.approve` also re-runs `check_lint`, so an adapter draft could never be approved. | Put the hold in `classify` (the tier decision): one card, one allowance, and approval (which re-runs only `check_lint`) sends. `check_lint` only warns or, under strict, refuses. | Resolved in plan sections 3 and 4, spec FR-003, FR-004, A2; tested in T003 (`client_approved_sends`). |
| H2 | Test first | HIGH | tasks.md Phase 1 (first draft) | The records tests were ordered after the task that removes the patterns from `lint()`, so they would pass on first run and never be seen failing. | Write them in T001 with the helper test, before T002. | Resolved in tasks.md T001. |
| M1 | Strict | MEDIUM | spec A3 | Under strict, a client draft the owner approves is refused at send by `check_lint`; for a connector call the allowance is spent by `check_tier` first. | Same as today under strict (the lint refuses after approval now too); the program keeps refusals under strict. The planner rewrites the line named in the reason. | Accepted. |
| M2 | Noise | MEDIUM | spec A5, plan section 4 | In the hook `check_lint` runs even when `check_tier` held the call, so under supervised a held call can write an `outward.lint` event although nothing went out. | Same ceiling as the existing `outward.ai_tells` note in `guards/outward._lint`; mark it with a `ponytail:` comment. Autonomous (the default) writes nothing. | Accepted. |
| M3 | Coverage | MEDIUM | spec FR-002, plan section 3 | A mail's `to` address is a destination for the lint but not a party in `classify` (parties read `recipient`, `recipients` and addresses in the text), so a mail to a client address only in `to` gets the company default class and a warning, not a hold. | This is the tier table's existing view of mail (#496), not changed here; the hold follows whatever `classify` already classifies as client or public. | Accepted; noted for a tier-table issue if it matters. |
| L1 | Scope | LOW | spec A6 | `digest._clean` and `remote.dm` lose the pattern check. | Both address only the owner; the item scopes the patterns to chat to other people. | Accepted. |
| L2 | Ordering | LOW | tasks.md T006 to T008 | After T006 the emitted-kinds test in `tests/test_signal_status.py` fails until T007 and T008 land. | Transient inside one phase run; T007 is the failing test for T008. | Accepted. |
| L3 | Workflow | LOW | constitution Workflow | `clarify` and `checklist` are not in this stage; the orchestrator scopes this run to specify, plan, tasks and analyze. | Run them before implement as the pipeline schedules. | Noted. |
| L4 | Deferred | LOW | spec A7 | The setup interview question for the umbrella and autonomy is not on main. | The `autonomy.mode` configuration row names the effect; the interview wording is deferred. | Deferred. |

No CRITICAL findings. No absolute local path, owner name, client name or em-dash in the
artifacts. `tests/test_invariants.py` is absent on the base, so no invariant row is due.

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 `internal_word`, `lint()` without patterns | T001, T002 |
| FR-002 chat and mail only, never records, never the owner | T001, T002, T005, T006 |
| FR-003 client and public hold in `classify` | T003, T004 |
| FR-004 warning, silent, strict refusal in `check_lint` | T005, T006 |
| FR-005 `outward.lint` reserved and silent | T007, T008 |
| FR-006 docs | T009 |
| SC-003 full suite | T010 |

## Constitution

- I stdlib only: no new dependency. II exits: invalid patterns fail closed as exit 2 through
  the existing `try` blocks. III: one function per behaviour. IV: every behaviour task has
  its failing test before it. V: one helper, no new module or key. VII: the new event kind
  is reserved to its producer; no seat-writable record gains trust.

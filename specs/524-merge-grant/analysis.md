# Specification Analysis Report: 524-merge-grant

Artifacts: `spec.md`, `plan.md`, `tasks.md`, constitution 1.4.0, design spec 4.6, 4.7, 9.1.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Constitution / #530 | HIGH | plan.md `check` | The granted check reused the auto policy's refusal wrapper, so a moved head or a red check under a grant would print `the owner merges; ask the owner`, the wall the owner reported. | Resolved: FR-002a and the plan give the granted path its own reason (`no grant lifts this; run bin/wuwei pr act <ref> once it holds`); T009 asserts it and the absence of `ask the owner`. |
| A2 | Coverage / tests | HIGH | tasks.md T009 | Existing `execute` tests that assert an eligibility reason (`merge.auto is off`) reach the new grant path and would fail without a stated fix. | Resolved: T009 says to point them at `check` or assert the card. |
| A3 | Reason shape (#362) | MEDIUM | plan.md `by_grant`, squash require | New reason strings must pass `tests/test_reasons.py` (`NEXT_STEP`). | Resolved: the texts use `: ask the owner to run ...`; T019 runs `test_reasons.py` first. |
| A4 | Governance | MEDIUM | plan.md Docs | The design spec is amended only by its owner. | The change is the owner's issue (#524, 2026-10-05); the amendment is a dated `(owner, 2026-10-05, #524)` line as for #478 and #530. |
| A5 | Ambiguity | MEDIUM | spec FR-002 | "The merge decision is recorded" has no record type on main (#511 is not built). | Recorded under Assumptions: the decision is the owner's recorded answer (card, planned card, standing line) or the auto policy clearing the PR. |
| A6 | Inconsistency | LOW | spec Assumptions | The hook still appends `no setting lowers it` to a session `gh pr merge` redirect while `merge.default_tier` now exists. | Accepted: the redirect itself is not lowered by any setting (the merge must run through `wuwei merge`); the reason now names that command. |
| A7 | Underspecification | LOW | spec Assumptions | Granted merges count toward the auto daily cap and can trip the breaker. | Accepted and recorded; the breaker stops only the auto path. |
| A8 | Dependency | LOW | spec Deferred | `grants.gate` checks the heartbeat session before the grant lookup, so #511's headless run cannot use a grant. | Deferred to #511, recorded. |
| A9 | Fixture churn | LOW | tasks.md T003 | Adding `squash` to the protection boolean validation breaks every fake protection dict without it. | T003 lists the files and the grep that finds them. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 merge is a grant action | T005, T006 |
| FR-002 granted check | T007, T008 |
| FR-002a granted refusal text | T009, T008 |
| FR-003 squash measured and required | T001 to T004 |
| FR-004 execute: grant, card or command | T009, T010 |
| FR-005 merge.default_tier | T005, T006, T009 |
| FR-006 standing merge lines | T005, T006, T009 |
| FR-007 planned merge cards | T013, T014 |
| FR-008 pr act print, guard redirect | T011, T012, T015, T016 |
| FR-009 docs and charters | T017, T018 |

Issue acceptance: granted merge from `pr act` with `grant.used` (T011, T009); card under
guarded and owner-only command under strict (T009); moved head never merges (T007, T009).

## Constitution alignment

- Test first: every implementation task follows its test task. Pass.
- Stdlib only, adapters behind ports: the squash read is in the code host adapter. Pass.
- Fail closed: auto-policy exit 2 never reaches the grant path; a missing
  `allow_squash_merge` is exit 2. Pass.
- Security (VII): no approval, no `--admin`, no protection change; the merge stays
  `--squash --match-head-commit` at the gated head. Pass.
- Ponytail: no new module, event kind or state key; two keyword arguments and two small
  functions. Pass.
- `tests/test_invariants.py` is absent on this base; no invariant row is required.

## Metrics

- Requirements: 10 (FR-001 to FR-009 with FR-002a); tasks: 19; coverage 100%.
- CRITICAL: 0; HIGH: 2 (both resolved); MEDIUM: 3; LOW: 4.

## Next action

No CRITICAL or HIGH finding is open. Proceed to `speckit-checklist`, then `speckit-implement`.

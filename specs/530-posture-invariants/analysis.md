# Specification Analysis Report: 530-posture-invariants

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md` (1.4.0),
design spec 4.6, 4.7, 4.9, 9 and 9.1, and the code the plan cites.

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| I1 | Inconsistency | HIGH | spec.md FR-002, FR-003, US1 scenarios 4 and 5 | FR-002 relabels canary, honeytoken and owner-marker refusals as the records floor in every posture, while FR-003 and scenario 5 said strict stays exactly as today. | Resolved: FR-003 and scenario 5 now except the records-floor label; T002 asserts it. |
| A1 | Ambiguity | HIGH | spec.md US2 scenario 1, SC-002; issue acceptance "runs in under a second" | Unclear whether the one-second budget covers the whole file (fixtures, corpus walk) or the walk. | Resolved: the budget is the product walk with its real calls; fixtures and the corpus walk sit outside it (spec Assumptions); plan gives the fallback if the walk is over budget. |
| C1 | Constitution / scope | HIGH | spec.md Definitions, Assumptions; plan constitution text | The owner's words are "a warning or a card, never a refusal". The spec treats a refusal that names the seat's own fix (coaching, #362) as not a wall, so under guarded such refusals still block. Read literally, every fix would become a warning or a card. | Resolved by an explicit, reversible assumption with its reasoning (a fix needs no permission; making fixes warnings would pass a force push or a default-branch push under the supervised answer; making each a card asks the owner for what a seat corrects). The wall test is one regular expression the owner can widen. Flagged to the orchestrator. |
| U1 | Underspecification | MEDIUM | plan.md product walk, `grant` projection | Sequential grant states on one workspace could leak (a `today` row lets a later `keep` case pass). | Resolved: plan replaces the whole `grants` dict before each call. |
| U2 | Underspecification | MEDIUM | plan.md corpus walk | Corpus texts built from shared constants start with `{}` (`UNKNOWN_GIT`), so a stub misses the prefix the hook levels by; non-guard modules (`security.py`) hold reasons that are not hook reasons (init errors). | Resolved: sources restricted to the functions the guards call; the unknown-git row is in `EXEMPT` with its #470 note. |
| U3 | Underspecification | MEDIUM | spec.md I7, plan I7 | A first draft asserted that a connector docs write is held under the ask umbrella; `outward.classify` (`:644-646`) lets a docs payload's own `kind` decide without the port flag, and `tests/test_outward.py::test_docs_kind_drafts_unless_auto` pins that. | Resolved: I7 asserts the adapter half and the send-umbrella connector half only. Note for the owner: under `ask`, a connector docs payload that names a `docs.auto` kind sends; not changed here (not a wall, and #419 pins it). |
| D1 | Deferred | MEDIUM | spec.md Deferred; `grants.py:129`; `commands/init.py:71` | `permissions.deny` rules that init writes for deploy and release verbs refuse a call a grant would allow: a wall below strict that this part cannot lower without changing the harness settings. | Recorded under Deferred for a follow-up issue (relates to #530 part C); listed in the corpus walk's `EXEMPT` and the 9.2 notes. |
| P1 | Process | MEDIUM | constitution Workflow | `speckit-clarify` and `speckit-checklist` are not part of this run (steps 1 to 5 were requested). | The orchestrator runs the checklist before implement; clarifications are answered under Assumptions. |
| T1 | Coverage | LOW | tasks.md T013 | FR-009 (constitution text) has no test; the constitution's rule is checked through the 9.2 table and `test_table_matches_the_checks` (T008). | Accepted: prose of the constitution is not pinned by tests elsewhere either. |
| T2 | Test-first | LOW | tasks.md T006, T007 | The invariant walk checks rules that already hold on main, so its red step is the mutation test against a stub walk. | Accepted: the mutation test is the failing test the walk must turn green. |
| S1 | Style | LOW | constitution Governance | Amendments carry a dated line in the commit message. | The ship step writes it; nothing in the artifacts. |

## Coverage Summary

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 owner-only line dropped below strict except #524 | Yes | T002, T003 | |
| FR-002 records-floor label for canary, honeytoken, markers | Yes | T002, T003 | |
| FR-003 strict unchanged | Yes | T002 | |
| FR-004 four reasons reworded | Yes | T004, T005 | |
| FR-005 design 9.2 table | Yes | T008, T009 | |
| FR-006 product walk dimensions | Yes | T007 | |
| FR-007 real rules, memoised | Yes | T007 | |
| FR-008 reason-corpus walk | Yes | T001, T005 | |
| FR-009 constitution | Yes | T013 | no test (T1) |
| FR-010 nothing added, levels unchanged | Yes | T002, T014 | |
| US3 text that states the old rule | Yes | T010, T011, T012 | |

Constitution alignment: no conflict with a MUST. Principle VII is amended by this feature
at the owner's request (issue #530); the amendment keeps "guards refuse at the moment of
action", the merge policy and the grant rule. Exits, test-first, one behaviour per function
and stdlib only hold.

Unmapped tasks: none.

## Metrics

- Total requirements: 10 functional + US3 text scope
- Total tasks: 14
- Coverage: 100% (every requirement has at least one task)
- Ambiguity count: 1 (resolved)
- Duplication count: 0
- Critical issues: 0; HIGH: 3, all resolved in the artifacts

## Next Actions

No CRITICAL or open HIGH finding. Proceed to `speckit-checklist`, then `speckit-implement`.
The builder should read C1 and U3 before T001: they set what counts as a wall and what I7
asserts.

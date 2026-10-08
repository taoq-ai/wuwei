# Specification Analysis Report: 557 measured reversibility

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `AGENTS.md`,
`.specify/memory/constitution.md`, design 5.8 and 5.8.1, the orchestrator notes for the
item, and the code on the base (main at #565) and on the #283 branch.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Inconsistency | CRITICAL | spec Assumptions, tasks T001 | The earlier draft made the build stop when the base lacked #283, while the orchestrator note says to build so #283 can reuse the registry when #283 has not landed. #283 is built and pushed on its branch (frozen code, in its ship step), so a second D-n undo built here would be the second undo path the same note forbids. | Resolved: T001 fetches and fast-forwards the worktree to `origin/main` (untracked spec files only, no commit); `wuwei undo D-n` calls #283's `commands.decision.undo`, `decision undo` stays as its alias; stop and report only if `origin/main` still lacks #283. Recorded in Assumptions. |
| A2 | Security / correctness | HIGH | plan `rehearse` decision branch, tasks T024, T025 | The `decision` rehearsal called `decide` and `undo` with a scratch root, but both resolve their root through `workspace.find_workspace`, which honours `WUWEI_WORKSPACE` first. In a planner session that sets it, the scratch record would be routed and undone in the real workspace: a rehearsal touching a real target. | Resolved: the rehearsal pins `WUWEI_WORKSPACE` to the scratch root and restores it in a `finally`; `decide` keeps its signature; T024 tests the pin with `WUWEI_WORKSPACE` naming the real root. |
| A3 | Correctness | HIGH | spec FR-005, plan `correct`, tasks T012 | The correction ran before `mandate`'s already-held check, so re-routing a record the mandate took before the ledger existed (after an upgrade) would rewrite a decided record to one-way and print a correction under a `mandate` result. | Resolved: the correction applies on a first route only (id in neither `decision_routes` nor `decision_outcomes`); new US1 scenario 8, edge case and T012 assertion. |
| A4 | Constitution (#362 reasons) | MEDIUM | spec US2.5, US3.3, plan `run`, `rehearse` | Two exit 1 reasons (`it cannot be undone`, `naming the registered kinds`) named no next step and would fail `tests/test_reasons.py`. | Resolved: both name a command (`run wuwei why <event id>`, `run wuwei undo rehearse commit or ...`); T024 checks every reason of `undo.py`. |
| A5 | Underspecification | MEDIUM | spec Assumptions | The issue says the lint "refuses" a two-way claim, but #530 forbids new refusals under observe and guarded, and the issue also says the CLI corrects it. Strict was unaddressed. | Resolved: Assumptions read "refuses" as refusing the claim under every posture, strict included; the record is corrected and carded; invariant (d) covers the lint exit code. |
| A6 | Underspecification | MEDIUM | spec US2 | What `wuwei undo D-n` does to code a seat committed under a commit-kind decision was unstated. | Resolved: Assumptions state the undo returns the decision to the owner; the seat reverts its own branch on the new answer; the CLI does not revert item-branch commits. |
| A7 | Coverage / suite risk | MEDIUM | tasks T007, T035 | The autouse fixture stands the ledger in as rehearsed in process only; subprocess-driven fixture days that route two-way records will see an empty ledger and card them. | Kept: T035 has those fixtures run `wuwei undo rehearse` in setup. Builder should expect a few such fixes. |
| A8 | Scope | LOW | spec Deferred, US5 | `## Cannot be undone` lists one-way decisions and sent messages only; PR raises, tracker and docs writes are unregistered (one-way by rule) but not listed. | Kept as Deferred: they join the registry and the section with their adapter undo. |
| A9 | Wording | LOW | spec FR-015 (c) | The merge event undo confirms at a host terminal, a third route beside the planner card and the DM. | Kept: the host terminal y is the owner (the #354 confirmation), never a seat; the invariant test checks that no route without a card, DM reply or terminal writes anything. |
| A10 | Agility (owner's autonomy push) | LOW | spec Assumptions | Risk that the measured door adds owner steps. | Checked: rehearsals run once per workspace on scratch from `wuwei next` rows the planner walks without the owner, before any seat launches on day one; after that routing is as today. Recorded under Assumptions. |

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001, FR-002 registry and kinds | T002, T004 |
| FR-003 measured door | T008, T009 |
| FR-004 lint line | T010, T011 |
| FR-005 route correction | T012, T013, T014, T015 |
| FR-006 `wuwei undo D-n` | T016, T017 |
| FR-007 merge event undo | T018, T019, T020, T021 |
| FR-008 rehearsal | T022, T023, T024, T025 |
| FR-009 records floor, reserved events | T005, T006 |
| FR-010 `next` rows | T026, T027 |
| FR-011 init and doctor | T028, T029 |
| FR-012 report sections | T030, T031 |
| FR-013 no new refusal | T010, T032 (d) |
| FR-014 docs and design 5.8 | T033, T034 |
| FR-015 invariants | T032 |
| Issue acceptance 1 to 4 | T012, T013, T012, T016 |

Every behaviour has its test task before its implementation task. No task is unmapped.

## Constitution

Test first, stdlib only, no subprocess in the core (the scratch git work is a git adapter
operation with a closed allowlist), exits 0, 1 and 2 with reasons, producer-only ledger
file and event kinds, no new config key, field or class. No violation remains.

## Metrics

- Requirements: 15 functional, 4 success criteria
- Tasks: 35, all mapped
- CRITICAL: 1 found, 1 resolved; HIGH: 2 found, 2 resolved; MEDIUM: 4 (3 resolved, 1 kept
  with a task); LOW: 3 kept

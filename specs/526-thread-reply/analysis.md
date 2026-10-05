# Specification Analysis Report: 526-thread-reply

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.4.0) and the code on the worktree base (c75ac88).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Correctness | HIGH | plan.md section 3, spec FR-003 | A first draft added only the thread row and recorded participants. Under `ask`, a thread reply with nothing recorded then had one reader, the work channel (team), which the new row sends: an unlearned thread would go out, the opposite of the issue. | Add one "not learned" party per unrecorded thread with the connector default class, so the company row asks under `ask` and the umbrella decides under `send`. | Resolved in spec FR-003 and plan section 3. |
| H2 | Inconsistency | HIGH | tasks.md T005 | The test named rule 10 for the thread row under both umbrellas; under `send` the three broad rows drop out and it is rule 7. | Name `<n>`: 10 under `ask`, 7 under `send`. | Resolved in T005. |
| M1 | Ambiguity | MEDIUM | spec A1, A2 | The issue says an unknown participant's reason names learn, and "team or company sends". Under the shipped `send` umbrella (#531) unknown and company readers send without a card; under `ask` company asks. | Recorded as assumptions A1 and A2; acceptance 2 is tested under `ask`, acceptance 1 and 3 under both. No new hold under `send` except a client or public participant (a card). | Accepted. |
| M2 | Coverage | MEDIUM | spec A4, Deferred | A table `block` row's posture line still says "no setting lowers it". | Out of the issue's named scope (held draft); listed under Deferred as a follow-up issue. | Accepted. |
| M3 | Security | MEDIUM | plan section 4, spec A7 | The participants record is planner-supplied evidence that lets a thread reply send. | Same trust as #492's listings: learn runs only in the planner session, the state key and event are reserved to `wuwei outbound learn` (T007, T008), unknown people still pass the card or `learn = "auto"` outside strict, and client participants still ask. | Accepted. |
| L1 | Fail closed | LOW | plan section 2 | `classify` now reads state for a thread reply; a read error is `UNRUN`, so under `send` an unreadable state turns a thread reply into a draft where main sent it. | Fail closed is the constitution's rule (II); keep. | Accepted. |
| L2 | Workflow | LOW | constitution Workflow | `clarify` and `checklist` are not in this stage; the orchestrator scopes this run to specify, plan, tasks and analyze. | Run them before implement as the pipeline schedules. | Noted. |
| L3 | Ordering | LOW | plan section 4 | The record step runs before the open-card and kept checks, so a kept connector still gets its participants recorded, then exits 1 as today. | Harmless: the record lets known team readers send; nothing else changes. Covered by the T007 open-card test. | Accepted. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 topic `thread` | T001, T002 |
| FR-002 thread topic in classify | T005, T006 |
| FR-003 participant and not-learned parties | T005, T006 |
| FR-004 default thread row | T003, T004 |
| FR-005 `outbound learn --thread` | T007, T008, T009 |
| FR-006 Always option | T010, T011 |
| FR-007 posture line | T012, T013 |
| FR-008 docs | T014, T015 |
| SC-001 to SC-003 | T005, T007, T012, T016 |

Every behaviour has a test task before its implementation task. No requirement without a
task; no task without a requirement.

## Constitution alignment

- I stdlib only, II exits, III one function per behaviour, IV test first, V ponytail (one row,
  one topic, one flag, one state key; learn card, `propose`, `apply`, `_person`, `decide` and
  `always_row` reused), VII security (no new refusal under observe or guarded; reserved
  producers): no violation.
- `tests/test_invariants.py` is absent on this base; no invariant row is required (spec A9).

## Metrics

- Requirements: 8 functional, 3 success criteria. Tasks: 16. Coverage: 100 percent.
- CRITICAL: 0. HIGH: 2, both resolved in the artifacts. MEDIUM: 3 accepted with recorded
  assumptions. LOW: 3.

## Next step

No open CRITICAL or HIGH finding; implement may start after clarify and checklist.

# Specification Analysis Report: 509-to-owner-event

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
and the code on the worktree base (327dd57).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Test first | HIGH | tasks.md T001, constitution IV | The behaviour already holds on the base (#496 removed the mode switch), so the new test passes on first run and is never seen failing. | Add a mutation step: remove the event append in `check_tier`, see all three cases fail on the event list, restore. | Resolved in tasks.md T001a. |
| M1 | Scope | MEDIUM | spec Root cause, A1 | The issue and the orchestrator note assume a mode switch before the owner check; on main there is none, so the item ships a test and no code change. | Keep the diff to the test; the plan's Contingency names the shared spot if a later base reintroduces a fast path. | Accepted. |
| L1 | Duplication | LOW | plan Changes, `test_guard_to_owner_floor` | The floor test already covers modes `draft` and `refuse` under strict with a sensitive word. | The new test is the per-mode test the issue asks for (default posture, exactly one event per call, `send` included); the floor test keeps its own purpose. | Accepted. |
| L2 | Coverage | LOW | spec A3 | `remote.dm`, WUWEI's control-plane reply, records no `outward.to_owner`. | Not a connector write and not this item's path; raise separately if the owner count must include it. | Deferred. |
| L3 | Coverage | LOW | spec A4 | The event is appended before `check_lint`, so a self-DM the lint refuses still counts. | Existing ponytail note in `check_tier`; unchanged. | Accepted. |
| L4 | Workflow | LOW | constitution Workflow | `clarify` and `checklist` are not in this stage; the orchestrator scopes this run to specify, plan, tasks and analyze. | Run them before implement as the pipeline schedules. | Noted. |

No CRITICAL findings. No absolute local path, owner name, client name, emoji or em-dash in
the artifacts. `tests/test_invariants.py` is absent on the base, so no invariant row is due.
The planned test was run from a copy outside the repository on the base: three passes.

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 one event per call under send, draft and refuse | T001, T001a |
| FR-002 no draft, no refusal for a message to the owner | T001 |
| FR-003 one test per mode through the guard | T001 |
| SC-001 test fails when a path skips the owner check | T001a |
| SC-002 full suite green, no production change | T002, T003 |

## Constitution

- I stdlib only: no runtime change. II exits: unchanged. III: the behaviour stays in
  `outward.check_tier`, now with its per-mode test. IV: T001a shows the test failing for the
  right reason before it is trusted. V: no production diff, existing helpers reused. VII:
  `outward.to_owner` stays reserved to its producer; no new trust surface.

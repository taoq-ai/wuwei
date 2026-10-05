# Specification Analysis Report: 516-subagentstop-budget

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.4.0) and design spec 2 (hook latency budget) and 10.6.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Coverage | HIGH | spec US1.4, issue Deliver | The issue asks for a test that SubagentStop's import graph "adds no module beyond PreToolUse's"; the literal reading fails on the five guard modules SubagentStop must import. | Resolved: spec Assumptions defines the allowlist (guard modules plus the four modules the path executes) and why; T007 pins it, so any new module fails. |
| A2 | Coverage | MEDIUM | spec US1.1, SC-003 | Acceptance 1 (five consecutive green latency jobs on the runner) cannot run locally; macOS fsync does not flush, so a local wall figure would not show the saving. | Accepted: T001 pins the fsync and append counts that carry the runner's blocked time; T016 reports the local numbers; the owner's runner confirms after merge. |
| A3 | Constitution III | MEDIUM | plan, `brief.tail_turn` | A second reader of the transcript format risks two parsers. | Resolved: both readers share `_entry` (the per-line parse); `last_turn` keeps its contract. |
| A4 | Constitution V / data loss | MEDIUM | FR-002 | Skipping the directory fsync after the `state.json` rename touches the single writer's durability. | Resolved: the snapshot's directory fsync, before the event append, makes both renames durable at return; argument in spec Assumptions; every other `atomic_write` caller unchanged. |
| A5 | Underspecification | MEDIUM | FR-001, plan lifecycle | The fold couples two guards through a payload key. | Resolved: the key carries the resolved root it wrote; lifecycle skips only on a match; a changed guard order yields a second write, never a lost one; T002 guards the unmatched case. |
| A6 | Inconsistency | LOW | issue "write the events in one append" vs FR-001 | Only the events of the one state write share an append; `discovery.requested` and `spec.warned` stay separate. | Accepted with measurement (about 0.1 ms each, no fsync); recorded in spec Assumptions. |
| A7 | Inconsistency | LOW | issue "read the transcript only when the message is absent" | The brief-reference head read stays on the message-present path; `build.stopped` keeps its full read. | Accepted: the head read binds the stop to its seat; the build binding stores the line index and hash; recorded in spec Assumptions. |
| A8 | Ambiguity | LOW | SC-003 | The 40 ms CPU target is not asserted: the workspace latency test asserts wall only. | Accepted: the test is not loosened or changed (FR-006); the CPU figure is reported. |
| A9 | Coverage | LOW | tasks T013 | Editing a #473 test could look like loosening it. | Resolved: the edit adds a stub, so the test guards the new reader as well; spec US2.1 says so. |
| A10 | Scope | LOW | spec Deferred | The benchmark fixture has no `charters/`, so it skips the retro evidence write a real stop pays. | Deferred to its own issue; out of this issue's scope. |

No CRITICAL findings. The one HIGH finding (A1) is resolved in the artifacts.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 one state write, one append for its events | T001, T002, T004, T005, T006 |
| FR-002 one directory fsync per state write | T001, T003, T004 |
| FR-003 unused imports off the path | T007, T008, T009, T010, T011 |
| FR-004 tail read of a missing report | T012, T013, T014 |
| FR-005 no result, event or refusal changes | T001 (state and events), T006 and T011 suite runs, T015 |
| FR-006 latency test and budgets unchanged | no task edits them; T016 |

Every behaviour task has its test task earlier in the same phase. Unmapped tasks: none.

## Constitution alignment

- I Stdlib only: no new imports beyond stdlib.
- II Exits: unchanged; no refusal added in observe, guarded or strict.
- III One behaviour, one function: the registry upsert stays `sessions.record`, the writer
  stays `_write_state`, the transcript line parse is one function.
- IV Test first: T001, T007, T012 and T013 fail on the base for the stated reason; T002 is a
  regression guard that passes on the base and must keep passing.
- V Ponytail: no new module, no config; one `ponytail:` comment on the tail window.

## Metrics

Requirements 6, tasks 16, requirements with tasks 100%, CRITICAL 0, HIGH 1 (resolved).

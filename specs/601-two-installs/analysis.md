# Specification Analysis Report: 601-two-installs

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against
`.specify/memory/constitution.md` (1.5.0) and design spec 9.2.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Constitution | MEDIUM | spec FR-003, plan 1 | Principle II says exit 2 blocks; the traces guard now returns 0 below strict on a recording failure. | Principle VII (#530) governs: below strict a guard is a warning, the records floor excepted, and the issue and notes say the traces guard is not that floor. The warning is the stderr reason plus `traces.gap`, which doctor counts. Strict keeps exit 2. I25 records the rule. No change. |
| A2 | Constitution | MEDIUM | plan 1 | Principle III: posture levelling lives in `hook.posture`, and the traces guard now decides strict itself. | Precedent: the MCP gate and spec mode apply their own posture (`guards/__init__.py` AREAS comment). Doing it in the guard keeps a failed events append from turning the warning back into a refusal, which the hook's warn path would do. `AREAS`, `FLOORS` and `hook.posture` stay unchanged. No change. |
| A3 | Coverage | HIGH (resolved) | tasks Phase 1 | The invariant test was first ordered after the traces implementation, which broke test-first. | Moved: T005 writes `i25` and the 9.2 row before T006 implements. |
| A4 | Ambiguity | MEDIUM | spec US2, Assumptions | "The one the hooks run" cannot be measured by doctor for an unregistered `--plugin-dir` copy. | Recorded as an assumption: the registered install is the one the hooks run; the traces reason (FR-004) names any other launcher from the hook side. |
| A5 | Underspecification | MEDIUM | plan 3 | With the record following the registration, `init --upgrade` from a newer extraction points the workspace at an older registered install. | Intended: the record must name what the hooks run. The installs row names both and the fix; updating the registered plugin is the owner's `/plugin` step. No change. |
| A6 | Coverage | LOW | spec Assumptions | The issue lists "the integrity record" as something the traces reason may name; nothing on the traces path reads it. | Recorded as an assumption; FR-001 lists the steps the guard reads. |
| A7 | Consistency | LOW | tasks T014, plan 4 | `test_trace_gap_on_status_line_and_doctor` calls `doctor._day` with probes lacking `config`. | Plan and T014 read `probes.get('config')` and skip the row without it. |
| A8 | Consistency | LOW | tasks T016 | `test_tracker_port_contract` pins the backlog row keys for all three trackers. | T016 allows `repo` on GitHub rows only. |
| A9 | Consistency | LOW | plan 6 | `discovery.discover` already uses `repo` as the scanner loop variable. | Plan says to rename the loop variable. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 named reason | T001, T004, T006 |
| FR-002 common tail and gap | T001, T006 |
| FR-003 warn below strict, fail closed | T001, T003, T005, T006 |
| FR-004 executable mismatch in reason | T002, T006 |
| FR-005 install helpers in init and doctor | T007, T008, T009, T011 |
| FR-006 installs row | T010, T011 |
| FR-007 heartbeat reloads env | T012, T013 |
| FR-008 credentials row | T014, T015 |
| FR-009 GitHub backlog over every repository | T016, T017 |
| FR-010 discover `--repo`, scanner `repo` | T018, T019 |
| FR-011 lead charter and agents | T020 |
| FR-012 invariant I25 | T005 |

Every functional requirement has a test task ordered before its implementation task. No
task lacks a requirement. Success criteria SC-001 to SC-005 map to T005, T001, T007, T012
and T018.

## Constitution alignment

- Stdlib only: no import beyond the standard library; the tracker port signature is kept.
- Fail closed: an unreadable config keeps the traces refusal (T003); one failed repository
  read makes the tracker source unmeasured (T016).
- Invariant rule: the changed guard rule has I25 in design 9.2 and `tests/test_invariants.py`.
- Style: no em-dashes, no emojis, no absolute local paths in the artifacts.

## Metrics

- Functional requirements: 12; tasks: 21; coverage: 100 percent.
- CRITICAL: 0. HIGH: 1, resolved (A3). MEDIUM: 4, accepted with rationale. LOW: 4,
  folded into plan and tasks.

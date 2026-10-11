# Specification Analysis Report: 843-discovery-rank-out

Artifacts read: spec.md, plan.md, tasks.md; the constitution (2.2.0); the #789 pass plan
(owner constraints, "Process control kept", the part 21 lead call); the issue brief and its
lead note; the part 17 plan; the code and tests at d60253b8.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| K1 | Owner constraint | CRITICAL | FR-004, US1 | "Spec before gates (non-light tiers)" is a kept process control; deleting `specmode.check` with the guard would lose it. | Resolved: only `check_edit` goes; dispatch and build checks stay; T001 adds the standard and light cases before any deletion. |
| K2 | Owner constraint | CRITICAL | FR-002, FR-005 | The lead note keeps morning discovery and ranking in code. `discovery.py` and `rank.py` hold both kept and deleted functions. | Resolved: only intake functions and the command go; `discover`, `dedupe`, `rank.rank`, `rank.validate` stay; US4 tests the order. |
| S1 | Scope | HIGH | `check_record`, `check_stop` | The issue names "the PreToolUse spec guard"; the module has two more hooks. | Resolved: Assumption 3 keeps them; they never refuse an edit. |
| T1 | Tests | HIGH | `tests/test_intraday_intake.py` | It holds the owner `plan add` cases and a helper two files import. | Resolved: T003 moves them before T004 deletes the file. |
| E1 | Test | MEDIUM | `tests/test_e2e_day.py` | The scripted day asserts a PreToolUse spec refusal and runs `wuwei rank`. | Plan rewrites both to the build loop's `spec` check and `plan propose`. |
| M1 | Behaviour | MEDIUM | advisory mode | With `guards.enforce = false` dispatch only warns on a spec gap. | Unchanged behaviour (part 15); recorded under Risks for batch 8. |

**Coverage**: FR-001 T003, T004; FR-002 T004, T006; FR-003 T002; FR-004 T001; FR-005 T005,
T006; FR-006 T007; FR-007 T008; FR-008 T008, T009. 8 requirements, 9 tasks, 100%.

**Constitution Alignment**: I to VII hold; IV via T001, T005, T007.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.

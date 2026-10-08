# Specification Analysis Report: 579-pace

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 5.2, 5.3 (#567 amendment), 5.6 and 9.2, issue #579 with the owner's
comment, and the orchestrator notes for #579.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Security / forgeable trust | HIGH | spec FR-007, plan `plan set` | The pace selects which recorded checks count as push evidence and lightens depth at fast. The first draft let any caller run `wuwei plan set pace=fast`, and a seat runs the CLI as the owner (9.1), so a seat could lighten its own evidence. | Resolved: `protect_state` lets the literal `plan set pace=<p>` run only from the registered planner session below strict; a seat keeps today's `plan set` owner-action reason (no new refusal). `pace` is producer-owned state; `proposal.json` is already protected. T030a/T030b test and implement it; I16 checks it. |
| A2 | Underspecification | HIGH | plan `pace.host_line` | The last suite duration was read from today's state only, so at the morning gate (before any check ran today) the host line would always say unmeasured and the advice would never see it. | Resolved: `host_line` searches day states newest first for the newest `repos.tests` record with `seconds`, as `calibrate.host` searches days for the seat cost; T025 covers a prior-day record. |
| A3 | Inconsistency | MEDIUM | issue Acceptance 2 vs the issue's pace table | Acceptance says guard items run full "whatever the owner picks"; the table says steady is "the computed tier". | Recorded under Assumptions: careful and fast pin guard-code and trust-path diffs to full; steady keeps #567's standard with step zero, so a default day does not change. US2 scenario 4 pins steady. |
| A4 | Floors | MEDIUM | spec FR-010, plan `fast_evidence` | Under strict the push guard still refuses without evidence, but at fast the evidence it accepts is the touched-test record instead of the fast checks. | Accepted: the issue asks for exactly this rule; local checks are not in the floor list (records, grants, strict refusals, trust-boundary findings, merge at the gated head with green required checks, routing). The refusal itself never moves; an unreadable diff or empty `repos.tests` falls back to the fast checks, so evidence is never empty. |
| A5 | Behaviour | MEDIUM | plan `launch_set` hold | At fast on a saturated host the hold also delays gate seats, so ready items wait for the load to fall. | Accepted: the issue says any seat that would push the load over the core count waits; the hold is a `wait` with the reason, never a refusal, and the status line shows `held by load`. |
| A6 | Coverage | MEDIUM | issue Deliver "the shepherd read it from state" | No shepherd change is planned. | Accepted: the shepherd merges only through the merge policy, which already requires green required checks at the gated head; fast must not change it, which I17 checks at every pace. |
| A7 | Ambiguity | MEDIUM | notes "one more option row" | The gate card gains two rows (`Approve at <p>` for each other pace), not one. | Accepted: still one question with the recommendation first (#530), within AskUserQuestion's four options; each row is a complete answer recorded by the same command with `--pace "<label>"`. |
| A8 | Inherited behaviour | MEDIUM | plan `brief.write` builder depth | The builder's depth is predicted at brief time on a near-empty diff, so at fast a builder about to touch guard code may be told `Depth: light`. | Accepted as #567's A1 design: the gates read only the tier `dispatch next` records from the real diff, so a guard diff is still raised to full before any gate; the SubagentStop retro check recomputes on the builder's diff. |
| A9 | Ambiguity | LOW | issue "token budget" | How the budget changes the advice was open (it cannot make careful cheaper). | Recorded under Assumptions: the budget names itself binding and advises against the pace with the items it reaches; it never changes the pace. |
| A10 | Performance | LOW | plan `dispatch.tier` | `tier` now reads day state for the pace, including on the SubagentStop path through #567's `_light`. | Accepted: one JSON read; an unreadable state means steady, today's record. |
| A11 | Noise | LOW | plan `launch_set` | `cap.derived` events are written when the bound flips between `host` and `load`. | Accepted: one event per flip, the same producer and kind as #528. |
| A12 | Constitution | LOW | plan Docs and design | The design spec is amended only by its owner. | The issue is the owner's and names the rule a design 5.2 amendment; the paragraph carries "(owner, 2026-10-08, #579)" like #567. |
| A13 | Coordination | LOW | spec FR-019 | Parallel items may also add 9.2 rows. | The rows take the next free ids on the base at build time; `test_table_matches_the_checks` keeps the table and `INVARIANTS` in step. |
| A14 | Dependency | HIGH | plan Precondition, spec Root cause | The worktree base (b6daa42) predates #567, which is on `main` as PR #577; the plan calls `dispatch.depth`, `step_zero`, `GUARD_CODE`, `CLASS_PATHS`, `metrics.cycles` and `cycle_by_tier`, absent on the base. Root-cause line numbers were taken from the base. | Resolved: Root cause cites `main` at 4e23a55 (verified: every named #567 symbol exists there); the Precondition and Assumptions tell the builder to bring the branch up to `main` before T001 and to stop if the symbols are still missing. |
| A15 | Inconsistency | HIGH | spec FR-019, plan and tasks invariant rows | The rows were numbered I12 to I14, which `main` already uses (#559 calibration, #560 shadow). | Resolved: renumbered I15 to I17 (next free on `main` at 4e23a55), with an Assumption that they take the next free ids at build time. |
| A16 | Underspecification | MEDIUM | plan `tests/test_invariants.py` | The first draft named `decision.level` and `decision.CLASSES`, which do not exist, and gave no `READS` entries; the walk on `main` raises on an undeclared dimension. | Resolved: I16 uses `cruise.level` over `cruise.CLASSES` and `decision.route`; each row declares `READS` (I15 and I17 none, I16 posture) and is cached to keep the 1.0 s walk budget. |

No CRITICAL findings. HIGH findings A1, A2, A14 and A15 are resolved in the artifacts.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T002 |
| FR-002 | T001, T002 |
| FR-003 | T027, T028 |
| FR-004 | T025, T026 |
| FR-005 | T027, T028, T031, T032 |
| FR-006 | T029, T030 |
| FR-007 | T029, T030, T030a, T030b |
| FR-008 | T003 to T006 |
| FR-009 | T007, T008 |
| FR-010 | T009 to T014 |
| FR-011 | T015, T016 |
| FR-012 | T017, T018 |
| FR-013 | T019 to T022 |
| FR-014 | T033, T034 |
| FR-015 | T023, T024 |
| FR-016 | T035, T036 |
| FR-017 | T037, T038 |
| FR-018 | T039, T040 |
| FR-019 | T041, T042 |
| FR-020 | T042 to T044 |

Every behaviour has a test task ordered before its implementation task. No task without a
requirement.

## Constitution alignment

- I stdlib: `os.getloadavg`, `shlex`, `statistics`; no dependency.
- II exits: new commands exit 0 or 2 with the reason; unmeasured load, suite and budget are
  printed as unmeasured.
- III one function per behaviour: `pace.adjust`, `pace.seats`, `pace.advise`,
  `fast_checks.commands`; callers reuse them.
- IV test first: tasks are ordered test then implementation.
- V ponytail: one module, one pure rule, two config keys; no second tier or depth table.
- VII and #530: no new refusal under any posture; the agent-launch guard and the merge
  policy do not read the pace; three invariant rows (I15 to I17).

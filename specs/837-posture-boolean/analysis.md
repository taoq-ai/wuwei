# Specification Analysis Report: 837-posture-boolean

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.1.0);
- the #789 pass plan (owner constraints, "Process control kept", outward duties, #831 handoff);
- the code and tests at 703b40de.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Process control | CRITICAL | FR-004, US1.3 | Mapping observe to `enforce = false` must not let a merge, deploy or state-file write through where observe refused it. | Resolved. `guards.FLOOR` keeps every floor observe had (records, merge, admin, approve, protection, deploy, held sends) blocking in both settings; the hook table test covers each (T001). |
| P2 | Owner constraint | CRITICAL | US4 | The table rows (seat without a brief, PR raised outside WUWEI, gate miss at raise) must block with enforce on. | Resolved. `_unbriefed`, `pr.py:249` and `shepherd.raise_pr` refuse by default, with red tests first (T003, T004). |
| C1 | Constitution | HIGH | VII | VII names observe, guarded and strict; leaving it would contradict the code. | Resolved. T011 amends VII to the switch and the floor, version 2.2.0. |
| B1 | Behaviour change | HIGH | Assumption 2 | Workspaces on the guarded default get new blocks: seat launch refusals (including CAP, host seat ceiling, free memory, missing ticket), the outward lint and unknown outward tool, scratch, a bare `gh pr create` for a recorded item. | Accepted and documented. The pass plan's table asks the launch and PR raise rows to block; the rest name their accepted form. CAP and host seat refusals are flagged for part 17 (log only). |
| S1 | Scope | HIGH | issue "floors go" | Keeping a floor might read as keeping posture floors. | Resolved (Assumption 1). The config floors and areas go; one constant keeps the constitution floor, read only by the hook. |
| U1 | Upgrade | HIGH | FR-007 | `_unread_keys` removes the retired keys before any mapping could read them. | Resolved. `_enforce` reads `before` (the file as loaded), the way `_today_tier` does, and never overrides an explicit `guards.enforce`. |
| T1 | Telemetry | MEDIUM | 5.13 | The owner keeps telemetry untouched, but it reads `workspace.posture`. | Resolved. The record keeps `config.posture`, mapped from the switch (`guarded` or `observe`), so stored weeks and the collector validate. |
| R1 | Reasons | MEDIUM | tests/test_reasons.py | Removing strict branches removes three `tracker.py` LEFT row texts; the stale check fails unless the rows go. | Resolved in T009. |
| D1 | Docs | MEDIUM | docs/site, README | Posture text stays in pages no test reads. | Deferred to part 24 per the pass plan; plan.md lists every page and line. |
| X1 | Tests | MEDIUM | about 48 files | Posture writers are per-file helpers. | Resolved in plan.md: one rule per file (enforce = false for observe cases, strict cases deleted with their branch). |
| L1 | Signals | LOW | signal.py | `guard.would_refuse` loses the posture field the signal tier read. | Resolved: silent; `traces.unmatched` warns. Only the report reads pages. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 schema | yes | T002 |
| FR-002 RETIRED | yes | T002 |
| FR-003 FLOOR | yes | T001, T002 |
| FR-004 hook | yes | T001, T002 |
| FR-005 readers | yes | T003, T004, T009, T010 |
| FR-006 traces | yes | T005, T006 |
| FR-007 upgrade | yes | T007, T008 |
| FR-008 init flags | yes | T007, T008 |
| FR-009 governance | yes | T011 |
| FR-010 reasons | yes | T009 |

**Constitution Alignment Issues**: VII, resolved by T011.

**Unmapped Tasks**: none.

**Metrics**: 10 requirements, 12 tasks, 100% coverage; 0 open CRITICAL or HIGH.

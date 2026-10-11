# Specification Analysis Report: 832-setup-profiles-out

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.1.0);
- the #789 pass plan (owner constraints, "Process control kept", outward duties, #831 handoff);
- the code and tests at 9639dd8.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Process control | CRITICAL | FR-001 | CAP and the seat ceiling are (b) process control. A rewrite during the move could let a launch past CAP. | Resolved. The functions move unchanged except one unmeasured text, the host tests move first and stay green (T001, T002), and every caller is named. |
| P2 | Owner constraint | HIGH | `next` rows, doctor fixes | The old `next` setup rows and doctor fixes sent the owner to a host terminal. A replacement must not. | Resolved. `no-workspace` runs `bin/wuwei init --shadow`; `setup` runs `config add-repo`, which asks its Owner step card. The part 12 LEFT rows in `test_reasons` go, and no new row is added (T003, T011). |
| P3 | Dead end | HIGH | `next` calibration gate | If `next` kept gating on `calibration.json` and offered `config promote`, an owner who answers No on its card would stall the day. | Resolved. The gate goes (Assumption 4); `doctor` warns instead. |
| C1 | Coverage | HIGH | `tests/test_calibrate.py` command tests | Some calibrate command tests are the only cover of survey lines `config promote` keeps (Flagged, CI only). Deleting them would lose cover. | Resolved. T007 and the plan port any such case to `config promote` instead of deleting it. |
| T1 | Test budget | HIGH | `tests/test_tone.py` cards class | Removing the interview texts changes the measured rate; the budget must never rise. | Resolved in tasks: re-measure, fix card text if needed, never raise the budget (T012). |
| H1 | Hook path | MEDIUM | `guards/agent_launch.py` | The launch guard now imports `dispatch` lazily instead of `calibrate`. `test_hooks` dumps hook-path module sets. | Accepted. The same guard already imports `dispatch` lazily (248, 451), and it is lighter than `calibrate`. T002 runs `tests/test_hooks.py`. |
| B1 | Behaviour change | MEDIUM | `build._repo` under strict | A strict repository without fast checks now builds. | Accepted and documented (Assumption 5, US4.5): the refusal only asked a card; CI and the gates stay the evidence. |
| B2 | Behaviour change | MEDIUM | allowlist writer | New workspaces get no permission allow rules written. | Accepted (Assumption 6, Risks). Not a guard. |
| D1 | Constitution | LOW | design spec edits | The design spec is amended only by its owner. | Resolved: part of the owner-approved #789 pass. |
| S1 | Scope | LOW | `--from-card` | `card_write`, `_from_card`, `assignment` and `declared` move, but belong to decision cards. | Accepted: part 14 deletes them (Handoff). |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 host moves into dispatch | yes | T001, T002 |
| FR-002 modules deleted, edit frame moved | yes | T005, T006 |
| FR-003 calibrate trimmed | yes | T006, T007 |
| FR-004 promote without answers or profiles | yes | T007 |
| FR-005 next rows | yes | T003, T004 |
| FR-006 doctor rows | yes | T009 |
| FR-007 strict builds without fast checks | yes | T010 |
| FR-008 dead writers and detectors | yes | T006 |
| FR-009 texts, LEFT rows, docs | yes | T011 to T014 |

**Constitution Alignment**: I, II, III and V hold. IV holds (red tests T001, T003, T007,
T009, T010). VII holds: no guard and no owner card is removed.

**Unmapped Tasks**: none.

**Metrics**: 9 requirements, 15 tasks, coverage 100%. 1 critical and 4 high findings, all
resolved.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.

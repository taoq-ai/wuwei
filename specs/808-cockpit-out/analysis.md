# Specification Analysis Report: 808-cockpit-out

Artifacts read: spec.md, plan.md, tasks.md, `.specify/memory/constitution.md` (1.5.0), the
#789 pass plan (part 5, no detail section), and the code at main `221f1f2`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| C1 | Constitution | CRITICAL (resolved) | spec FR-010, Assumptions "Design spec"; plan docs section | Design 5.9, 4.2, 5.11, 5.12 and section 8 describe the cockpit, menu bar, briefings and board; the constitution lets only the owner amend the design spec. | #789 is the owner's instruction; each passage is marked retired "(owner, 2026-10-11, #789)", as parts 4 and 7 do. |
| U1 | Underspecification | HIGH (resolved) | plan "Rename and trim"; tasks T009 | `tests/test_brief_pack.py` holds the only ICS parser tests and the only `say` adapter test; deleting the file whole would leave the kept calendar port (read by `status`) untested. | The file is renamed `tests/test_calendar_tts.py` and keeps its four adapter cases. |
| U2 | Underspecification | HIGH (resolved) | spec Assumptions "tts and transcripts", Deferred | Removing the now-unused `tts` and `transcripts` ports changes `telemetry.ADAPTERS`; `telemetry.validate` would then reject a stored week that names `tts`, and `tests/test_telemetry.py` pins `ADAPTERS` to the schema. Telemetry is the owner's. | The ports stay; their removal is deferred to a follow-up issue with a telemetry schema step; FR-012 forbids telemetry edits here. |
| I1 | Inconsistency | MEDIUM (resolved) | issue acceptance; spec FR-011; plan "RETIRED at rebase"; tasks T005, T015 | The acceptance says `init --upgrade` removes the retired keys via `RETIRED`, which #799 adds and the base lacks. | The two keys are listed for the lead to add after #799; T005 adds them if the rebased base has `RETIRED`. |
| I2 | Inconsistency | MEDIUM (resolved) | pass plan "edit docs/site only where a test forces it"; issue acceptance | The acceptance requires no docs page to mention the cockpit. | The issue acceptance governs; docs change at sentence level; part 24 rewrites the site. |
| G1 | Coverage | MEDIUM (resolved) | FR-008; tasks T002 | The doctor own-server row had only a positive test that injected a fake server. | The test asserts no own-server rows and fails before T003. |
| G2 | Coverage | MEDIUM (resolved) | FR-001, FR-002, FR-005; tasks T002 | Deleting commands had no test that they are gone. | One CLI case: `brief pack` exit 2, three commands refused by argparse, no `mcpServers`. |
| R1 | Risk | MEDIUM | plan "Risks"; tasks T001 | Part 4 (#801) edits `board.py`, `dashboard.py`, the SwiftBar files and `test_signal_status.py`; part 3 rewrites GROUPS and the command sets. | T001 rebases first; conflicts in deleted files resolve by deleting; conditional edits are marked. |
| R2 | Risk | LOW | spec Edge Cases | `brief.pack` and `brief.answer` events already in today's log fall to the unknown-kind tier on the upgrade day. | Accepted: one day, no gate reads the tier. |
| R3 | Risk | LOW | spec Edge Cases | Before #799 an unknown key raises under strict; a strict config with `brief.lead_minutes` would not load. | Merge order puts part 2 before part 5. |
| A1 | Ambiguity | LOW | spec Assumptions "Signal module stays" | "Phone status signal command" could mean the classifier module. | It is `wuwei signal classify`; the module stays because `status` reads it. |
| A2 | Ambiguity | LOW | tests/test_mcp.py | A fixture server named `cockpit` remains. | It models a third party server for the registry gate (part 18); only a stale comment changes. |
| C2 | Constitution | LOW | constitution Workflow (9.2 invariant rule) | The rule applies to guard and decision-rule changes. | None here; no invariant row. |

No CRITICAL or HIGH finding is open.

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T002, T007, T009 |
| FR-002 | T002, T003 |
| FR-003 | T007 |
| FR-004 | T007 |
| FR-005 | T002, T004 |
| FR-006 | T002, T005 |
| FR-007 | T009 |
| FR-008 | T002, T003 |
| FR-009 | T012, T013, T014 |
| FR-010 | T013 |
| FR-011 | T005, T015 |
| FR-012 | T014 (`tests/test_telemetry.py` runs unchanged) |
| FR-013 | T008, T009 |

## Metrics

- Requirements: 13; with at least one task: 13.
- Unmapped tasks: none (T001, T006, T010, T011 are setup, runs and comment cleanup).
- Open CRITICAL or HIGH: 0.

# Specification Analysis Report: 801-nudges-out

Artifacts read: spec.md, plan.md, tasks.md, `.specify/memory/constitution.md` (1.5.0), the
#789 pass plan (part 4), and the code at main `bfbf6a3`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| C1 | Constitution | CRITICAL (resolved) | spec Assumptions "Design spec"; plan "Not edited" | Design 5.9 defines a `nudge` tier; the constitution lets only the owner amend the design spec and says a conflict is raised, not resolved silently. Deleting the tier conflicts with 5.9. | #789 is the owner's instruction: the design spec is amended to match, each passage marked (owner, 2026-10-10, #789). |
| U1 | Underspecification | HIGH (resolved) | spec FR-004, Assumptions "Rename, not collapse" | Folding `nudge` into `silent` would zero the doctor `traces` and `untraced subagents` counts and the `status` phone-answer, changed-PR and trace-gap counts, which read non-page `scan` rows. | Tier renamed `warn`; those readers keep working unchanged; T008 and T009 keep their tests. |
| U2 | Underspecification | HIGH (resolved) | spec FR-007, US2 scenario 3; tasks T002, T004 | A `pr.action` episode stored today as `tier: nudge` would fail the episode check after an upgrade and leave that PR unmeasured for the day. | The check also accepts the legacy `nudge`; one new test in T002 proves it. |
| I1 | Inconsistency | HIGH (resolved) | spec Assumptions "Docs"; plan docs section | The pass plan says edit docs/site only where a test forces it; the issue acceptance says docs do not mention nudges. | The issue acceptance governs this feature; docs change at sentence level only, and part 24 rewrites the site. |
| I2 | Inconsistency | MEDIUM (resolved) | pass plan part 4 detail vs spec FR-003 | The pass plan lists `attention()` among the things to touch. `attention` is read by the SessionStart phone-answer lines and the board. | `attention` and `scan` stay as the one view; only the list layers go. |
| G1 | Coverage | MEDIUM (resolved) | FR-013; tasks T008, T016 | The board's pages-only Attention table had no planned test. | `tests/test_board_mcp.py:102-104` counts pages only; dashboard and SwiftBar tests are updated in T008. |
| G2 | Coverage | LOW | FR-010; T019 | The two `obligations.py` refusals have no text test of their own. | The reason-corpus lint (`tests/test_invariants.py`, `tests/test_reasons.py`) runs over them; T020 runs both. |
| R1 | Risk | MEDIUM | plan "Risks"; tasks T001, T016, T017 | Parts 5 and 7 delete files this feature edits (board, dashboard, SwiftBar, listener, control plane); part 3 deletes `guide.py`, GROUPS and READ_ONLY/WRITES. | T001 rebases first; T016, T017 and T019 skip files a merged part removed. |
| A1 | Ambiguity | LOW | plan docs section | "Reword" is open-ended across about 50 doc lines. | One rule given: delete for deleted surfaces, "a warning in the event log" for kept events, `bin/wuwei doctor` where it listed pages. |
| C2 | Constitution | LOW | constitution Workflow (9.2 invariant rule) | The rule applies to guard and decision-rule changes. | No guard or decision rule changes (classification feeds no guard); no invariant row. |
| D1 | Duplication | LOW | tasks T009 | Four `scan` cases move from the deleted file. | Moved, not copied; the source file is deleted in T010. |

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T010, T011 |
| FR-002 | T012, T013 |
| FR-003 | T008, T012 |
| FR-004 | T002, T003, T005 |
| FR-005 | T008, T012 |
| FR-006 | T008, T015 |
| FR-007 | T002, T004 |
| FR-008 | T006 |
| FR-009 | T017 |
| FR-010 | T019 |
| FR-011 | T013, T014, T021 |
| FR-012 | T021, T022, T024 |
| FR-013 | T008, T016 |

Unmapped tasks: T001 (setup), T007, T020, T023 (test runs), all intended.

## Metrics

- Requirements: 13 functional, 3 success criteria; coverage 100 percent.
- Findings: 1 CRITICAL, 3 HIGH, 4 MEDIUM, 3 LOW. Every CRITICAL and HIGH is resolved in the
  artifacts.

## Next actions

Ready for `speckit-implement` once parts 1 to 3 have merged (T001). Design 5.9 is amended under
the owner's #789 instruction (C1).

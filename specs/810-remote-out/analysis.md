# Specification Analysis Report: 810-remote-out

Artifacts read: spec.md, plan.md, tasks.md, `.specify/memory/constitution.md` (1.5.0), the
#789 pass plan (part 7; it has no detail section for this part), and the code at main
`221f1f2`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| C1 | Constitution | CRITICAL (resolved) | spec FR-017, Assumptions "Design spec"; plan docs section | Only the owner amends the design spec; this feature edits section 15 and eight other passages. | The issue acceptance and #789 are the owner's instruction; every edit is marked "(retired by #789, owner, 2026-10-10)". |
| C2 | Constitution | HIGH (resolved) | plan Constitution Check; tasks T024 | The Constraints section names the listener as one of two long-running processes; leaving it contradicts the code, editing it is an amendment. | Amend to the watch only, patch version bump, Last Amended 2026-10-11; the dated commit line is the lead's. |
| U1 | Underspecification | HIGH (resolved) | spec US3; plan init.py; tasks T007, T008 | An owner with `wuwei listen install` keeps a launchd or systemd unit that restarts a command that no longer exists. | `init --upgrade` stops and removes the unit through `commands/watch._remove`, with a dry-run line and a test first. |
| U2 | Underspecification | HIGH (resolved) | spec FR-005; tasks T005, T006 | A wake marker written today with only an `inbox` count would make `watch.wake` raise "empty planner wake marker" at every SessionStart once the inbox code goes. | Such a marker reads as no wake; test first. |
| U3 | Underspecification | HIGH (resolved) | spec US2; tasks T003, T004 | `watch.tick` skips its PR poll while a `listen: clock` is fresh; removing the listener without changing `tick` would stop PR polling on the upgrade day. | `watch.listening` goes and `tick` polls whenever due; test first. |
| I1 | Inconsistency | HIGH (resolved) | pass plan "Edit docs/site only where a test forces it" vs issue acceptance | The acceptance requires no docs page to name these units. | The acceptance governs; sentence-level deletions only, part 24 rewrites the site. |
| A1 | Scope | MEDIUM (resolved) | spec Assumptions "Headless shepherd"; plan units table | The issue does not name the headless shepherd or the runtime `headless` function. | Their only callers are the listener tick and the remote turns, and their only tests are in `tests/test_listen.py`; keeping them leaves dead code and an unread `shepherd.autostart`. Deleted here; the #511 overnight shepherd stays. |
| U4 | Underspecification | MEDIUM (resolved) | spec US4; plan setup.py | `setup slack` derived `outbound.owner.slack.user` from the pinned inbound sender. | Setup prints the `config set` command when the key is empty. |
| U5 | Underspecification | MEDIUM (resolved) | spec Edge Cases, Assumptions "Leftover event kinds" | Kinds removed from `signal.SILENT` that were written earlier on the upgrade day fall to the default tier. | The default is non-page; after part 4 warnings are not surfaced. No legacy tuple. |
| G1 | Coverage | MEDIUM (resolved) | tasks T002 | `tests/test_listen.py` holds generic wake and SessionStart tests (#346, #562). | Moved to `tests/test_watch.py` before the file is deleted. |
| R1 | Risk | MEDIUM | plan Risks; tasks T001, T020 | Parts 1, 3, 4, 5, 6 edit `status.py`, `doctor.py`, `signal.py`, `telemetry.py`, `protect_state.py`, GROUPS, WRITES and `tests/test_docs.py`. | T001 rebases first; T020 and T023 skip what earlier parts removed. |
| B1 | Rule of the pass | LOW | plan units table | `WUWEI_SEAT_ROLE == 'shepherd'` refusals lose their only setter (the headless seat). | Kept as (b): they stop a seat from merging or sending; parts 17 and 23 decide their fate. |
| G2 | Coverage | LOW | spec FR-011 | `where` stays in `owner_outcome` and `undo` without a production caller. | Tests use it as the confirmation seam; part 14 deletes decide. Only the DM branch and its test go. |
| D1 | Duplication | LOW | plan tests section | `tests/test_docs.py` remote tests may already be gone after part 1. | T023 skips them. |

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T013 |
| FR-002 | T015 |
| FR-003 | T015 |
| FR-004 | T003, T004 |
| FR-005 | T005, T006 |
| FR-006 | T014 |
| FR-007 | T016 |
| FR-008 | T016, T017 |
| FR-009 | T015, T018 |
| FR-010 | T011, T012 |
| FR-011 | T017 |
| FR-012 | T017 |
| FR-013 | T009, T010, T015 |
| FR-014 | T007, T008, T026 |
| FR-015 | T022 |
| FR-016 | T023, T025 |
| FR-017 | T024 |

Unmapped tasks: T001 (setup), T002 (test move), T019, T020, T021 (cleanup and grep), T027
(final run), all intended.

## Metrics

- Requirements: 17 functional, 3 success criteria; coverage 100 percent.
- Findings: 1 CRITICAL, 5 HIGH, 5 MEDIUM, 3 LOW. Every CRITICAL and HIGH is resolved in the
  artifacts.

## Next actions

Ready for `speckit-implement` after the earlier parts merge (T001). The lead adds the RETIRED
keys after #799 merges.

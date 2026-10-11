# Tasks: tracker lifecycle updates become outward duties; the ticket walls go

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at d60253b8.
Parts 16 to 19 are on the branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task.

## Phase 1: The walls go (US1, P1)

- [X] T001 [US1] Red: one test per US1 scenario, in `tests/test_build_next.py`,
  `tests/test_dispatch.py`, `tests/test_agent_launch.py`, `tests/test_pr_actions.py`,
  `tests/test_plan.py`, `tests/test_intraday_intake.py` (owner `plan add`) and
  `tests/test_stop.py` (close with a ticketless merged item). Run: red.
- [X] T002 [US1] Delete `tracker.check`, `in_force` and their callers' refusals, the
  auto-create, `_skipped`, the `CAPACITY` text; doctor rows. Delete the wall tests plan.md
  lists. Run the T001 files plus `tests/test_tracker.py tests/test_enforce.py
  tests/test_doctor.py tests/test_hooks.py`: green.

## Phase 2: Duties (US2, US3, P1)

- [X] T003 [US2] Red: `tests/test_dispatch.py` (`duty.due`/`duty.done`, comments, no ticket no
  duty), `tests/test_tracker.py` (`open_duties`, `_entries` without link and merged entries,
  fold category, `move claim`), `tests/test_shepherd.py` (`pr claim` runs in-review),
  `tests/test_merge.py` (done duty). Run: red.
- [X] T004 [US2] `dispatch.tracker_call`, `tracker.open_duties`, `tracker._entries`,
  `tracker.log`, `shepherd.claim_pr`, `commands/tracker.py`, `event.py`, `signal.py`. Run the
  T003 files plus `tests/test_signal_status.py tests/test_linear_loop.py
  tests/test_build_next.py tests/test_watch.py`: green.
- [X] T005 [US3] Red: `tests/test_next.py` (duty row, merged item, `rows`, tracker none) and
  `tests/test_stop.py` (close waits and names the command, clears after `tracker move`). Run:
  red.
- [X] T006 [US3] `commands/next.py` (`_seen`, `step`, finding text), `closing.unresolved`,
  `commands/close.py` comment. Run the T005 files plus `tests/test_close_parked.py
  tests/test_path_day.py tests/test_e2e_day.py`: green.

## Phase 3: Config and texts (US4, P2)

- [X] T007 [US4] Red: `tests/test_config_transition.py` retired keys. Then `workspace.py`,
  template, `relabel` text; delete the LEFT row. Update `tests/test_workspace.py`. Run
  `tests/test_config_transition.py tests/test_workspace.py tests/test_reasons.py
  tests/test_docs.py`: green.
- [X] T008 Charters (lead, planner), `bin/wuwei agents build`, design spec, docs site. Run
  `tests/test_charters.py tests/test_agents.py tests/test_docs.py tests/test_tone.py`: green.
- [X] T009 SC-001 grep; rerun every touched test file.

# Tasks: Headless shepherd

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (`acme/widget`, logins `ada` and `bob`, item `A`), built on
`case`, `own`, `REF` from `tests/test_stop.py`. New tests go in
`tests/test_headless_shepherd.py` unless a task names another file. Every headless test uses
a runtime fake that fails the test on any call (SC-002).

## Phase 1: the owning day (FR-001, FR-002)

- [X] T001 Test: with `workspace._DAY` unset `day_dir` is `days/<WUWEI_NOW date>`; set to
  a name it returns that day; reset it returns today again.
- [X] T002 Implement `_DAY` and the one-line `day_dir` change in `cli/wuwei/workspace.py`.
- [X] T003 Test: `shepherd.owning_day` returns today when today's state has
  `gate_approved`; after midnight with no state for today (or today's state written by a
  session but not approved) it returns yesterday's directory; with no day holding a
  `state.json` it returns None.
- [X] T004 Implement `owning_day` in `cli/wuwei/shepherd.py`.

## Phase 2: the sweep (FR-003 to FR-006, US1, US2, US3)

- [X] T005 Test (edge): a live planner on today's state, and separately on the owning day's
  state, makes `overnight` return 0, print `shepherd: planner live`, and write no event and
  no `overnight.md`; `evaluate`, `merge` and the ping recorder are never called. A run whose
  `pr_actions.evaluate` raises leaves `workspace._DAY` None.
- [X] T006 Test (edge): no owning day, and an owning day with no owned PR, return 0 with
  `shepherd: no owned PRs` and write nothing.
- [X] T007 Implement `_live` and steps 1 to 4 of `overnight` (pin set and reset in
  `finally`).
- [X] T008 Test (US1.1): yesterday approved, PR approved at head, `WUWEI_NOW` 02:00 today,
  `merge.check` and `merge.execute` recorders returning `Result(0, ...)`: one execute call;
  one `shepherd.overnight` `{pr, state: approved, outcome: merged}` and one `shepherd.swept`
  in yesterday's `events.jsonl`; none in today's; `days/<yesterday>/overnight.md` lists the
  PR as merged; exit 0.
- [X] T009 Test (US1.2): `merge.check` returns `Result(1, None, 'merge policy: merge.auto is
  off; ...')`: no execute call; event `outcome: queued` with that reason; exit 1.
- [X] T010 Test (US1.3 and edge): a second sweep with nothing changed writes no second
  `shepherd.overnight`, makes no second execute call, and a PR whose last outcome is
  `merged` is not re-checked; a PR the fake host reports merged gives one `outcome: merged`.
- [X] T011 Implement steps 5 to 8 of `overnight` for `approved`, `merged`, the dedup and the
  exit and summary in `cli/wuwei/shepherd.py`.
- [X] T012 Test (US2.1): an unanswered review thread by `bob` on `src/app.py` at night:
  no `reply` or comment call on the fake code host, no draft in state, no decision file, no
  runtime call; event `outcome: queued`, `state: threads_unanswered`, evidence line
  `thread <id> by bob on src/app.py: <text>`.
- [X] T013 Test (US2.3): `ci_red` evidence names the red check and conclusion; `conflicted`
  gives `conflicts with its base`; `changes_requested` gives the review line; no
  `builds` change, no brief file, no rebase call on the fake vcs.
- [X] T014 Test (`tests/test_pr_actions.py`): the existing thread tests still pass after the
  lookup moves; one new assert that `pr_actions._latest` finds a `bot-p1` thread's last
  comment.
- [X] T015 Implement `pr_actions._latest` (extracted from `_thread`, used there) in
  `cli/wuwei/pr_actions.py`, and `_evidence` plus the queued branch in `overnight`.
- [X] T016 Test (US3): `review_stale` calls the ping recorder once; recorder exit 0 gives
  `pinged`; recorder printing `outward: draft ...` and exit 1 gives `queued` with that text;
  exit 2 gives `unmeasured` and the sweep exit is 2.
- [X] T017 Test (edge): one PR unreadable (fake host error) and one approved: the unreadable
  one is `unmeasured` with the reason, the other is still acted on, exit 2.
- [X] T018 Implement the `review_stale` and unmeasured branches in `overnight` (reuse
  `wuwei.commands.doctor._capture`).
- [X] T019 Test (FR-006, `tests/test_headless_shepherd.py`): `bin/wuwei event
  shepherd.overnight '{}'` and `shepherd.swept` are refused as producer-only.
- [X] T020 Implement the two `EVENT_PRODUCERS` rows in `cli/wuwei/commands/event.py`.

## Phase 3: the morning report (FR-007, FR-008)

- [X] T021 Test: `overnight_lines` on a day with no `shepherd.overnight` event is `[]`; on a
  day with merged, pinged and two queued PRs it prints the heading with the sweep count and
  last time, every event in order, and a Morning queue holding only the two queued PRs,
  oldest first, numbered from 1, each with its evidence lines and `Run: wuwei pr act <pr>`;
  a PR queued then merged is not in the queue.
- [X] T022 Implement `overnight_lines` in `cli/wuwei/shepherd.py` and make `overnight` write
  `overnight.md` with it.
- [X] T023 Test (US1.1, US1.2, US2.2, US5.3, `tests/test_plan.py`): after the night sweep of
  T009 and T012, `plan.propose` on the new day writes `plan.md` whose first section after
  Status is `## Overnight`, before `## Goals to confirm`, and whose queue item 1 is the
  first queued PR with its thread line; with no overnight event on the prior day the
  `plan.md` text equals the text before this change (no Overnight section).
- [X] T024 Implement the one-line insertion in `plan.propose` (`cli/wuwei/plan.py`).

## Phase 4: running it (FR-009, FR-010, US4)

- [X] T025 Test (FR-009, `tests/test_cli.py` style through `main`): `sweep obligations
  --headless` runs one sweep and returns its exit; a held `.wuwei/shepherd.lock` gives exit
  2 with `another shepherd holds the workspace lock`; `sweep obligations` without the flag
  prints and exits as before.
- [X] T026 Implement `shepherd.loop` and the `--headless` flag in
  `cli/wuwei/commands/sweep.py`.
- [X] T027 Test (US4.2, US4.3, pattern of `tests/test_listen.py:337-360`): in a host
  terminal, `shepherd schedule --dry-run` prints a unit labelled `wuwei-shepherd-` that runs
  `bin/wuwei shepherd`; `shepherd schedule` on linux writes the unit and calls the fake
  service; `shepherd unschedule` removes it.
- [X] T028 Test (US4.1): with `WUWEI_SESSION_ID` set, `shepherd schedule` exits 1, writes no
  unit, makes no service call and prints one JSON line with `action: owner_terminal`,
  `command: bin/wuwei shepherd schedule`, `why`, `then`, and a `widget` whose header is
  `Shepherd`, whose question starts with the morning gate citation and whose first option is
  `Schedule (Recommended)`; without today's `plan.md` the `widget` key is absent;
  `shepherd unschedule` in a session prints its action and exits 1; `--dry-run` in a session
  prints the unit.
- [X] T029 Test (US4.4): `shepherd.loop` passes `HEADLESS_SECONDS` (900) and the name
  `shepherd` to `watch.serve` (monkeypatched recorder); `once=True` passes 0 and `once`.
- [X] T030 Implement `cli/wuwei/commands/shepherd.py`, `GROUPS` in `cli/wuwei/__main__.py`
  and `WRITES` in `cli/wuwei/commands/__init__.py` (run `tests/test_cli_known_command.py`
  first to see the paths it requires).

## Phase 5: doctor and docs (FR-011, FR-012, US5)

- [X] T031 Test (US5.1, US5.2, `tests/test_doctor.py`): no unit and no sweep gives an ok
  `shepherd` row `runs only in a session; bin/wuwei shepherd schedule runs it overnight` and
  the same doctor exit as before; a unit file at `workspace.watch_unit(root,
  name='shepherd')[1]` and a `shepherd.swept` event give `scheduled (...), last swept
  <ts>`; installed with no event gives `last swept not yet`.
- [X] T032 Implement `shepherd.last_swept` and the row in `_day`
  (`cli/wuwei/commands/doctor.py`).
- [X] T033 Test: run `tests/test_docs.py` and `tests/test_cli_known_command.py` after T030;
  a failure naming `shepherd` (command groups, reference rows) is the failing test for T034.
  Add one assert in `tests/test_docs.py` that design 4.2.1 contains `#511` and
  `sweep obligations --headless`.
- [X] T034 Write the `bin/wuwei shepherd` row and the Doctor Day list entry in
  `docs/site/reference.md`, and the dated 4.2.1 bullet in
  `docs/specs/2026-09-24-wuwei-design.md`.

## Phase 6: finish

- [X] T035 Run `python -m pytest -q` from the repository root; everything passes with no
  existing assertion changed (SC-003). Check every written file for em-dashes and emojis.

## Phase 7: review fixes (`_pipeline/review/511-findings.md`)

- [X] T036 F1: `shepherd.overnight` and `shepherd.swept` are silent in `cli/wuwei/signal.py`
  and in `test_emitted_kinds_have_intended_tiers`.
- [X] T037 F2 test then fix: `owning_day` is the newest approved day (today included), so
  unapproved watch clock days never own the sweep; `plan.propose` renders the overnight
  report of the newest earlier approved day and `last_swept` reads the owning day
  (`test_the_weekend_sweep_skips_unapproved_clock_days`, the plan and doctor tests).
- [X] T038 F3 test then fix: in a session `shepherd schedule` returns `action: ask` with the
  Shepherd card and the record command `bin/wuwei shepherd schedule --yes`, which installs;
  `unschedule` removes directly; only strict returns `owner_terminal`.
- [X] T039 F4 test then fix: until #524 is on main an approved PR gets `merge.check` only and
  is queued (`merge cleared by policy; merge waits for the morning (#524)` when it clears);
  no `merge.execute` at night. Supersedes the merge outcome in T008, T010 and T011.

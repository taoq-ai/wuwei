# Tasks: The CLI owns the path and the model walks it

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Fixtures are neutral (`tests/test_next.py` helpers, `fakes.day.Day`,
items `A`, `ITEM-1`..). Row numbers refer to the state table in `plan.md`.

## Phase 1: one action shape (FR-001, FR-007)

- [X] T001 Test in `tests/test_next.py`: every existing row (setup, decision, build, verdicts,
  pr, dispatch, wait, doctor, unmeasured) has keys `state`, `action`, `why`, `then` and no
  `step`; `wuwei next` without `--json` prints `<state>: <why> <then>` and the command on its
  own line; the unmeasured row still exits 2 with `wuwei next:` on stderr. Update the
  existing shape asserts in the same file.
- [X] T002 Implement `_row`, `THEN`, `text` and the plain print in
  `cli/wuwei/commands/next.py`; switch the fallback row in `cli/wuwei/guards/lifecycle.py`
  to `next_command._row`.

## Phase 2: the morning path (US1.1, FR-002, FR-003, FR-005, FR-006)

- [X] T003 Test in `tests/test_next.py`: rows 1 to 10. No workspace and setup are `card`
  rows with the host command; no planner session gives `wuwei plan session S` with
  `WUWEI_SESSION_ID=S` and `<session id>` without it; with a session, `pr-flow` then `mcp`
  (each once: the second call moves on); the lead brief command is exact and contains no
  `<`; with `briefs/lead.md` written the action is `launch` with the fields
  `brief.seat_action('lead', ...)` returns; a running `lead` seat gives `wait`; `lead.json`
  gives the propose command; `plan.md` without approval gives a `card` whose `widget` equals
  `wuwei plan gate`'s printed list and which repeats on the next call. No row's text holds
  `/wuwei:`, `SKILL.md` or the word skill.
- [X] T004 Test in `tests/test_next.py`: each returned action appends one `next.action`
  event with `state`, `action`, `item`, `named` (the gate row includes the propose command)
  and `traces` (the line count of `traces.jsonl`); nothing is written outside a workspace or
  without day state; `wuwei event next.action` and `wuwei event day.closed` are refused as
  reserved (`tests/test_cli.py` style, exit and message).
- [X] T005 Implement rows 3 to 10, `_seen`, the lead and gate parts of `resolve`, `named`,
  the event append in `run`, and `LEAD_BODY` in `cli/wuwei/commands/next.py`; add both kinds
  to `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py`.
- [X] T006 Test in `tests/test_next.py`: after approval, a provisional `goals.md` gives the
  `goals edit` row once; the first day gives the `calibrate` card once, and a `[]` widget is
  passed in the same call (the event records it under `passed`, and the call returns the
  next due row); `telemetry` likewise; a decision card is returned once per D-n and the next
  call moves on to the item rows.
- [X] T007 Implement rows 11 to 14, `_widget` and the passed-state loop in
  `cli/wuwei/commands/next.py`.

## Phase 3: gate seats and starts at the shared spot (US1.3, US1.4, FR-009)

- [X] T008 Test in `tests/test_dispatch.py`: an item at `gate` with no gate brief gives
  `gates` with `commands` holding one exact `wuwei brief <role> A <role>-A --gate --worktree
  <path> --body ...` per role; a stopped sentinel with no received verdict adds its
  `receive`; a delta seat stopped after its continue adds `receive ... --round delta`; no
  `commands` key when there is nothing to run. Update the exact `gates` asserts in
  `tests/test_dispatch.py` and `tests/test_e2e_day.py` (`:29`, `:202`) with the expected
  `commands`.
- [X] T009 Test in `tests/test_dispatch.py` (`:1473` and a new case): a `start` entry holds
  `wuwei worktree add P3` and `wuwei brief builder P3 builder-P3 --worktree worktrees/P3
  --body ...` with the proposal's scope and evidence; with `worktrees/P3` present only the
  brief command remains; no `<name>` or `<path>` placeholder.
- [X] T010 Implement `_seats`, `next_step` and `launch_set` changes and `GATE_BODY` in
  `cli/wuwei/dispatch.py`.

## Phase 4: delegation for the day (US1.2, FR-003)

- [X] T011 Test in `tests/test_next.py`: a build-phase item returns `build.next_action`'s
  `launch` unchanged with `then` `agent`, a `check` with `then` `background`; a build
  `done` or `park` is never returned (the call asks the day again); a gate item returns
  `gates` with `then` `set`; `fix` is never returned; `raise` gives the shepherd brief
  command, then its `launch`, then (shepherd stopped, item still at gate) a `card` naming
  `wuwei why A`; `escalate` gives `wuwei plan park A --reason "..."`; planned items give the
  `set` of `dispatch.launch_set`; `stuck` gives the exact `--unmeasured` command; a
  delegate's refusal exits 1 with the reason as `why`.
- [X] T012 Implement the delegated rows 15 to 20, `SHEPHERD_BODY` and the re-ask loop in
  `cli/wuwei/commands/next.py`.

## Phase 5: steward and close (US1.1, FR-010)

- [X] T013 Test in `tests/test_next.py`: a `steward.due` newer than the last run gives the
  background `steward run` row; a `steward.run` without a seat gives the steward `launch`;
  all items terminal gives `wuwei close`; then, with no close steward run, a pending owner
  decision card (repeating) or `wuwei close`; then `retro`, `promote` (once),
  `retro-applied` (once), `report` (with `outbound.owner_channel = "dm"` its `then` names
  the DM id), `wuwei close`, and `done` once a `day.closed` event exists.
- [X] T014 Test in `tests/test_report_retro.py`: plain `wuwei close` appends `day.closed` on
  exit 0 and not on exit 1.
- [X] T015 Implement rows 21 to 33 in `cli/wuwei/commands/next.py` and the `day.closed`
  append in `cli/wuwei/commands/close.py`.

## Phase 6: orientation (US3.3, FR-004, FR-008)

- [X] T016 Test in `tests/test_next.py`: the planner orientation holds `Next: ` plus
  `text(row)`, `LOOP`, `wuwei guide`, and `wuwei plan session S` on the session row; no step
  list and no `SKILL.md` path; seats keep their charter entry. Delete
  `test_steps_come_from_the_skill_file` and update `test_orientation_block`,
  `test_orientation_by_state`, `test_issue_acceptance_session_start_orients`. The
  SessionStart budget test and `tests/test_hooks.py` import pins stay unchanged and pass.
- [X] T017 Implement `orientation` and delete `steps()` in `cli/wuwei/commands/next.py`.

## Phase 7: path metrics (US4, FR-011)

- [X] T018 Test in `tests/test_metrics.py`: `metrics.path` over recorded events and trace
  lines: Stop count for the planner only; AskUserQuestion spans for the planner only;
  `off_path` lists a planner Bash command not named by the governing `next.action`, and
  not one that matches after the `wuwei` basename rule, a changed `--body` value, a
  `<label>` token, or `wuwei next`/`wuwei status --line`; spans of other sessions are
  ignored; no planner or no traces gives `unmeasured`. `collect` carries the three keys and
  the report's process metrics show them.
- [X] T019 Implement `path` and the `collect` keys in `cli/wuwei/metrics.py`.

## Phase 8: the fixture day (US2, FR-013)

- [X] T020 Extend `tests/fakes/day.py`: `Runtime.finish` for `lead` (returns the
  one-candidate proposal JSON) and `shepherd` (raises the PR with `day.raise_pr()`).
- [X] T021 Test `tests/test_path_day.py`: the loop of plan.md "Fixture day" drives the day
  from no plan to `done`; asserts A merged, `day.closed`, retro and report present,
  `off_path == 0`, `planner_asks` equal to the cards answered, `planner_turns > 0`, and a
  bound on loop iterations and time. Run it; fix what it reveals in the production files
  named in Phases 1 to 7 only.

## Phase 9: skills, charter, guide (US3, FR-012)

- [X] T022 Test: `tests/test_docs.py` asserts each of `skills/wuwei-plan/SKILL.md` and
  `skills/wuwei-report/SKILL.md` has fewer than 25 lines and names `launch`, `continue`,
  `resume`, `subagent_type`, `in one message`, `AskUserQuestion`, `record`; `guide.text()`
  holds `LOOP`, `outbound.owner_channel`, `outbound.owner.slack.dm`, `outbound learn
  --tool`, `--owner <file>` and not `config set outbound.owner`. Move the pins listed in
  plan.md "Existing tests that change" (`tests/test_docs.py`, `tests/test_charters.py`,
  `tests/test_parallel_dispatch.py`, `tests/test_intraday_intake.py`) to next rows, the
  guide or the charter.
- [X] T023 Rewrite `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md` and
  `charters/planner.md`; regenerate `agents/` with `bin/wuwei agents build`; update
  `cli/wuwei/guide.py` and regenerate the block in `docs/site/agent.md`; update the `next`
  row in `docs/site/reference.md`.

## Phase 10: the smaller-model eval (US4.3, FR-014)

- [X] T024 Test in `tests/test_headless_e2e.py`: `claude_command(plugin, model='haiku')`
  carries `--model haiku` and defaults to `sonnet`; `main(['--start', '--model', 'haiku'])`
  passes the model through (no network: patch `exercise`); `validate(..., start=True)` with
  traces holding one off-path planner command gives a finding naming it, and the named park
  command gives none.
- [X] T025 Implement `--model`, the traces load, the park command in `start_prompt` and the
  off-path finding in `scripts/headless_e2e.py` and `scripts/headless_adapter.py`; document
  the run in `docs/headless-e2e.md`.

## Phase 11: verification

- [X] T026 Run `python -m pytest -q` from the repository root; everything passes. Check the
  changed files for em-dashes, emojis and absolute local paths.

## Phase 12: review fixes

- [X] T027 Test and fix: a once-row is done when a Bash span since the last recorded action
  matches one of its named commands (recorded as `done`), or after three returns; plain
  `wuwei next` records no action; the path day closes when the planner asks next twice
  per action (`tests/test_next.py`, `tests/test_path_day.py`).
- [X] T028 Test and fix: the gate row adds `--import-yesterday` when the prior day left
  unfinished items the proposal does not name again; the guide holds the owner-only publish
  card, assume-and-record and the negotiation and question-note rules (`tests/test_docs.py`).
- [X] T029 Test and fix: an empty close card passes instead of holding next; only
  `wuwei next` and `wuwei next --json` are exempt from `off_path` (`tests/test_metrics.py`).

## Dependencies

Phase 1 before all. Phases 2 to 7 in order (each extends `next.py`); Phase 3 before Phase 4.
Phase 8 after Phases 1 to 7. Phase 9 after Phase 6. Phase 10 after Phase 7.

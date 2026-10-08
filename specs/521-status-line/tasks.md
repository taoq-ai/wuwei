# Tasks: status --line is one readable line, the detail moves to status

Test first: each test task is written, run and seen failing for the expected reason before its
implementation task. Fixtures are neutral: the `day` and `cli` helpers in
`tests/test_signal_status.py`, items `ITEM-1`.., seats named by role, versions `0.12.0`,
`0.15.0`. Run with `python -m pytest -q` from the repository root.

## Phase 1: the restart says what to do (US3, FR-007)

- [X] T001 Test in `tests/test_config_transition.py` (lines 185-193): `integrity.restart`
  returns `restart Claude Code: hooks 0.12.0 still running (plugin 0.13.0 installed)` for a
  newer template, `hooks 0.11.0 still running (plugin 0.12.0 installed)` for a marker, and
  joins three old versions as `a, b and c`; `''` when nothing is stale. Update
  `tests/test_doctor.py::test_in_use_row_names_the_restart` to the new text. Fails on the old
  text.
- [X] T002 Implement the new text in `integrity.restart` in `cli/wuwei/integrity.py`.

## Phase 2: the snapshot facts the line needs (FR-002, FR-008)

- [X] T003 Test in `tests/test_signal_status.py`: `status --json` carries `plan` (false, then
  true once `plan.md` is in the day directory), `decisions` (`['D-7']` for a routed decision
  with no outcome, `[]` once decided), `plugin` (the plugin manifest version) and `template`;
  every key it carried before is still there. Fails on the missing keys.
- [X] T004 Implement the four keys in `snapshot` in `cli/wuwei/commands/status.py`.

## Phase 3: one line, importance first (US1, FR-001 to FR-003)

- [X] T005 Test in `tests/test_signal_status.py` (acceptance 1): a day with `gate_approved`,
  four running seats `lead`, `arch`, `quality`, `security` on `ITEM-1` with start times, one
  live fast check, and `status.line({**data, 'restart': integrity-style text for 0.12.0 and
  0.15.0})`: the line is at most 100 characters, starts with `WUWEI restart Claude Code: hooks
  0.12.0 and 0.15.0 still running`, contains no `ITEM-1`, no `HH:MM` time, no `(plugin`, and
  every token on it is a whole token of the untruncated line.
- [X] T006 Test in `tests/test_signal_status.py` (acceptance 2): the same day without the
  restart gives exactly `WUWEI implement 1/1 · seats 4/1 (lead, arch, quality, security) |
  pages 0 · nudges 0` (phase counts as the fixture sets them; posture shown only when not
  guarded, `observe` in a second case); a gate approved with no seat gives `seats 0/<cap>`
  with no parentheses; the line has no `watch`, `listen`, `sessions`, `meeting`, `reply`,
  `running`, `loops`, `bound`, goal split.
- [X] T007 Test in `tests/test_signal_status.py` (acceptance 3 and 4): no `plan.md` and no gate
  starts `WUWEI no plan yet | pages 0 · nudges 0`; `plan.md` written and no gate starts `WUWEI
  gate waiting`; an approved gate with routed `D-7` pending starts `WUWEI decision D-7
  waiting`; restart beats all three. Update `test_no_plan_yet_before_the_gate`,
  `test_approved_gate_has_no_plan_yet_prefix`, `test_restart_on_the_status_line` and
  `test_status_line_shows_running_seats_per_goal` to the new shape.
- [X] T008 Implement `_groups`, `_render` and the new `line` in `cli/wuwei/commands/status.py`
  per plan.md; remove the moved parts from the line.

## Phase 4: width (US4, FR-004, FR-005)

- [X] T009 Test in `tests/test_signal_status.py`: for the four-seat day, `line(data, 70)`
  shows `(lead, arch, +2 more)`-style cuts and is at most 70; a width where even `(+4 more)` is
  too long drops work tokens from the right first, then attention tokens, never now, and keeps
  the first token; `line(data, 5)` returns the first token whole; `wuwei status --line --width 60`
  through the CLI prints at most 60 characters and exits 0; `wuwei status --line --width x`
  exits 2 (argparse).
- [X] T010 Implement the cut and drop loops in `line`, `--width` in `register`, and `width` in
  the fast path namespace in `cli/wuwei/__main__.py`.

## Phase 5: the full status (US2, FR-006)

- [X] T011 Test in `tests/test_signal_status.py` (US2 acceptance 1 and 3): `wuwei status` with
  no flag on the four-seat day with a stale plugin exits 0, prints first `WUWEI restart Claude
  Code: hooks ... still running (plugin ... installed)` (marker fixture as in
  `tests/test_config_transition.py`, or `status.full` with the restart text in process), then
  the work line, then four `running <role> ITEM-1 <HH:MM>` lines and one `running checks ITEM-1
  <HH:MM>` line, oldest first; a broken `state.json` prints `WUWEI ? unmeasured` and exits 2.
- [X] T012 Test in `tests/test_signal_status.py` (US2 acceptance 2): `status.full(data)` shows
  `watch <state>`, `listen <state>`, `health <h>` when set, `sessions N`, `phone answers N`,
  `loops N`, `prs N changed`, the solo text, `traces: N gaps`, `reply <due>`, `meeting <next or
  unmeasured>`, `bound <cap_bound>`, `builders <goal split>`, `plugin <v> · template <v>`.
- [X] T013 Move the existing asserts on moved parts to `wuwei status` / `status.full`, per the
  rule and list in plan.md "Existing tests that change": `tests/test_signal_status.py`,
  `tests/test_quiet_sweeps.py`, `tests/test_listen.py`, `tests/test_sessions.py`,
  `tests/test_remote.py`, `tests/test_traces.py`, `tests/test_watch.py`,
  `tests/test_heartbeat.py`, `tests/test_parallel_dispatch.py`,
  `tests/test_operator_records.py`, `tests/test_pr_actions.py`, `tests/test_shadow.py`,
  `tests/test_e2e_day.py`, `tests/test_setup.py`, `tests/test_board_mcp.py`. Run them and see
  them fail on the missing `status` output.
- [X] T014 Implement `full` and the no-flag branch of `run` (with the unmeasured line) in
  `cli/wuwei/commands/status.py`; make the output group not required in `register`.

## Phase 6: docs and the budget (FR-009, SC-002)

- [X] T015 Test: run `tests/test_hooks.py::test_status_line_skips_parser_and_hashlib` and
  `test_status_line_latency` unchanged (must pass); update the phrases in `tests/test_docs.py`
  that name `status --line` for a moved part to name `status` (for example `status --line`
  shows `listen dead`), and see them fail against the old docs.
- [X] T016 Update `docs/specs/2026-09-24-wuwei-design.md` (5.2, 5.3, 5.8.2, 5.9),
  `docs/site/reference.md`, `docs/site/daily.md` and `docs/site/configuration.md` per plan.md.
- [X] T017 Run the focused test files (the full suite runs in CI on the pull request); check every file written for em-dashes and emojis.

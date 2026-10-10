# Tasks: nudges.mode, off under autonomous

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process (`main([...])`, `status.snapshot`, `status.line`) with
`WUWEI_WORKSPACE` and `WUWEI_NOW` set and a day built from `tmp_path`, as
`tests/test_signal_status.py` does (`day`, `status_of`). Neutral fixtures only. Run the touched
test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the setting (FR-001, US3)

- [X] T001 Test in `tests/test_nudges_mode.py`: `workspace.load_config` of an empty
  `config.toml` gives `nudges.mode == ''`; `workspace.nudge_mode` is `off` for the default,
  `next` with `[autonomy]\nmode = "supervised"`, and the explicit value for `off`, `next` and
  `all` under either autonomy mode; `[nudges]\nmode = "sometimes"` is refused by
  `load_config` (`workspace.ConfigError`).
- [X] T002 Implement the `nudges` schema row and `nudge_mode` in `cli/wuwei/workspace.py`.

## Phase 2: the filter (FR-002, US1, US2)

- [X] T003 Test in `tests/test_nudges_mode.py`: `status.surfaced` on rows from
  `status.attention` of a day with events `watch: read-failed`, `merge.unmeasured`,
  `draft.created`, `guard.would_refuse` (posture `guarded`), `steward.due` and
  `security.finding` (a page):
  - empty `config.toml` (autonomous): mode `off`, only the page row;
  - `[nudges]\nmode = "all"`: mode `all`, the rows unchanged (same list);
  - `[nudges]\nmode = "next"`: mode `next`, only the page row;
  - no `config.toml`: mode `all`, the rows unchanged.
- [X] T004 Test in `tests/test_nudges_mode.py` (mode `next`, gate approved):
  - approved item `A` in phase `fix`, no seats: one row, source `round.ready`, tier `nudge`,
    reason containing `wuwei build next A`; calling `surfaced` twice gives one row each time;
  - the same with a running builder seat for `A`, and separately with a running fast check
    marker for `A` (`builds.A`, as `state.check_running` reads it): no row;
  - approved `A` merged and `B` parked, no seats, no `close_requested`: one row, source
    `close.ready`, reason containing `wuwei close`; with `close_requested` true: none; with
    `B` still `implement`: none;
  - a routed decision answered from the phone (`decision.replied` event, as the existing
    `decision.answered` test in `tests/test_signal_status.py` builds it): one
    `decision.answered` row; the same decision unanswered (`decision.pending`): none.
- [X] T005 Implement `surfaced` in `cli/wuwei/commands/status.py`.

## Phase 3: the surfaces (FR-003, FR-004, FR-005, US1, US2)

- [X] T006 Test in `tests/test_nudges_mode.py`: for the T003 day,
  - empty config: `status.snapshot` has `nudges == 0`, `nudges_mode == 'off'`, `pages == 1`;
    `status.line(snapshot(day, line=True))` contains `pages 1` and not `nudges`; `main(['status',
    '--json'])` prints `nudges` 0 and `nudges_mode` `off`;
  - `mode = "all"`: `nudges` equals the raw nudge count and the line contains `nudges <n>`;
  - `mode = "next"` with the T004 fix-round state: the line contains `nudges 1`;
  - `status._groups({...})` for a snapshot dict without `nudges_mode` still renders
    `nudges N` (remote and fixture snapshots).
- [X] T007 Implement the `snapshot` count and `nudges_mode`, and the `_groups` token rule in
  `cli/wuwei/commands/status.py`.
- [X] T008 Test in `tests/test_nudges_mode.py`: for the T003 day with an empty config,
  `main(['nudges', '--json'])` prints only the page row and `main(['nudges'])` one `page:` line;
  `main(['nudges', '--all', '--json'])` prints every `status.attention` row; under
  `mode = "next"` with the fix-round state, `main(['nudges'])` prints one line naming
  `wuwei build next A` and no `Run: wuwei next` suffix; with no `state.json`, every mode prints
  `No open pages or nudges.` and exits 0; `nudges.run` with a namespace lacking `all` works.
- [X] T009 Implement `--all` and the `surfaced` call in `cli/wuwei/commands/nudges.py`.
- [X] T010 Test in `tests/test_nudges_mode.py`: with an empty config, the board's Attention
  table (`board.read(root)`, as `tests/test_board_mcp.py` calls it) lists the page and no
  nudge row; doctor's `_day` rows (as `tests/test_doctor.py:596` reads them) have a `nudges`
  row whose value names `nudges.mode off` and `wuwei nudges --all`, a `traces` row whose fix
  names `wuwei nudges --all`, and the page row unchanged.
- [X] T011 Implement the `surfaced` calls in `cli/wuwei/commands/board.py` (`read`) and
  `cli/wuwei/commands/doctor.py` (`_day`), with the two text changes.

## Phase 4: setup answer and upgrade (FR-006, FR-007, US3)

- [X] T012 Test in `tests/test_nudges_mode.py`: the Autonomous answer's effects written to
  `config.toml` give `nudge_mode` `off`, Supervised `next`, and neither names `nudges.mode`.
  (Changed during implementation: adding the key to the effects re-asks the autonomy question
  on configured workspaces, see plan.)
- [X] T013 No code: the `""` default covers it; `cli/wuwei/interview.py` is unchanged.
- [X] T014 Test in `tests/test_workspace.py`, beside its upgrade tests: `init --upgrade` on a workspace whose `config.toml` has no
  `nudges.mode` prints `nudges.mode unset, so nudges follow autonomy.mode: off` and writes no
  `nudges` key; with `[autonomy]\nmode = "supervised"` the line names `next`; `--upgrade
  --dry-run` prints it too; with `[nudges]\nmode = "all"` no such line; the notice alone does
  not suppress `No workspace changes needed`.
- [X] T015 Implement the notice in `upgrade` in `cli/wuwei/commands/init.py`.

## Phase 5: template, docs and the existing suite (FR-008)

- [X] T016 Add the commented `# [nudges]` block to `templates/workspace/config.toml`, then run
  `tests/test_docs.py`: `test_every_template_config_key_is_documented` fails on `nudges.mode`.
- [X] T017 Document `nudges.mode` in `docs/site/configuration.md` (its row, the autonomy answer
  row and the intro list), and the status line token and `--all` in `docs/site/reference.md`;
  fix the `nudges 0` example lines in `docs/site/daily.md` and `docs/site/remote.md` only where
  the default now drops the token. Rerun `tests/test_docs.py` until it passes.
- [X] T018 Run the full suite. For each failure caused only by the default (autonomous) mode
  hiding nudges in a test about the raw classification, move the test to `--all`,
  `status.attention` or a `[nudges]\nmode = "all"` config line (see plan, Test files); do not
  change any other assertion. Any failure of another kind is a bug in T002 to T015.
- [X] T019 Run `python -m pytest -q`; everything passes. Check the files written for em-dashes,
  emojis and absolute local paths.
- [X] T020 Point the five lookup and refusal hints (`control_plane.py`, `commands/why.py`,
  `commands/decision.py`, `obligations.py` twice) at `bin/wuwei nudges --all`, since the
  filtered listing hides the decision and obligation rows they name; update the asserting tests
  in `tests/test_why.py` and `tests/test_reasons.py` first.

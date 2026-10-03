# Tasks: session orientation (`wuwei next`, SessionStart block, agent guide)

**Input**: `specs/358-session-orientation/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names. Tests are in process; no subprocess
beyond what existing tests already do.

## Phase 1: Fixture

- [X] T001 Fixture, `tests/test_next.py`: `root` fixture (as in `tests/test_sessions.py`:
  `WUWEI_WORKSPACE`, `WUWEI_NOW`, `.wuwei/config.toml`, empty day state) plus helpers
  `calibrated(root)` (config with one `[[repos]]` table for `example/project` and
  `.wuwei/calibration.json` `{"example/project": {}}`), `planned(root)` (writes today's
  `plan.md`), `approved(root, items, cap=1)` (sets `gate_approved`, `approved_items`,
  `items`, `cap` through `state._write_state(..., reserved=False)`), and `row(capsys,
  *args)` that runs `main(['next', '--json', *args])` and returns `(code, json)`. Neutral
  names only. No behaviour yet.

## Phase 2: US1 `wuwei next` (P1)

- [X] T002 Test, `tests/test_next.py`: setup rows. Outside any workspace (`tmp_path`
  without `.wuwei`, `WUWEI_WORKSPACE` unset, `monkeypatch.chdir`) exit 0 and
  `{'state': 'no-workspace', 'command': 'bin/wuwei setup --shadow', 'step': ...}`; the
  bare fixture gives `setup` / `bin/wuwei setup`; repos without `calibration.json` also
  give `setup`. Assert the JSON keys are exactly `{'state', 'step', 'command'}`. Run
  `python -m pytest -q tests/test_next.py -k setup` and see it fail on `invalid choice: 'next'`.
- [X] T003 Implement, `cli/wuwei/commands/next.py`: `register`, `run`, `line`, and `step`
  through the `no-workspace` and `setup` rows (plan.md section 1).
- [X] T004 Test, `tests/test_next.py`: morning rows. Calibrated, no `plan.md`: `plan`,
  `/wuwei:wuwei-plan`, step contains `start the day`. With `plan.md` and the gate closed:
  `gate`, `/wuwei:wuwei-plan`, step contains `Morning gate` and `days/<date>/plan.md`.
  Without `--json` the line is `gate: <step> Run: /wuwei:wuwei-plan`.
- [X] T005 Implement, `cli/wuwei/commands/next.py`: `plan` and `gate` rows.
- [X] T006 Test, `tests/test_next.py`: decision row. Gate approved, `decision_routes`
  `{'D-1': ...}` with no owner outcome gives `decision`, `wuwei decision show D-1`; with
  `decision_outcomes` `{'D-1': {'option': 'A', 'decided_by': 'owner'}}` the row moves on.
- [X] T007 Implement, `cli/wuwei/commands/next.py`: `decision` row via
  `wuwei.decision.answered`.
- [X] T008 Test, `tests/test_next.py`: item rows, one parametrized table. Approved
  `ITEM-1` in phase `planned` gives `dispatch` / `wuwei worktree add ITEM-1` and the step
  names `brief builder` and `build next`; `implement` and `fix` give `build` /
  `wuwei build next ITEM-1`; `gate` and `delta` give `verdicts` /
  `wuwei dispatch next ITEM-1`; `raised` with `pr` `example/project#7` gives `pr` /
  `wuwei pr act example/project#7`. CAP: `ITEM-1` in `implement` with a running builder
  seat and `ITEM-2` `planned` at cap 1 gives `wait` (not `dispatch`), step names the seat;
  the same at cap 2 gives `dispatch` for `ITEM-2`. Order: two due items, the first in
  `approved_items` wins. An approved id missing from `items` is skipped.
- [X] T009 Implement, `cli/wuwei/commands/next.py`: the item walk, `running` from
  `brief.seats`, `building` from `state.BUILD_PHASES`, and the `wait` row.
- [X] T010 Test, `tests/test_next.py`: end of day. All approved items `merged`, `parked`
  or `escalated` (and an empty `approved_items`) give `close` / `/wuwei:wuwei-report`;
  with `report.md` and `close_requested` true, `closed` / `wuwei close`. With a
  `watch: clock` event today older than the watch's dead threshold (or a
  `heartbeat: clock` event `{'health': 'degraded', 'page': 'x'}` with a live watch; reuse
  the event shapes from `tests/test_heartbeat.py` or `tests/test_watch.py`), the row is
  `doctor` / `wuwei doctor` instead of `close`.
- [X] T011 Implement, `cli/wuwei/commands/next.py`: `doctor` (lazy `status.scan`),
  `close` and `closed` rows.
- [X] T012 Test, `tests/test_next.py`: unreadable input. A `config.toml` that is not TOML,
  and a `state.json` that is not JSON, each give exit 2, state `unmeasured`, command
  `wuwei doctor`, the reason in `step`, and `wuwei next:` on stderr.
- [X] T013 Implement, `cli/wuwei/commands/next.py`: the error branch of `run`.

## Phase 3: US2 SessionStart orientation (P1)

- [X] T014 Test, `tests/test_next.py`: `orientation(row, posture)` unit table. Starts with
  `next.HEADER`; fewer than 25 lines; contains `Next: ` + `line(row)`,
  `/wuwei:wuwei-plan`, `str(integrity.PLUGIN / 'docs/site/agent.md')`,
  `skills/wuwei-plan/SKILL.md` and `docs/site/daily.md`; observe gives the old shadow text
  (`Observe posture is on` and `bin/wuwei shadow report`), guarded and strict give their
  lines. With `WUWEI_SEAT_ROLE=shepherd` the entry names `charters/shepherd.md` and not
  `/wuwei:wuwei-plan`; with `WUWEI_SEAT_ROLE=../x` or `nope` it is the interactive entry.
- [X] T015 Implement, `cli/wuwei/commands/next.py`: `HEADER`, `POSTURES`, `orientation`.
- [X] T016 Test, `tests/test_next.py` (issue acceptance 2 and 4):
  `test_issue_acceptance_session_start_orients`: calibrated workspace, no plan, run
  `hook.run` with the recorded SessionStart payload (`cwd` the workspace, as
  `tests/test_sessions.py::hook`); `additionalContext` starts with `HEADER`, has the line
  `Next: plan: ... Run: /wuwei:wuwei-plan`, the agent.md path, and the index of the
  `Active constraints:` line is below 25. Second case: monkeypatch `wuwei.integrity.check`
  to return `Result(0, None, 'plugin integrity: owner-confirmed content (local evidence)')`
  and `wuwei.integrity.workspace_check` to return `Result(0)` (the guard's `GUARDS` entry
  holds the function, so patch what it calls); the context still starts with `HEADER` and
  holds the integrity line after the block. Third case: `next.step` raising `ValueError('broken')` gives
  `Next: unmeasured: broken Run: wuwei doctor` and the block still prints.
- [X] T017 Implement, `cli/wuwei/guards/lifecycle.py`: remove `SHADOW_LINE` and its append;
  build the row and append `orientation` first (plan.md section 2).
- [X] T018 Implement, `cli/wuwei/commands/hook.py`: SessionStart branch sorts the parts so
  the `HEADER` block is first (plan.md section 3).
- [X] T019 Update, `tests/test_sessions.py::test_issue_acceptance_payload_after_compaction`:
  assert the text starts with `HEADER` and contains `'\nActive constraints:\n'` (it fails
  after T017, as expected).
- [X] T020 Test, `tests/test_next.py` (issue acceptance 3, #323 regression):
  `hook.run` SessionStart with `cwd` a directory outside any workspace and
  `WUWEI_WORKSPACE` unset prints nothing and returns 0. Expected to pass already; it pins
  the behaviour.
- [X] T021 Run `python -m pytest -q tests/test_shadow.py tests/test_listen.py tests/test_sessions.py tests/test_hooks.py tests/test_guard_mutation.py tests/test_scope_first.py`
  and fix only what this change broke.

## Phase 4: US3 agent guide and docs (P2)

- [X] T022 Test, `tests/test_docs.py`: `test_agent_guide_ships_and_is_linked`:
  `docs/site/agent.md` starts with the front matter, is at most 100 lines, contains
  `wuwei next`, `/wuwei:wuwei-plan`, `/wuwei:wuwei-report`, `.wuwei/executable`, `-P`,
  `host terminal`, `posture:` and each of `planner`, `lead`, `builder`, `sentinel`,
  `shepherd`, `steward`; no em dash and no emoji; `(agent.html)` is in `index.md` and
  `daily.md`; the README `## Quick start` section contains `orients itself`; each
  `skills/*/SKILL.md` has `` `wuwei next` `` in the first paragraph after its `# ` heading.
  Run `python -m pytest -q tests/test_docs.py` and see this test and
  `test_reference_lists_every_cli_command` fail.
- [X] T023 Write `docs/site/agent.md` (plan.md section 4), with the humanizer checklist.
- [X] T024 Edit `docs/site/index.md`, `docs/site/daily.md` (link and Re-anchoring bullet),
  `docs/site/reference.md` (commands row) and `README.md` (Quick start sentence).
- [X] T025 Edit `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`,
  `skills/wuwei-retro/SKILL.md`, `skills/wuwei-consolidate/SKILL.md`: the `wuwei next`
  first sentence (plan.md section 5).

## Phase 5: Verify

- [X] T026 Full suite: `python -m pytest -q`. Everything passes, including the hook
  latency tests.
- [X] T027 Check every file written or changed for em dashes, emojis and absolute local
  paths; remove any.

## Dependencies

T001 first. Within each pair the test precedes its implementation. Phase 3 needs T003 to
T013 (`step`). T019 follows T017. Phase 4 can start after T003 (the command exists, so
the reference row test is red for the right reason).

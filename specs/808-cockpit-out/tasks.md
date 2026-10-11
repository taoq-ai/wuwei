# Tasks: delete the cockpit (board, dashboard, menu bar, brief packs)

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers are at main `221f1f2`.

Rules: test before each behaviour change (see it fail, then change the code). For a pure
deletion the task is "delete the tests with the code, then run the touched test files". Never
relax an assertion that covers kept code. No commits, no pushes, no `gh`. Never edit
`agents/*.md` by hand.

## Phase 0: setup

- [X] T001 Rebase onto main after parts 1 to 4 (#798, #799, #800, #801) merge; recheck every
  line in plan.md; note which "only if part N has not" edits remain and whether
  `workspace.RETIRED` exists.

## Phase 1: behaviour changes, tests first (US1, US2)

- [X] T002 [US1] [US2] Tests first: add the new CLI case from plan.md (`brief pack` exits 2
  naming `expected ROLE ITEM NAME`; `board`, `dashboard`, `signal classify` exit 2 from
  argparse; `plugin.json` has no `mcpServers`); edit `tests/test_doctor.py:557-568` (no
  own-server rows) and `tests/test_workspace.py:271` (brief defaults). Run
  `python -m pytest -q tests/test_cli.py tests/test_doctor.py tests/test_workspace.py`; see the
  new and edited cases fail.
- [X] T003 [US1] Delete `mcpServers` from `.claude-plugin/plugin.json`; delete the own-server
  rows in `cli/wuwei/commands/doctor.py:528-535` (and any import left unused); docstring at 933.
- [X] T004 [US2] `cli/wuwei/commands/brief.py`: drop the pack and answer forms, `--meeting`
  and the `brief_pack` import; new message.
- [X] T005 [US2] `cli/wuwei/workspace.py` `SCHEMA['brief']` and
  `templates/workspace/config.toml` `[brief]`: drop `lead_minutes` and `[brief.style]`; comment
  at 642. If `workspace.RETIRED` exists, add `'brief.lead_minutes'` and `'brief.style'`.
- [X] T006 Run the T002 files; green.

## Phase 2: delete the cockpit (US1, US2)

- [X] T007 [US1] Delete `cli/wuwei/commands/board.py`, `cli/wuwei/commands/dashboard.py`,
  `cli/wuwei/commands/signal.py`, `templates/dashboard.html`, `templates/swiftbar/`,
  `tests/fixtures/swiftbar/`, `tests/test_board_mcp.py`, `tests/test_dashboard.py`,
  `tests/test_swiftbar.py`. Delete `init --menu-bar` (`cli/wuwei/commands/init.py:35, 43,
  46-57`) and `menu_bar=False` in `cli/wuwei/commands/setup.py:484`. Only if part 3 left them:
  GROUPS in `cli/wuwei/__main__.py`, `READ_ONLY`/`WRITES` in `cli/wuwei/commands/__init__.py`.
- [X] T008 [US1] Delete the tests with the code: `tests/conftest.py:8`;
  `tests/test_dispatch.py:1633, 1653-1654`; `tests/test_drafts.py:378-389` and the
  `cockpit_snapshot` lines in 392-401; `tests/test_doctor.py:1026, 1043`;
  `tests/test_watch.py:904, 927`; `tests/test_signal_status.py:111-115`; `tests/test_integrity.py:460`
  (board.py to next.py); `tests/test_mcp.py:775` comment; only where earlier parts left them,
  `tests/test_cli.py:325`, `tests/test_cli_known_command.py:55`, `tests/test_nudges_mode.py:170-185`
  board half.
- [X] T009 [US2] `git mv tests/test_brief_pack.py tests/test_calendar_tts.py` and trim it to
  the four adapter cases with a minimal fixture (plan.md). Delete `cli/wuwei/brief_pack.py`.
  Delete `brief_packs`/`brief_drill` in `cli/wuwei/state.py:265`, `brief.pack`/`brief.answer`
  in `cli/wuwei/commands/event.py:80` and `cli/wuwei/signal.py:9`, `brief_drill_score` in
  `cli/wuwei/metrics.py:851-852`. Tests: `tests/test_signal_status.py:335` drop the two kinds;
  `tests/test_operator_records.py:62-65, 70`.
- [X] T010 Comment cleanups: `cli/wuwei/commands/why.py:83`.
- [X] T011 Run every file touched in T007 to T010; green.

## Phase 3: charters, skills, docs (US4)

- [X] T012 [US4] `charters/planner.md:24`, `charters/_common-authoring.md:17`,
  `skills/wuwei-plan/SKILL.md:8`; then `bin/wuwei agents build` and `bin/wuwei agents check`.
- [X] T013 [US4] Docs per plan.md: `README.md`, `NOTICE`, `docs/site/{concepts,daily,reference,
  configuration,integrity,index,recovery}.md`, `docs/site/agent.md` (only if the guide block
  remains), `docs/specs/2026-09-24-wuwei-design.md`; `tests/test_docs.py` pins only where part 1
  left them.

## Phase 4: verify

- [X] T014 Run the plan.md Verification greps (empty). Run
  `python -m pytest -q tests/test_cli.py tests/test_doctor.py tests/test_workspace.py
  tests/test_dispatch.py tests/test_drafts.py tests/test_watch.py tests/test_signal_status.py
  tests/test_integrity.py tests/test_mcp.py tests/test_operator_records.py
  tests/test_calendar_tts.py tests/test_docs.py tests/test_charters.py tests/test_telemetry.py
  tests/test_tone.py tests/test_adapters.py` plus `tests/test_cli_known_command.py` and
  `tests/test_nudges_mode.py` if they still exist. No full suite; CI is the gate.
- [X] T015 If #799 is not on the base, leave `RETIRED` alone; the lead adds the two keys
  listed in plan.md "RETIRED at rebase".

## Dependencies

T001 first. T002 before T003 to T005. Phase 2 after Phase 1. T012 and T013 after Phase 2.
T014 last.

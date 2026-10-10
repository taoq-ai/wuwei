# Tasks: the terminal and other local tools are a local class

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root using
the interpreter the pipeline names. Signatures, texts and line numbers are in plan.md.
Fixtures: `configured`, `payload()`, `set_posture()`, `run_hook()` (`tests/test_outward.py`);
`root`, `configure()`, `posture()`, `learn()`, `events()`, `decisions()`, `answer()`
(`tests/test_outbound_learn.py`); `rules.hook()`, `rules.bash()`, `rules.memo()`
(`tests/test_invariants.py`). No absolute local path, no em-dash and no emoji in any file.

## Phase 1: the class in the outward guard (US1 1, US2, FR-001 to FR-003)

- [X] T001 In `tests/test_outward.py`, add failing `test_local_tools_pass`, parametrized over
  posture (`observe`, `guarded`, `strict`) and tool (`mcp__terminal__run_in_terminal`,
  `mcp__terminal__open_terminal_tab`, `mcp__terminal__stop_terminal_tab`,
  `mcp__Claude_Code_iOS_Simulator__control`, `mcp__Claude_Preview__preview_start`,
  `mcp__Claude_Browser__preview_start`, `mcp__computer-use__open_application`), with
  `tool_input = {'command': 'sleep 600'}`: `check_tier` and `check_lint` both return `(0, '')`,
  no `drafts` row is stored and no `outward.unknown_tool` event is written; and
  `resolve(tool, config) == {'local'}`. Fails today: run_in_terminal, open_terminal_tab and
  open_application are refused as unknown connectors (exit 2); the others are refused under
  strict.
- [X] T002 In `tests/test_outward.py`, add failing `test_local_shapes_are_exact`:
  `mcp__plugin_x_terminal__run_job` is still refused as an unknown connector write naming
  `outbound learn` (exit 2); `resolve('mcp__Claude_Browser__navigate', config)` is not
  `{'local'}`; `mcp__terminal__read_terminal` passes as a read with `resolve` `set()`. Passes
  the non-local half today; the `{'local'}` half fails until T005.
- [X] T003 In `tests/test_outward.py`, add failing `test_local_alias`: with
  `[outward.servers] acme = "local"` a write `mcp__acme__send_message` passes `check_tier` and
  `check_lint` under strict with no draft; with `[outward.servers] terminal = "mail"`,
  `resolve('mcp__terminal__run_in_terminal', config) == {'mail'}` (the owner alias wins).
  Fails today: `local` is not a valid `outward.servers` value (`ConfigError`).
- [X] T004 In `tests/test_outward.py`, add failing `test_local_keeps_canary_floor`:
  `check_tier` on `mcp__terminal__run_in_terminal` whose command contains
  `security.load(root)['canary']` returns exit 1 with a reason starting `outward: security.`;
  `check_lint` on it returns `(0, '')`. Fails today: refused as an unknown connector (exit 2).
- [X] T005 In `cli/wuwei/workspace.py`, add `"local"` to the `outward.servers` choices and bump
  `CONFIG_CACHE_VERSION`. In `cli/wuwei/guards/outward.py`, add `LOCAL_SERVERS` and `LOCAL`,
  the `LOCAL` step in `resolve`, and the local return in `_check` (plan section 2). T001 to
  T004 pass.

## Phase 2: the terminal command is judged as Bash (US1 2-4, FR-004)

- [X] T006 In `tests/test_hooks.py`, add failing `test_terminal_as_bash`: `hook.as_bash` on a
  PreToolUse `mcp__terminal__run_in_terminal` payload with `command = "sleep 600"`,
  `cwd = "demo"` returns `tool_name == 'Bash'`, `tool_input == {'command': 'sleep 600'}` and
  `cwd` equal to the session cwd joined with `demo`; with no `cwd` the session cwd stays; a
  PostToolUse payload and a `Bash` payload come back unchanged; a non-string `command` or
  `cwd` raises `ValueError` naming the payload. Fails today: no attribute `as_bash`.
- [X] T007 In `tests/test_outward.py` (it reuses the `configured` workspace and `run_hook`), add failing `test_terminal_hook_judges_the_command`
  inside a workspace: the whole PreToolUse hook (`hook.run`) on run_in_terminal with
  `sleep 600` exits 0; on run_in_terminal with a command that writes the day's `state.json`
  (the same command a `protect_state` test refuses through `Bash`) exits with the same code
  and the same first stderr line as that command through `Bash`; a run_in_terminal payload with
  `command = 3` exits 2. Fails today: the plain command is refused as an unknown connector and
  the state write is refused with the outward reason, not the records reason.
- [X] T008 In `cli/wuwei/commands/hook.py`, add `TERMINAL` and `as_bash`, and call
  `payload = as_bash(payload)` after `validate` in `run` (plan section 3). T006 and T007 pass.

## Phase 3: learn card and tier table (US3, FR-005, FR-006)

- [X] T009 In `tests/test_outbound_learn.py`, add failing `test_local_card`: `learn(root,
  '--as', 'local', tool=f'mcp__{UUID}__run_job', listings=False)` exits 0 with one card whose
  question starts `D-1: Connector <UUID> is local?`, whose option labels are Approve and the
  Defer row only (no `Approve, mode ...` row), and `decision lint` on `D-1.md` exits 0;
  answering `approve` records `outward.servers == {UUID: 'local'}` and no `outward.modes`
  entry; afterwards `check_tier` on that tool passes. Fails today: `--as local` is not a valid
  choice (argparse exit 2).
- [X] T010 In `tests/test_outbound_learn.py`, add failing `test_local_shape_proposes_local`:
  `learn(root, tool='mcp__terminal__open_terminal_tab', listings=False)` without `--as` writes a
  card proposing `local`. Fails today: `connector terminal has no channel`.
- [X] T011 In `tests/test_outbound_learn.py`, add failing `test_auto_never_learns_local_without_the_card`
  for each posture: with `learn = "auto"`, `--as local` writes a card (`D-1.md`), no
  `outbound.learned` event and no `outward.servers` entry. Fails today: invalid choice.
- [X] T012 In `cli/wuwei/commands/outbound.py`, add `MODE_TEXT['local']`, the local branches in
  `record`, and `'local'` in the `card` condition of `learn` (plan section 4). T009 to T011
  pass; `test_as_cannot_override_a_resolving_channel` still passes.
- [X] T013 In `tests/test_outbound.py`, extend `test_outbound_tiers_prints_table`: the last line
  starts `-     local    terminal, Claude_Preview, Claude_Code_iOS_Simulator, computer-use,
  Claude_Browser preview tools: local` and `len(lines) == 15`; with `[outward.servers] acme =
  "local"` the line also names `acme`. Fails today: 14 lines.
- [X] T014 In `cli/wuwei/commands/outbound.py`, print the local line in `tiers` (plan section 4).
  T013 passes.

## Phase 4: invariant and docs (FR-007, FR-008)

- [X] T015 In `tests/test_invariants.py`, add `i65` (plan section 6), register it last in
  `INVARIANTS` and in `READS` with `(0,)`; run it and see `test_table_matches_the_checks` fail
  (the design table has no I65 row). If the code of T005 or T008 is reverted, `i65` fails.
- [X] T016 In `docs/specs/2026-09-24-wuwei-design.md`, append the I65 row to the 9.2 table
  (plan section 6). T015 passes, the walk stays under its time budget.
- [X] T017 [P] Update `docs/site/configuration.md` (`outward.servers` row),
  `docs/site/security.md` (channel order paragraph) and `templates/workspace/config.toml`
  (alias comment) to name `local` (plan section 5). Any docs test that pins these texts
  passes.

## Phase 5: finish

- [X] T018 Run the full suite (`python -m pytest -q`); everything passes. Check every file you
  wrote for em-dashes, emojis and absolute local paths and remove any.

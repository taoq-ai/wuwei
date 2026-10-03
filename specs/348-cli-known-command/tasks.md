# Tasks: the plugin's own CLI is a known command

**Input**: `specs/348-cli-known-command/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, see it fail for the
stated reason, then do the implementation task that follows. Run from the repository root
with the interpreter your task names. No absolute local paths, client or repository names,
emojis or em-dashes in any file. Fixture names stay neutral. Do not edit or remove an
existing test row except the doctor name lists in T011 and the phrase additions in T013.
Only the four skills, `next.py` and `docs/site/agent.md` tell a session how to call the
executable (`docs/site/daily.md:12` only says which one the planner uses), so no other doc
changes.

Shapes used by several tasks (`<exe>` is the recorded executable, a launcher copy at
`tmp_path / 'plugin-cache/0.12.0/bin/wuwei'` recorded in `.wuwei/executable`):

- P1 `<exe> config check | grep -n -A3 -i 'repos\|\[repo\|tracker' | head -40`
- P2 `<exe> mcp check | grep -n -A3 -i 'repos\|\[repo\|tracker' | head -40`
- W1 `<exe> note add --body "rm the stale config"`

## Phase 1: the table (FR-001, FR-002)

- [X] T001 [US1] [US2] Test, new `tests/test_cli_known_command.py`:
  `test_every_registered_command_is_in_exactly_one_set` builds an `argparse` parser,
  registers every module of `wuwei.commands` as `cli/wuwei/__main__.py` does (skip names
  starting with `_`), walks the sub-parsers to their leaves, and for a leaf whose positional
  `action` has choices adds `path + choice` for each choice (plus the bare path when its
  `nargs` is `'?'`). Assert the set of paths equals `commands.READ_ONLY | commands.WRITES`,
  that the two sets are disjoint, and that every `protect_state._OWNER_ACTIONS` pair, joined
  with a space and stripped (`('setup', '')` is `setup`), is in `commands.WRITES`.
  `test_read_only` is a table over `commands.read_only`: true for `['status', '--line']`,
  `['why', 'last', 'refusal']`, `['doctor']`, `['doctor', '--json']`, `['config', 'check']`,
  `['mcp', 'check', '--widget']`, `['integrity', 'check']`, `['shadow', 'report']`,
  `['board']`, `['sessions']`, `['heartbeat']`, `['calibrate', '--questions']`,
  `['calibrate', '--repo', 'x', '--questions']`, `['--version']`,
  `['mcp', 'decide', '--help']`, `['config', 'set', '-h']`; false for `[]`,
  `['doctor', '--fix']`, `['calibrate']`, `['calibrate', 'export', 'x', '--questions']`,
  `['mcp', 'decide', 'D-1', 'proceed']`, `['mcp', 'decide', '--', '--help']`,
  `['config', 'show']`, `['config', 'set', 'k', 'v']`, `['integrity', 'reconfirm']`,
  `['state', 'get']`. Run `python -m pytest -q tests/test_cli_known_command.py`: fails on
  `AttributeError` (no `READ_ONLY`, `WRITES` or `read_only` in `wuwei.commands`).
- [X] T002 Implement in `cli/wuwei/commands/__init__.py` per plan section 1: `READ_ONLY`,
  `_NEEDS`, `WRITES` (the 81 paths) and `read_only(args)`. Rerun T001: passes.

## Phase 2: acceptance through the hook (red)

- [X] T003 [US1] [US2] Test, `tests/test_cli_known_command.py`: a `workspace` fixture like
  `tests/test_parser_warns.py` (seeded integrity, no `WUWEI_WORKSPACE`, no `CDPATH`) that
  copies the repository `bin/wuwei` to `tmp_path / 'plugin-cache/0.12.0/bin/wuwei'` and
  records that path in `.wuwei/executable`; `configure`, `hook` and `events` helpers as in
  that file; postures `observe`, `guarded`, `strict`. Tests, each parametrized over the
  three postures:
  - `test_read_commands_pass`: `<exe> mcp check`, `<exe> config show`, P1, P2, P1 with
    `<exe>` replaced by the repository `bin/wuwei` (the running plugin's launcher, not
    recorded) and by bare `wuwei`: exit 0, no `hook.refusal` and no `guard.would_refuse`
    event.
  - `test_help_passes`: `<exe> mcp decide --help` and `<exe> config set --help`: exit 0, no
    event.
  - `test_owner_actions_keep_the_host_terminal_rule`: `<exe> mcp decide D-1 proceed` and
    `<exe> mcp decide -- --help`: exit 2 and `MCP decisions require the owner terminal` in
    `permissionDecisionReason`.
  - `test_writer_subcommand_is_not_opaque`: W1 exits 0 and records no `guard.would_refuse`.
  - `test_unrecognised_copy_stays_opaque`: P1 through a second copy at
    `tmp_path / 'elsewhere/bin/wuwei'` that is not recorded: under `strict` exit 2 with
    `opaque interpreter command` in the reason; under `observe` exit 0 with one
    `guard.would_refuse` naming it.
  Run `python -m pytest -q tests/test_cli_known_command.py`: P1 and P2 forms fail (exit 2
  under guarded and strict, a would-refuse under observe, "opaque interpreter command"),
  `--help` fails (exit 2, "MCP decisions require the owner terminal"), W1 fails under all
  postures with "opaque interpreter command"; the single commands, the owner-action test and
  the unrecognised-copy test already pass and pin behaviour.

## Phase 3: the CLI is a read-only word (FR-003, FR-004)

- [X] T004 [US1] Test, `tests/test_cli_known_command.py`: `test_classify_knows_the_cli`
  calls `shell.classify` directly in the T003 workspace: P1 with `cwd=<workspace>` is
  `readonly`; P1 without `cwd` is not (only bare `wuwei` is known without a cwd);
  `wuwei status --line | head -5` is `readonly` without a cwd; `<exe> status --line > out.txt`
  is not; `<exe> config set k v | head -1` is not. `shell.unread(P1, cwd=...)` returns
  `(0, '')`. Run it: fails with `TypeError` (unexpected keyword `cwd`).
- [X] T005 Implement in `cli/wuwei/shell.py` per plan section 2: `known_cli(word, cwd)`,
  the `cwd` parameter on `classify`, `unread` and `_classify` (both recursive calls), and the
  `safe` line. Rerun T004: passes.
- [X] T006 Implement plan section 3 call sites: `cwd=` on `shell.unread` in
  `cli/wuwei/guards/commit_push.py` (four calls), `cli/wuwei/guards/pr.py` (two),
  `cli/wuwei/guards/deploy.py` (two), and on `classify` in `cli/wuwei/guards/decision.py`
  and `cli/wuwei/guards/protect_state.py` (`check_bash`). Rerun T003:
  `test_read_commands_pass` passes; W1 and `--help` still fail.

## Phase 4: the commit/push path rule (FR-005)

- [X] T007 Implement in `cli/wuwei/guards/commit_push.py` (`check`, non-git branch): the
  path test excludes `shell.known_cli(command.argv[0], directory)` per plan section 3. Rerun
  T003: `test_writer_subcommand_is_not_opaque` passes and
  `test_unrecognised_copy_stays_opaque` still passes.

## Phase 5: `--help` for owner actions (FR-006)

- [X] T008 Implement in `cli/wuwei/guards/protect_state.py` (`_owner_action`) per plan
  section 4. Rerun T003: `test_help_passes` passes and
  `test_owner_actions_keep_the_host_terminal_rule` still passes. Run
  `python -m pytest -q tests/test_launcher_relevance.py tests/test_owner_edits.py`: passes.

## Phase 6: the doctor names a stale pointer (FR-008)

- [X] T009 [US4] Test, `tests/test_doctor.py`: `test_workspace_executable_pointer(ws)`:
  with `.wuwei/executable` holding `ws.plugin / 'bin/wuwei'` the `executable` row is `ok`;
  with it holding `tmp_path / 'cache/0.11.0/bin/wuwei'` (never created) the row is `fail`,
  its `value` names that path and says `missing`, `fix == 'wuwei init --upgrade'` and
  `apply == 'init-upgrade'`; with the file removed the row is `fail` with the same fix. Run
  `python -m pytest -q tests/test_doctor.py -k executable`: fails in `row()` (no
  `executable` row).
- [X] T010 Implement in `cli/wuwei/commands/doctor.py` (`_workspace`) per plan section 5.
  Rerun T009: passes.
- [X] T011 Update `tests/test_doctor.py`: the `ws` fixture writes `.wuwei/executable` with
  `ws.plugin / 'bin/wuwei'` and a newline; `test_workspace_rows_healthy` and
  `test_workspace_config_does_not_load` list `'executable'` right after `'template'`. Run
  `python -m pytest -q tests/test_doctor.py`: passes.

## Phase 7: skills, orientation and docs (FR-007, FR-009)

- [X] T012 [US3] Test, `tests/test_docs.py`:
  `test_skills_use_the_recorded_executable_directly`: for `wuwei-plan`, `wuwei-report`,
  `wuwei-retro` and `wuwei-consolidate`, the `SKILL.md` text has no `$(`, no
  `executable recorded in`, and contains ``read `.wuwei/executable` once with the Read
  tool`` and `first word of a plain command`. Run
  `python -m pytest -q tests/test_docs.py -k recorded_executable`: fails on the missing
  phrase.
- [X] T013 [US3] Test, `tests/test_docs.py`: `test_agent_guide_ships_and_is_linked` also
  asserts `first word of a plain command` in `docs/site/agent.md`;
  `test_unparsed_commands_are_documented` also asserts `read-only subcommands` and
  `--help` in `docs/site/security.md`. `tests/test_next.py`: `test_orientation_block` also
  asserts `first word of a plain command` in the text. Run
  `python -m pytest -q tests/test_docs.py tests/test_next.py`: fails on the missing phrases.
- [X] T014 Implement plan section 6: the sentence in the four `skills/*/SKILL.md`, the
  orientation line in `cli/wuwei/commands/next.py`, `docs/site/agent.md` and the
  `docs/site/security.md` sentence. Rerun T012 and T013: pass.
## Phase 8: regression

- [X] T015 Run the full suite: `python -m pytest -q`. Everything passes, the #347 `$W`
  rows included. Check every file you wrote for em-dashes and emojis.

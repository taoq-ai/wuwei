# Tasks: owner commands work from any configured repository

**Input**: `specs/735-workspace-from-repo/spec.md`, `specs/735-workspace-from-repo/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root. `HOME` is a tmp folder in every
test (`tests/conftest.py`), so `Path.home() / '.config/wuwei/workspaces.json'` is the test's
own index.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - the CLI finds the workspace from a configured checkout (P1)

### Tests first

- [X] T001 [US1] In `tests/test_workspace.py` (use the `clean_environment` fixture and
  `write_config`), add `test_index_writes_configured_checkouts`: a workspace `ws/` whose
  config has `[[repos]]` with `path = "."`, `path = "../repo"`, `path = "~"` and an absolute
  path; call `workspace.index(ws, load_config(ws))`; assert the file at
  `Path.home() / '.config/wuwei/workspaces.json'` is `{str(ws.resolve()): [sorted resolved
  ../repo and the absolute path]}` (no root, no home). Then write a second root's entry, call
  `index` again for `ws`: the other entry is kept. Then a config with no repositories: the
  `ws` entry is removed. Run it; it fails (`workspace.index` does not exist).
- [X] T002 [US1] In `tests/test_workspace.py`, add `test_find_workspace_from_indexed_checkout`:
  `ws/` configures `../repo`, `repo/sub/` exists, `index(ws, ...)`; assert
  `find_workspace(repo / 'sub') == ws`; with `monkeypatch.chdir(repo)`, `find_workspace()`
  is `ws`; with `WUWEI_WORKSPACE` set to another workspace it returns that one; a workspace
  `repo/inner/` with its own `.wuwei/` wins for `repo/inner/x` (walk before index). Run it;
  it fails.
- [X] T003 [US1] In `tests/test_workspace.py`, add `test_two_workspaces_configure_one_checkout`:
  `a/` and `b/` both configure `../repo`, both indexed; `find_workspace(repo)` raises
  `FileNotFoundError` whose text contains both roots and `--workspace`; and
  `cli(repo, 'config', 'check')` returns 2 with both roots and `--workspace` in stderr (US1
  scenario 2, SC-002). Run it; it fails (today's message names neither root).
- [X] T004 [US1] In `tests/test_workspace.py`, add `test_damaged_index_reads_as_empty`,
  parametrized over: no file, `not json`, `[]`, `{"relative": ["/x"]}`, `{"/ws": "x"}`,
  `{"/ws": [1]}`, and an entry whose root has no `.wuwei/` or a symlinked `.wuwei/`; in
  each case `find_workspace(repo)` raises today's `No .wuwei/ found` error (match
  `wuwei init`). These rows pass today (nothing reads the index); they are the regression
  guard that T009 never raises on a damaged index and skips a root without a real
  `.wuwei/`. Run them after T009 too.
- [X] T005 [US1] In `tests/test_workspace.py`, add `test_status_from_a_configured_checkout`
  (SC-001): `ws/` configures `../repo`, a day directory with `state.json` as
  `tests/test_signal_status.py` `day()` builds (`{'cap': 1, 'items': {}}`), `index(ws, ...)`;
  `cli(repo, 'status', WUWEI_NOW=<that day's timestamp>)` returns 0 and `cli(repo, 'config',
  'check')` returns 0. Run it; it fails (exit 2, no workspace).
- [X] T006 [P] [US1] In `tests/test_setup.py`, add a test next to
  `test_repository_table_lands_after_its_digest` (line 170): `add_repo(confirm,
  path='../widget')` with `widget/` created beside the workspace; assert the index maps the
  resolved workspace to `[resolved widget]` (US1 scenario 3). Add a second test: with
  `Path.home() / '.config'` made a file (so the index cannot be written), `add_repo` still
  returns 0, the config is written, and stderr says `workspace index not written`. Run them;
  they fail.
- [X] T007 [P] [US1] In `tests/test_workspace.py`, extend or add next to
  `test_upgrade_previous_workspace` (line 708): give `previous_workspace` a `[[repos]]`
  table with `path = "../repo"`; after `cli(tmp_path, 'init', '--upgrade')` the index holds
  the workspace's entry; after `init --upgrade --dry-run` on a fresh home it does not (US1
  scenario 3). Run it; it fails.

### Implementation

- [X] T008 [US1] In `cli/wuwei/workspace.py`, add `INDEX`, `_indexed()` and `index(root,
  config)` as in plan Design 1 (with the `ponytail:` no-lock comment). T001 passes.
- [X] T009 [US1] In `cli/wuwei/workspace.py` `find_workspace`, add the index lookup between
  the parent walk and the final raise (plan Design 1): one root returned, two or more raise
  naming every root and `--workspace`. T002, T003, T004 and T005 pass; the existing
  `test_find_nearest_workspace`, `test_workspace_override` and
  `test_missing_workspace_and_invalid_override` pass unchanged.
- [X] T010 [US1] In `cli/wuwei/commands/config.py` `offer`, call `workspace.index` after the
  config write, warning on `OSError` (plan Design 2). T006 passes.
- [X] T011 [US1] In `cli/wuwei/commands/init.py` `upgrade`, call `workspace.index` inside
  `if not args.dry_run:`, warning on `OSError`, no output on success (plan Design 2). T007
  passes and the other upgrade tests keep their output.

## Phase 2: User Story 2 - every owner command WUWEI prints carries --workspace (P1)

### Tests first

- [X] T012 [US2] In `tests/test_workspace.py`, add `test_owner_cli_quotes_the_root`:
  `owner_cli(Path('/w s'))` is `"bin/wuwei --workspace '/w s'"` and
  `owner_cli(Path('/w'))` is `'bin/wuwei --workspace /w'`. Run it; it fails.
- [X] T013 [US2] In `tests/test_decision.py`, change
  `test_decision_widget_passes_the_question_guard` (line 1226) to call
  `record_widget('D-3', fields, root=ws)` and assert
  `built['record'] == f'{owner_cli(ws)} decide D-3 "<label>"'`; add
  `test_printed_decide_runs_from_anywhere`: route `D-3` in `ws` as the tests around line 715
  do, patch `wuwei.integrity._host_confirm` to accept, take the card's record, put option
  `A`'s label in place of `<label>`, `shlex.split` it, drop `bin/wuwei`, and run it through
  `main` with `monkeypatch.chdir` to a folder outside any workspace: exit 0 and the outcome
  is recorded in `ws` (US2 scenario 2, SC-001's decide half). Update the other
  `record_widget` calls in tests (`grep -rn "record_widget(" tests`) to pass `root=`. Run
  them; they fail.
- [X] T014 [P] [US2] In `tests/test_decision.py`, update
  `test_owner_outcome_with_where_refuses_a_one_way_record` (line 741) to expect
  `f'run {owner_cli(ws)} decide D-3 A in a host terminal'`; add the same expectation for the
  declined-confirmation text (`rerun {owner_cli(ws)} decide <id> <option>`). In
  `tests/test_cruise.py` (lines 343, 346) and `tests/test_remote.py` (line 1018) expect
  `run {owner_cli(root)} decide D-n <option> to reverse it`. Run them; they fail.
- [X] T015 [P] [US2] In `tests/test_drafts.py`, update lines 388 (`approve_command`), 675
  (card `record`), 682 (`--file` option) and 868 (`--always` option) to the
  `owner_cli(root)` form, and assert the `Drop` option and the four-option `Keep as draft`
  text name `{owner_cli(root)} drafts drop {id}`. Run them; they fail.
- [X] T016 [P] [US2] In `tests/test_signal_status.py`, update lines 525, 549 and 809 to
  `confirm with {owner_cli(<workspace root>)} decide D-n X`. Run them; they fail.
- [X] T017 [P] [US2] In `tests/test_card_confirms.py:358` and
  `tests/test_outbound_learn.py:170`, expect `f'{owner_cli(root)} decide D-n "<label>"'`.
  Run them; they fail.

### Implementation

- [X] T018 [US2] In `cli/wuwei/workspace.py`, add `owner_cli(root)` (plan Design 1). T012
  passes.
- [X] T019 [US2] In `cli/wuwei/decision.py`, set `RECORD = '{cli} decide {id} "<label>"'`
  and give `record_widget` the required keyword `root`, formatting
  `cli=workspace.owner_cli(root)`; pass `root=root` at `commands/decision.py:164`,
  `grants.py:315`, `cruise.py:313`, `commands/outbound.py:370`, `mcp.py:408` and
  `calibrate.py:788`. T013 and T017 pass.
- [X] T020 [US2] In `cli/wuwei/commands/decision.py`, use `workspace.owner_cli(root)` in the
  texts at lines 203, 206, 274 and 277. T014 passes.
- [X] T021 [US2] In `cli/wuwei/drafts.py`, `widget(row, config, root)` with the prefix in the
  `--file`, drop, `--always` and record texts; pass `root` from `commands/drafts.py:35`. In
  `cli/wuwei/commands/dashboard.py:106`, build `approve_command` with
  `workspace.owner_cli(root)`. T015 passes.
- [X] T022 [US2] In `cli/wuwei/commands/status.py:220`, use
  `workspace.owner_cli(directory.parents[2])` in the phone-answer reason. T016 passes.

## Phase 3: User Story 3 - the guards cover a configured checkout (P2)

- [X] T023 [US3] In `tests/test_workspace.py`, add `test_scope_reaches_an_indexed_checkout`:
  `ws/` configures `../repo`, indexed; `scope((repo / 'x').resolve())` returns
  `(ws, config)`; with a second workspace also configuring `../repo` and indexed, it
  returns `None`. Run it; after T009 it passes with no `scope` change (FR-008). If it fails,
  fix the lookup in `find_workspace`, never in `scope`.

## Phase 4: Polish

- [X] T024 Run `grep -rn "wuwei decide\|drafts approve\|drafts drop" cli/wuwei` and confirm
  every remaining hit with a concrete id is one the spec's Assumptions list as unchanged.
- [X] T025 In `docs/site/reference.md` line 446 (the paragraph that already explains
  `WUWEI_WORKSPACE` and the leading `--workspace`), add one sentence: from a repository
  checkout a workspace configures, WUWEI finds the workspace through
  `~/.config/wuwei/workspaces.json`, written by config edits and `init --upgrade`, and the
  `decide` and `drafts` commands WUWEI prints already carry `--workspace`.
- [X] T026 Run the full suite (`python -m pytest -q`); fix only fallout from the changed
  texts and the new `root` parameters. Check the changed files for em-dashes and emojis.

## Dependencies

- T008 before T009 (the lookup reads `_indexed`); T009 before T005 and T023 can pass.
- T010 and T011 need T008.
- T018 before T019 to T022.
- Phase 2 does not depend on Phase 1 and may run in parallel with it.

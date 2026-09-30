# Tasks: Operator records and owner-action consistency after the fourth dry run

Test first throughout: write the test, run `python -m pytest -q <file>` and see it fail for the stated reason, then write the code. Plan sections are in [plan.md](plan.md). New acceptance tests go in `tests/test_records_after_dryrun4.py` (T001 creates it); reuse `cli` and `day` from `tests/test_signal_status.py` and the fixtures named below instead of new helpers.

## Steward nudge clears on a run (US1.1, US1.2, FR-001)

- [X] T001 Create `tests/test_records_after_dryrun4.py` with a failing test: a day (via `test_signal_status.day`) with state `{'cap': 1, 'items': {}, 'gate_approved': True}` and events `steward.due {'tool_calls': 51}` then `steward.run {'trigger': 'tool-calls', 'brief': 'b', 'tool_calls': 51}` (today's `ts`); `cli(root, 'nudges')` has no row with source `steward.due`, and `cli(root, 'status', '--json')` has `nudges == 0`. A second case with the order reversed (run, then due) lists exactly one `steward.due` row. Fails because the due row is never dropped.
- [X] T002 In `cli/wuwei/commands/status.py` `scan`, drop `steward.due` rows on a `steward.run` event before the `SILENT` skip (plan section 1).

## Steward ack ids (US1.3, US1.4, FR-002)

- [X] T003 In `tests/test_records_after_dryrun4.py`, add a failing test: `cli(root, 'steward', 'ack', '--help')` exits 0 and its stdout (whitespace-collapsed) contains `-fix-3`, `requires planner acknowledgement` and `steward.due`; `docs/site/reference.md` contains `steward ack` and `-fix-3`. Fails because the help has no text and the page never mentions it.
- [X] T004 In `cli/wuwei/commands/steward.py`, add the `ack` parser help and the `id` help; in `docs/site/reference.md`, add the `## Steward` section (plan section 2).

## Merged means done (US2, FR-003)

- [X] T005 In `tests/test_records_after_dryrun4.py`, add a failing test modelled on `tests/test_operator_records.py:14-38` (propose and approve `DIVIDE-1`, then `state transition` through `implement`, `gate`, `raised`, `merged` with `main`): `main(['state', 'get', 'items.DIVIDE-1.status'])` prints `"done"`; before the `merged` move it printed `"queued"`. Then capture a retro note (as in `tests/test_report_retro.py:12-33`) and `retro.compile(root)` contains `| DIVIDE-1 | merged | done |`. Fails because status stays `queued`.
- [X] T006 In `cli/wuwei/state.py` `_move`, set `status` to `done` when the phase becomes `merged` (plan section 3).

## One close steward review per day (US3, FR-004, FR-005)

- [X] T007 In `tests/test_records_after_dryrun4.py`, add a failing test using the `tests/test_steward.py` `root` fixture pattern (workspace with empty config, approved state) and a fake runtime (`registry.load` returning `SimpleNamespace(dispatch=...)` that counts calls and returns `registry.Result(0, {'agent_type': 'wuwei:steward'})`, as in `test_fresh_seat_run_and_pending_decision_queue`), with `workspace.guard_scope` patched to the root and `close.closing.check` patched to `(1, 'OWED: retro')`: `close.run(SimpleNamespace(check=None)) == 1` leaves exactly one `briefs/steward-*.md` and one `steward.run` event with trigger `close`; then `main(['steward', 'run', '--trigger', 'close']) == 0` prints `steward: close review already ran today (brief ` plus that brief's path, dispatches nothing more, and the brief count and `steward.run` event count are unchanged; a second `close.run` keeps them unchanged too; `steward.run(root, trigger='sweep')` still writes a new brief. Fails because the second close run writes a second brief.
- [X] T008 In `tests/test_steward.py`, rewrite `test_close_retry_uses_existing_steward_run`: keep the recorded close `steward.run` event, drop the `steward.run` fail-stub, and instead patch `registry.load` to `pytest.fail('duplicate steward dispatch')`; `close.run` still returns 1 and no `briefs/steward-*.md` exists. `test_sweep_and_close_trigger_steward` stays unchanged and green. (Passes before and after; it pins the no-dispatch behaviour at the right level once the check moves.)
- [X] T009 In `tests/test_records_after_dryrun4.py`, add a failing test: `skills/wuwei-retro/SKILL.md` does not contain `if today's close review has not run` and does contain `wuwei close` together with `steward_launch` in step 1. Fails on the current step 1 text.
- [X] T010 In `cli/wuwei/steward.py` `run`, add the once-per-day close no-op; in `cli/wuwei/commands/close.py`, call `steward.run(root, trigger='close')` unconditionally and drop the now-unused `watch` import; rewrite step 1 of `skills/wuwei-retro/SKILL.md` (plan section 4). Run `tests/test_steward.py`, `tests/test_launch_contract.py` and `tests/test_stop.py`.

## config.toml errors (US4, FR-006)

- [X] T011 In `tests/test_records_after_dryrun4.py`, add a failing table test over two configs, a syntax error (`repos = []\n[[repos]]\nname = "a/b"\npath = "r"\ndefault_branch = "main"\n`) and a schema error (`nonsense = 1\n`): `workspace.load_config(root)` raises `workspace.ConfigError` whose message starts with `config.toml: ` and does not contain `str(root)`; `guards.integrity.check({'cwd': str(root), 'tool_name': 'Bash', 'tool_input': {'command': 'ls'}})` returns `(2, message)` with `message.startswith('config.toml:')`; `guards.integrity.session_start({'cwd': str(root)})` the same. Add one hook-level case: piping a PreToolUse `ls` payload (all required fields: `session_id`, `transcript_path`, `cwd`, `hook_event_name`) through `cli(root, 'hook', 'PreToolUse', input=...)` exits 2 and `permissionDecisionReason` starts with `config.toml:`. Fails because the message starts with the absolute path and the guard prefixes `integrity unmeasured:`.
- [X] T012 In `cli/wuwei/workspace.py` `load_config`, prefix `config.toml: `; in `cli/wuwei/guards/integrity.py`, return a `ConfigError` message unprefixed in both `check` and `session_start` (plan section 5). Run `tests/test_workspace.py`, `tests/test_memory_lint.py`, `tests/test_integrity.py` and `tests/test_hooks.py`.

## JSON records (US5, FR-007)

- [X] T013 In `tests/test_records_after_dryrun4.py`, add a failing test in the `tests/test_report_retro.py:69-80` setup with `wuwei.report.metrics.collect` patched to return the real `metrics.collect(root)` result with `review_rework` replaced by `{'mean_per_pr': 0, 'median_per_pr': 0, 'p90_per_pr': 0.0, 'share_with_rework': 0.0}`: `main(['report']) == 0`, the `Review rework:` value (text between `Review rework: ` and `; baseline`) parses with `json.loads` to that mapping, and the report contains no `{'`. Fails on the Python repr.
- [X] T014 In `tests/test_build_next.py` `test_claude_launch_check_continue_done_idempotent`, after the `continue` action is read, add a failing assertion: the text after the first `': '` of `action['feedback']` parses with `json.loads` to `{'test_ids': ['test_one'], 'error': 'failure'}`, and the `build check` stderr contains `"test_ids"`. Fails on the repr.
- [X] T015 In `cli/wuwei/report.py` `build` and `cli/wuwei/commands/build.py` line 360, print mapping values and check data as JSON (plan section 6). Run `tests/test_report_retro.py`, `tests/test_operator_records.py`, `tests/test_build.py` and `tests/test_build_next.py`.

## drafts approve confirms on the host terminal (US6, FR-008)

- [X] T016 In `tests/test_drafts.py`, capture `REAL_CONFIRM = integrity._host_confirm` at module import and stub `wuwei.integrity._host_confirm` to `lambda value, **kwargs: True` in the `root` fixture so existing approve tests keep passing. Add failing tests using the `root` and `port` fixtures and a stored approve-tier draft (as `test_owner_approval_sends_original_once` does): (a) `/dev/tty` unavailable (restore `REAL_CONFIRM`, patch `builtins.open` for `'/dev/tty'` to raise `OSError(6, 'Device not configured')`, as `tests/test_decision.py:600-617`): `main(['drafts', 'approve', id]) == 2`, stderr contains `this is an owner action: run it in a host terminal`, the adapter sent nothing and the draft is still `pending`; (b) `_host_confirm` stubbed to return False: exit 1, stderr contains `drafts: owner confirmation declined`, nothing sent, still `pending`; (c) a recording stub: the digest it receives is `sha256(id + '\n' + text)` of the draft and its prompt contains the destination and the text. Fails because approve sends without asking.
- [X] T017 In `cli/wuwei/drafts.py` `approve`, confirm through `integrity._host_confirm` after lint and before the claim (plan section 7). Run `tests/test_drafts.py`, `tests/test_owner_actions.py`, `tests/test_dashboard.py` and `tests/test_launcher_relevance.py`.
- [X] T018 In `tests/test_records_after_dryrun4.py`, add a failing test: `docs/site/reference.md` has a row `| \`bin/wuwei drafts approve <id>\` | yes |` and a row for `drafts drop <id>` with `no`. Then update `docs/site/reference.md` (plan section 7).

## init hints (US7, FR-009)

- [X] T019 In `tests/test_records_after_dryrun4.py`, add a failing test: `cli(project, 'init')` in a fresh directory exits 0, `stdout.splitlines()[1]` still parses as the `statusLine` JSON, line 2 contains `.claude/settings.json` and `statusLine`, and no line equals `.wuwei/`; in a second directory with a `.git` directory created first, the output also contains a line mentioning `.gitignore` followed by the lines `.wuwei/` and `.claude/`. Fails because init prints neither hint.
- [X] T020 In `cli/wuwei/commands/init.py`, add `_status_line` and use it in `run` and `upgrade`, and print the `.gitignore` lines when the project has `.git` (plan section 8). Run `tests/test_signal_status.py`, `tests/test_workspace.py` and `tests/test_integrity.py`.

## Finish

- [X] T021 Run the full suite, `python -m pytest -q`, from the repository root; everything passes. Check every file written for em-dashes, emojis and absolute local paths and remove any.

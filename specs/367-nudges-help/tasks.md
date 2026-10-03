# Tasks: readable nudges, grouped help and a short session-start block

**Input**: `specs/367-nudges-help/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names (`python -m pytest -q ...`). All new
tests are in process. Neutral fixture names only; no absolute local paths.

## Phase 1: US1 nudges (P1)

- [X] T001 Test, `tests/test_signal_status.py`: `test_issue_acceptance_adapter_none_is_silent`.
  `classify({'kind': 'adapter: none', 'payload': {'adapter': 'none', 'kind': 'scanner',
  'call': 'audit', 'exit': 2, 'reason': 'unmeasured', 'performed': False}}, {})` is
  `('silent', 'Work')`; with `day(tmp_path, {'cap': 1, 'items': {}}, [two such events])`,
  `status.attention(day_dir)` is `[]` and `main(['status', '--line'])` prints `nudges 0`
  (set `WUWEI_WORKSPACE` and `WUWEI_NOW` as the neighbouring tests do). In
  `test_emitted_kinds_have_intended_tiers` change `'adapter: none': 'nudge'` to
  `'silent'`. Run `python -m pytest -q tests/test_signal_status.py -k "adapter_none or
  intended_tiers"`; it fails on `('nudge', 'Work')`.
- [X] T002 Implement, `cli/wuwei/signal.py`: add `'adapter: none'` to `SILENT` (plan 1).
- [X] T003 Test, `tests/test_signal_status.py`: `test_issue_acceptance_nudges_print_lines`,
  one fixture via `day()` with `decision_routes` `{'D-1': {...}}` (no outcome), two
  `mcp.checked` events `{'exit': 2}`, two `adapter: none` events, one `decision.replied`
  for a second routed `D-2` (`option` `A`), and one event of a kind with no table entry
  and a plain reason (for example `{'kind': 'build.parked', 'payload': {'reason':
  'ITEM-1 parked'}}`). Assert `main(['nudges']) == 0` and stdout lines are exactly, in
  order of `attention`:
  `nudge: The last MCP registry check did not pass or could not run (2 times). Run: wuwei mcp check`,
  `nudge: ITEM-1 parked. Run: wuwei next`,
  `nudge: D-1 pending owner decision. Run: wuwei decision show D-1`,
  `nudge: D-2 answered from the phone: option A, confirm with decision outcome D-2 A`
  (build the expected list from `attention(day_dir)` order rather than hard-coding the
  order if `scan` sorts differently). Assert `main(['nudges', '--json'])` prints
  `json.dumps(attention(day_dir), allow_nan=False)` with both `mcp.checked` rows. Empty
  day: `No open pages or nudges.`; no day directory: human prints the same line and
  `--json` prints `[]`. Run `python -m pytest -q tests/test_signal_status.py -k
  nudges_print_lines`; it fails because stdout is a JSON array.
- [X] T004 Test, `tests/test_signal_status.py`: `test_nudge_line_actions`, a parametrized
  table over `nudges.line(row, 1)` for each `ACTIONS` source (`item.escalated` reason
  `ITEM-1` gives `... Run: wuwei why ITEM-1`; `draft.created` gives `... Run: bin/wuwei
  drafts`; `watch: health` keeps its reason and runs `wuwei doctor`; `decision.answered`
  keeps its reason with no `Run:`), a
  `decision.pending` row with an empty reason (no crash, `Run: wuwei next`), a reason
  containing `/wuwei:wuwei-plan` (no `Run:`), and a page and a nudge with the same source
  and reason that stay two lines in `run` output. Run `python -m pytest -q
  tests/test_signal_status.py -k nudge_line_actions`; it fails on the missing `line`.
- [X] T005 Implement, `cli/wuwei/commands/nudges.py`: `--json`, `ACTIONS`, `line(row,
  count)`, merged output and the empty line (plan 2). T003 and T004 pass.
- [X] T006 Update, the tests listed in plan section 2 that parse `main(['nudges'])` or
  `day.run('nudges')` as JSON: pass `--json`. Run `python -m pytest -q
  tests/test_signal_status.py tests/test_quiet_sweeps.py tests/test_operator_records.py
  tests/test_watch.py tests/test_listen.py tests/test_sessions.py tests/test_pr_actions.py
  tests/test_records_after_dryrun4.py tests/test_remote.py tests/test_e2e_day.py`.

## Phase 2: US2 grouped help (P1)

- [X] T007 Test, `tests/test_cli.py`: `test_issue_acceptance_grouped_help`, in process
  (`from wuwei.__main__ import main`, `capsys`). `main(['--help']) == 0`; stdout has the
  three headings Daily, Owner, Recovery in that order and no Plumbing or Other heading;
  `next` is listed after the Daily heading and before Owner, `setup` under Owner,
  `doctor` under Recovery; none of `hook`, `event`, `git-hook`, `payload`, `signal`,
  `board` is a listed name; the output names `bin/wuwei --help --all`; no `{agents,` brace
  list. `main(['-h'])` is the same. For `['--help', '--all']`, `['--all', '--help']` and
  `['--all']`: exit 0, Plumbing heading present, and the listed names (`re.findall(r'^  ([a-z-]+) ', out, re.M)`)
  are each listed once and equal the set of command modules (module names under
  `cli/wuwei/commands` not starting with `_`, `_` replaced by `-`). Run `python -m pytest
  -q tests/test_cli.py -k grouped_help`; it fails on `SystemExit` from argparse help
  (or missing headings).
- [X] T008 Implement, `cli/wuwei/__main__.py`: `metavar="<command>"`, `GROUPS`, `_help`
  and the top-level help branch (plan 3).
- [X] T009 Test, `tests/test_cli.py`: extend `test_help` (subprocess, plugin copy with the
  `probe` command): `probe` and its help appear after an `Other` heading in `--help`.
  Confirm `test_usage_errors` and `test_version` still pass. Run `python -m pytest -q
  tests/test_cli.py`.
- [X] T010 Update, `tests/test_docs.py::test_reference_lists_every_cli_command`: run
  `--help --all` and collect names with `re.findall(r'^  ([a-z-]+) ', stdout, re.M)`. Run
  it; it fails until T011 only if the reference misses a command, otherwise passes.
- [X] T011 Docs, `docs/site/reference.md`: the Commands intro line and the `Plumbing: `
  prefix on the plumbing rows (plan 5).

## Phase 3: US3 short session-start block (P1)

- [X] T012 Test, `tests/test_next.py`: `test_issue_acceptance_session_start_budget`.
  Fixture: `approved(root, {f'ITEM-{n}': ('implement', {}) for n in (1, 2, 3)}, cap=3,
  builds={...each item: {'status': 'ready', 'brief': 'briefs/b.md', 'action':
  {'action': 'launch', 'prompt': 'LAUNCH-PROMPT ' + 'x' * 4000}}},
  seats={'b1': {'role': 'builder', 'item': 'ITEM-1', 'status': 'running', 'brief':
  'briefs/b1.md'}}, decision_routes={'D-1': {}, 'D-2': {}})`; copy `spine.md`,
  `index.md` and `goals.md` from `templates/workspace/memory` into `.wuwei/memory` and
  create `notes/`. Run `hook(monkeypatch, root)`, read `context(capsys)`. Assert
  `len(text.encode('utf-8')) <= 4096` (constant `BUDGET = 4096` in the test, one comment
  saying it is the issue's fixed budget), `'Next: decision: '` in text,
  `'Open decisions: D-1, D-2'` in text, `'Goals: '` and `'Plan: '` in text,
  `'Full day state: wuwei state get'` in text, and none of `'LAUNCH-PROMPT'`,
  `'Today state:'`, `'"approved_items"'`. Run `python -m pytest -q tests/test_next.py -k
  budget`; it fails on the size (over 12000 bytes) and the prompt marker.
- [X] T013 Update, `tests/test_watch.py`: `test_session_payload_omits_watch_state` asserts
  the pointer line and no `'"raised_prs"'`; rename
  `test_session_payload_lists_drafts_without_bodies` to
  `test_session_payload_carries_no_drafts` and assert neither the body, `"inputs"` nor
  `C2` is in the content. Run `python -m pytest -q tests/test_watch.py -k session_payload`;
  both fail on `main`.
- [X] T014 Implement, `cli/wuwei/memory.py::session_payload`: drop the state JSON and the
  drafts mapping, add the pointer line (plan 4).

## Phase 4: Docs and full run

- [X] T015 Docs, `docs/site/configuration.md` nudges paragraph and `docs/site/daily.md`
  Re-anchoring bullet (plan 5). Run `python -m pytest -q tests/test_docs.py`.
- [X] T016 Full suite: `python -m pytest -q`. Check every file you wrote for em-dashes,
  emojis and absolute local paths and remove any.

# Implementation Plan: nudges.mode, off under autonomous

**Branch**: `742-nudges-off` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Add `nudges.mode` (`""` follows `autonomy.mode`) and one filter, `status.surfaced`, between
the raw attention rows and the four surfaces that show nudges: the status line and
`status --json` (via `snapshot`), `wuwei nudges`, the board's Attention table and doctor's
count. Classification (`signal.classify`), `status.scan` and `status.attention` do not change.
The interview's autonomy answer sets the mode through the default; `init --upgrade` prints a notice when the key is
absent.

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, no new event kind, no new state
key. The status line path gains no file read: `snapshot` already loads the config and state
that `surfaced` needs.

## Constitution Check

- I stdlib only: yes.
- II exits: unchanged; `wuwei nudges` keeps exit 0 clean and 2 on an unreadable record.
- III one behaviour, one function: the mode filter lives only in `status.surfaced`; every
  surface calls it. The effective mode lives only in `workspace.nudge_mode`.
- IV test first: tasks put each test before its code.
- V ponytail: one schema row, one resolver, one filter, one flag; no classification rewrite.
- VII: no guard, refusal or decision rule changes; no 9.2 invariant row owed.

## Changes, by file

### `cli/wuwei/workspace.py`

- `SCHEMA`: add next to `"autonomy"`:
  `"nudges": {"mode": (str, "", ("", "off", "next", "all"))},`
  with a `# #742:` comment saying `""` follows `autonomy.mode`.
- New `nudge_mode(config)` beside `verbosity` (`workspace.py:429`):
  `return config['nudges']['mode'] or ('off' if config['autonomy']['mode'] == 'autonomous' else 'next')`.

### `cli/wuwei/commands/status.py`

- New function `surfaced(directory, rows, data=None, config=None)` returning `(mode, rows)`:
  1. `config is None` and `directory.parents[1] / 'config.toml'` is a file: load it with
     `workspace.load_config(directory.parents[2])` (the same pattern `scan` uses at
     `status.py:242`). Still no config: mode `all`.
  2. `all`: return the rows unchanged.
  3. Keep every row whose tier is not `nudge`; under `next` also keep rows whose source is
     `decision.answered`.
  4. Under `next` append the derived rows from `data` (read with
     `state.read_state(directory=directory)` only when `data` is None and the mode is `next`):
     - for each item in `data['items']` with phase `fix` and no `state.in_flight(data)` row
       naming it: `{'tier': 'nudge', 'source': 'round.ready', 'lane': 'Work', 'reason':
       f'{name} fix round is ready: run wuwei build next {name}'}`;
     - when `data['gate_approved']`, `data['approved_items']` is non-empty, every approved
       item present in `data['items']` has phase in `('merged', 'parked', 'escalated')`, at
       least one is `merged`, `state.in_flight(data)` is empty and `data.get('close_requested')`
       is falsy: one row `{'tier': 'nudge', 'source': 'close.ready', 'lane': 'Work', 'reason':
       f'{merged} merged and nothing left to build: run wuwei close'}`.
  Inline the terminal tuple; do not import `commands.next` (it imports `status.scan`).
- `snapshot` (`status.py:255`): after `scan`, call
  `result['nudges_mode'], shown = surfaced(directory, active, data, config)` and set
  `result['nudges'] = sum(row['tier'] == 'nudge' for row in shown)`. Leave `pages`,
  `answered`, `trace_gaps` and `prs_changed` on the raw `active` rows (they are not nudge
  counts). `nudges_mode` is set for `line=True` too.
- `_groups` (`status.py:381`): `attention = [f'pages {data["pages"]}']`, then append
  `f'nudges {data["nudges"]}'` unless `data.get('nudges_mode') == 'off'`. A snapshot without
  the key (remote, tests, fixtures) keeps the token.

### `cli/wuwei/commands/nudges.py`

- `register`: add `--all` (`help='every open cause, whatever nudges.mode says'`).
- `run`: after `rows = attention(day)`, unless `args.all`, `rows = surfaced(day, rows)[1]`.
  The `FileNotFoundError` branch (no day yet) stays and skips the filter. Use
  `getattr(args, 'all', False)`: a test calls `nudges.run` with a bare namespace
  (`tests/test_signal_status.py:849`).
- `ACTIONS`: no new entry; the derived reasons already name their command, so `line` adds no
  `Run: wuwei next` suffix (it checks `'wuwei ' in reason`).

### `cli/wuwei/commands/board.py`

- `read` (`board.py:161`): the Attention table lists
  `status.surfaced(directory, status.attention(directory), data, config)[1]`. `data` and
  `config` are already loaded in `read`.

### `cli/wuwei/commands/doctor.py`

- `_day` (`doctor.py:618`): count nudges from `status.surfaced(workspace.day_dir(root), found,
  config=config)`; the row text becomes
  `f'{nudges} shown, nudges.mode {mode} (wuwei nudges --all lists every open cause)'`.
  The traces row's fix becomes `read the traces.gap reasons in wuwei nudges --all, then run
  wuwei doctor`. Page rows and the gap and untraced counts stay on the raw `found`.

### `cli/wuwei/interview.py`

- No change (changed during implementation). The `""` default already gives `off` for the
  Autonomous answer and `next` for Supervised. Adding `nudges.mode` to the effects would make
  `interview._configured` ask the autonomy question again on every configured workspace
  without the key, and would pin `off` after a hand move to supervised.

### `cli/wuwei/commands/init.py`

- `upgrade`, beside the interview notice (`init.py:440`, a read that prints under
  `--dry-run` and counts no change): when `'mode' not in tomllib.loads(migrated).get('nudges',
  {})`, print
  `f'nudges.mode unset, so nudges follow autonomy.mode: {workspace.nudge_mode(loaded)}; set nudges.mode = "next" or "all" in config.toml to see more'`
  where `loaded = workspace.load_config(destination.parent, raw=migrated)` (already computed for
  the interview notice; reuse it). Not added to the "No workspace changes needed" condition.

### `templates/workspace/config.toml`

- Beside the commented `# [autonomy]` block (line 274), a commented block:
  `# [nudges]` and
  `# mode = "" # off, next or all. Empty follows autonomy.mode: off when autonomous, next when supervised.`
  Commented, so `tests/test_docs.py:399` (no table but `[spec]` has a `mode =` line) holds and
  upgrade adds nothing.

### Docs

- `docs/site/configuration.md`: a row for `nudges.mode` (`""`; what each value shows, `--all`);
  the autonomy answer row (line 372) and the intro list (line 3) name `nudges.mode`.
  `tests/test_docs.py:377` requires the `nudges.mode` row once the template names the key.
- `docs/site/reference.md`: the status line paragraph (line 182) says the nudge token and count
  follow `nudges.mode` and are absent under `off`; the `bin/wuwei nudges` row (line 51) names
  `--all`. Example lines in `daily.md:250` and `remote.md:270` that show `nudges 0` under an
  autonomous default drop the token or name the mode; change only lines a test or the default
  makes wrong.

## Shared helpers reused

- `status.scan` / `status.attention`: the raw rows, unchanged.
- `state.in_flight`: running seats and fast checks per item (the round is running).
- `workspace.load_config` and the `directory.parents[1] / 'config.toml'` existence check
  already used in `scan` and `snapshot`.
- `init.upgrade`'s read-only notice pattern (`init.py:440`).

## What must not change

- `signal.classify`, `SILENT`, the tiers and lanes; `status.scan` and `status.attention`
  output (session start's phone-answer lines read `attention`, `next.step` reads `scan`).
- Pages on every surface and `pages N` on the line, in every mode.
- Every event producer and `events.jsonl`; `listen.notify` DMs.
- `status --json`'s `nudges` stays a non-negative integer (SwiftBar
  `templates/swiftbar/wuwei.1m.sh:29`).
- Under `nudges.mode = "all"`: the status line, `--json` counts and `wuwei nudges` output equal
  main's for the same day.
- No new file read on the `status --line` path.

## Test files

- `tests/test_nudges_mode.py` (new): the resolver, `surfaced` per mode, the status line and
  `--json`, `wuwei nudges` with and without `--all`, board, doctor, the three `next` subjects
  and the excluded sources, upgrade notice, interview effects, invalid value.
- Existing tests that read the raw classification through a surface under a default config:
  run the suite after the code and move each to `--all`, `status.attention` or a config with
  `[nudges]\nmode = "all"`, never weakening an assertion. Expected: `tests/test_signal_status.py`
  (lines 134, 142, 642, the `nudges --json` and text tests from 497 to 849),
  `tests/test_quiet_sweeps.py`, `tests/test_shadow.py:111`, `tests/test_records_after_dryrun4.py`,
  `tests/test_sessions.py:267`, `tests/test_cruise.py:289`, `tests/test_budget_classes.py:191`,
  `tests/test_listen.py:501`, `tests/test_operator_records.py:67`, `tests/test_pr_actions.py:192`,
  `tests/test_watch.py:610`, `tests/test_doctor.py:596`. Moved in the end: test_signal_status, test_quiet_sweeps, test_shadow, test_records_after_dryrun4, test_sessions, test_budget_classes, test_cruise, test_listen, test_operator_records, test_pr_actions, test_board_mcp (compares to `surfaced`) and test_hooks (the status-line budget test now expects the autonomous line without the nudge token).
  Tests without a `config.toml` see `all` and need no change.

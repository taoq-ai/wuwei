# Implementation Plan: readable nudges, grouped help and a short session-start block

**Branch**: `367-nudges-help` | **Date**: 2026-10-03 | **Spec**: spec.md

## Summary

Four small edits at the shared spots, no new module:

1. `cli/wuwei/signal.py`: add `'adapter: none'` to `SILENT`.
2. `cli/wuwei/commands/nudges.py`: `--json` keeps today's print; the default prints merged
   human lines from a small `ACTIONS` table.
3. `cli/wuwei/__main__.py`: a `GROUPS` table and a top-level help printer.
4. `cli/wuwei/memory.py::session_payload`: the state JSON becomes one pointer line.

Reused, not copied: `status.attention` (the rows), `signal.SILENT` (the silent-kind list
every surface reads through `classify` and `scan`), `memory.constraints` (goals, plan,
open decisions, briefs, from #288), `next_command.orientation` (the `Next:` line, from
#358), `wuwei state get` (full state on request), the `hook()` and `context()` helpers
and the `root`/`calibrated`/`approved` fixtures in `tests/test_next.py`, and the
`day()` helper in `tests/test_signal_status.py`.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Every new test is in process: `main([...])`
from `wuwei.__main__` with `capsys`, and `hook.run` with
`tests/payloads/SessionStart/recorded.json`. No subprocess, no adapter, no network.

## Constitution Check

- I stdlib only: yes (`argparse`, `json`).
- II three-state: `nudges` keeps 0 on success and 2 with the reason on an unreadable day;
  help exits 0. Silencing `adapter: none` changes only the attention tier: the adapter
  still returns exit 2 `unmeasured` to its caller, and the caller reports it.
- III one behaviour, one function: tiering stays in `signal`, rows in `status.scan`,
  constraints in `memory.constraints`, the next step in `next.step`. `nudges` only formats.
- IV test first: tasks.md orders each test before its code.
- V ponytail: no new module, no config key, no runtime byte truncation, no reason rewrites
  at producers, no `action` field in JSON rows.
- VII security: the payload carries less (no launch prompts, no absolute paths from
  state, no draft destinations). Nothing new is trusted, so no `state.RESERVED` change.
  Scope (spec 9.1): `nudges` and help do not refuse anything; SessionStart outside a
  workspace stays silent through `lifecycle.scoped`.

## 1. `adapter: none` is silent (`cli/wuwei/signal.py`)

Add `'adapter: none'` to the `SILENT` tuple (next to the other routine kinds). `classify`
then returns `('silent', lane)` and `status.scan` skips it at its `if kind in SILENT:
continue`. No change to `registry.record_none` (the event is still written; `why` and the
retro can still read it).

Tests to update: `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`
expects `'adapter: none': 'nudge'`; change it to `'silent'`.

## 2. Human nudges (`cli/wuwei/commands/nudges.py`)

```python
# source: (text, command); {reason} is the row reason, {id} its first word.
ACTIONS = {
    'decision.pending': ('{reason}', 'wuwei decision show {id}'),
    'decision.answered': ('{reason}', None),  # the reason names decision outcome D-n <option>
    'item.escalated': ('{reason} is escalated and waits for the owner', 'wuwei why {reason}'),
    'mcp.checked': ('The last MCP registry check did not pass or could not run',
                    'wuwei mcp check'),
    'draft.created': ('An outward draft waits for owner approval', 'bin/wuwei drafts'),
    'watch: health': ('{reason}', 'wuwei doctor'),
    'listen: health': ('{reason}', 'wuwei doctor'),
    'watch: sweep:unmeasured': ('A sweep could not read a record (unmeasured)', 'wuwei doctor'),
}
```

- `register`: add `--json` (`store_true`).
- `run`: read `rows = attention(workspace.day_dir())` as today. `FileNotFoundError` means
  `rows = []`. With `--json` print `json.dumps(rows, allow_nan=False)` exactly as today
  (including `[]` for the missing day). Without it, merge with a dict keyed by
  `(tier, source, reason)` that keeps first-seen order and counts, and print one line per
  key via `line(row, count)`; print `No open pages or nudges.` when empty. Exit 0. The
  existing `except (OSError, ValueError, KeyError, TypeError)` exit 2 path is unchanged.
- `line(row, count)`: look up `ACTIONS.get(row['source'])`. With an entry and a non-empty
  reason, format text and command (when not `None`) with
  `reason=row['reason'], id=row['reason'].split()[0]`.
  Without an entry (or an empty reason), text is the reason and the command is `None` when
  `'wuwei ' in reason or '/wuwei:' in reason`, else `'wuwei next'`. Return
  `f'{tier}: {text}' + (f' ({count} times)' if count > 1 else '') + (f'. Run: {command}' if command else '')`.

Tests calling `main(['nudges'])` and parsing JSON switch to `main(['nudges', '--json'])`:
`tests/test_signal_status.py` (lines near 425, 455, 481), `tests/test_quiet_sweeps.py`
(46, 53, 293, 308, 329, 356), `tests/test_operator_records.py` (67),
`tests/test_watch.py` (567), `tests/test_listen.py` (501), `tests/test_sessions.py` (241),
`tests/test_pr_actions.py` (190), `tests/test_records_after_dryrun4.py` (28),
`tests/test_remote.py` (790), and `tests/test_e2e_day.py` (`day.run('nudges')`, 65 and
68). Check each: a call that only asserts the exit code can stay as is.

## 3. Grouped help (`cli/wuwei/__main__.py`)

- `subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")`.
- Module-level table, in the order printed. As built, each group's names are one
  space-separated string split at use: `tests/test_state_allowlist.py::reader_inventory`
  reads every identifier string in a tuple as a state key, and a tuple holding `note`
  failed the generic-write check for `items.A.note`. The sketch below shows membership.

```python
GROUPS = (
    ('Daily: the session runs these through the day', (
        'next', 'status', 'nudges', 'plan', 'decision', 'worktree', 'brief', 'build',
        'dispatch', 'pr', 'merge', 'reply', 'discover', 'note', 'metrics', 'report',
        'retro', 'close', 'steward')),
    ('Owner: run these in your own host terminal', (
        'setup', 'init', 'config', 'calibrate', 'goals', 'voice', 'drafts', 'remote',
        'mcp', 'outbound', 'watch', 'listen', 'dashboard', 'promote', 'consolidate')),
    ('Recovery: when something is stuck', (
        'doctor', 'why', 'state', 'shadow', 'heartbeat', 'integrity', 'runtime',
        'sessions')),
    ('Plumbing: hooks, seats and the plugin call these', (
        'agents', 'board', 'event', 'fast-checks', 'git-hook', 'hook', 'index', 'memory',
        'payload', 'rank', 'signal', 'sweep', 'verdict')),
)
```

- In `_main`, after the registration block and before `parser.parse_args`:
  `if argv and set(argv) <= {'-h', '--help', '--all'}: print(_help(parser, subparsers, '--all' in argv)); return CLEAN`.
- `_help(parser, subparsers, everything)`: `helps = {a.dest: a.help or '' for a in subparsers._choices_actions}`
  (argparse keeps the one-line help only there; the attribute is present on 3.11 to 3.14).
  Start with `parser.format_usage().rstrip()`. For each group (skip Plumbing unless
  `everything`), a blank line, the heading, then `f'  {name:<13} {helps[name]}'` for each
  name present in `helps`. Names in `helps` that no group lists go under a last heading
  `Other`, always shown. End with `bin/wuwei <command> --help shows its options.` and,
  when plumbing is hidden, `bin/wuwei --help --all also lists the plumbing commands.`

Must not change: `--version`, subcommand help, the usage error for a bare call or an
unknown command (exit 2), the exit-status contract, the lazy single-module registration
path for a named subcommand.

Tests to update: `tests/test_docs.py::test_reference_lists_every_cli_command` reads the
`{...}` list from `--help`; switch it to `--help --all` and collect names with
`re.findall(r'^  ([a-z-]+) ', stdout, re.M)`. `tests/test_cli.py::test_help` keeps passing
because the copied `probe` command lands under `Other`.

## 4. Short session-start payload (`cli/wuwei/memory.py::session_payload`)

Delete the `data.pop('watch', None)`, the drafts import and mapping, and `state_text`.
Content becomes:

```python
content = (f'{active}\nSpine:\n{spine.rstrip()}\n\nIndex:\n{index.rstrip()}\n\n'
           f'Full day state: wuwei state get\n{promote_line}\n')
```

`data = state.read_state(root)` stays (it feeds `constraints`, and a broken state still
fails closed as `memory unmeasured` in `lifecycle.session_start`). `json` stays imported
(used further down). Nothing changes in `lifecycle.py`; `wuwei payload` prints the same.

Tests to update in `tests/test_watch.py`: `test_session_payload_omits_watch_state`
asserts `'"raised_prs"' in content`; change it to assert `'Full day state: wuwei state get'`
is in the content and `'"raised_prs"'` is not. `test_session_payload_lists_drafts_without_bodies`
asserts `'"DR-1": "C2"'`; keep its body and `"inputs"` assertions, assert `'C2'` is not in
the content either, and rename it `test_session_payload_carries_no_drafts`.

## 5. Docs

- `docs/site/reference.md` line 11: `Every command bin/wuwei --help --all prints; bin/wuwei
  --help groups them and leaves out the plumbing.` Prefix `Plumbing: ` to the "What it
  does" cell of the plumbing rows that lack it (`agents`, `fast-checks`, `index`, `memory`,
  `rank`, `signal`, `sweep`, `verdict`).
- `docs/site/configuration.md` (the "Run `bin/wuwei nudges`" paragraph near line 472):
  one line per cause with the command to run, identical causes merged with a count,
  `--json` lists every entry and its count matches `status --line`; "a skipped call to a
  tracker set to `none`" becomes "a call to any adapter set to `none`".
- `docs/site/daily.md` Re-anchoring bullet (line 204): add that the full day state is one
  command away, `bin/wuwei state get`, and is no longer pasted into the session.
- Do not edit `docs/specs/2026-09-24-wuwei-design.md` (owner only; see spec Assumptions).

## Files

| File | Change |
|---|---|
| `cli/wuwei/signal.py` | `'adapter: none'` in `SILENT` |
| `cli/wuwei/commands/nudges.py` | `--json`, `ACTIONS`, `line`, merged output |
| `cli/wuwei/__main__.py` | `metavar`, `GROUPS`, `_help`, top-level help branch |
| `cli/wuwei/memory.py` | `session_payload` drops the state JSON |
| `tests/test_signal_status.py`, `tests/test_cli.py`, `tests/test_next.py` | new tests (no new test file) |
| tests listed in sections 1 to 4 | `--json` and expectation updates |
| `docs/site/reference.md`, `configuration.md`, `daily.md` | text |

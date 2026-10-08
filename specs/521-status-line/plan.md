# Implementation Plan: status --line is one readable line, the detail moves to status

**Branch**: `521-status-line` | **Spec**: `specs/521-status-line/spec.md`

## Summary

`status.line` builds three groups (now, work, attention) from the snapshot it already has and
fits them to a width; a new `status.full` prints the same groups one per line plus the detail
the line drops; `integrity.restart` says the action first. One shared spot (`_groups` in
`cli/wuwei/commands/status.py`) feeds both outputs, so the line and `status` cannot drift.

## Technical Context

Python 3.11 stdlib only. Files: `cli/wuwei/commands/status.py`, `cli/wuwei/integrity.py`,
`cli/wuwei/__main__.py` (fast path namespace only). Tests: `tests/test_signal_status.py`
(new tests and the moved asserts), plus the existing tests listed below. No new module, no new
event kind, no new state key, no new refusal (#530 holds). No data-model, contract or research
file: the snapshot dict is the only entity and it only gains four keys.

## Constitution Check

- I stdlib: yes. II exits: `status` (full) exits 0, or 2 with `WUWEI ? unmeasured` like the
  line. III one behaviour one function: the groups are built once in `_groups`; the restart text
  only in `integrity.restart`; running rows only from `state.in_flight` and
  `state.in_flight_text`. IV test first: every behaviour below has a test task first. V
  ponytail: no formatter class, no config key for the width (a CLI flag with a default). VII:
  no guard touched.
- #551: the line is owner-facing; `wuwei next` already returns the planner's action and the
  running rows with items and start times (`next.py` wait rows), so nothing new for the planner.

## Changes

### `cli/wuwei/integrity.py`

`restart(config)` (line 70): same detection, new text.

```python
names = old[0] if len(old) == 1 else f'{", ".join(old[:-1])} and {old[-1]}'
return f'restart Claude Code: hooks {names} still running (plugin {new} installed)'
```

Docstring updated. `RESTART`, `other_versions`, `newer_template` unchanged. Doctor
(`cli/wuwei/commands/doctor.py:114`) keeps calling it; no code change there.

### `cli/wuwei/commands/status.py`

- `WIDTH = 100` next to `SHADOW_NUDGE`.
- `register`: the `--line`/`--json` group becomes `required=False` (no flag prints the full
  status); add `parser.add_argument('--width', type=int, default=WIDTH)`.
- `snapshot(directory)` adds, after `scan` and the config read:
  - `result['plan'] = (directory / 'plan.md').is_file()`
  - `result['decisions']`: the routed ids with no outcome, in route order. `scan` has already
    validated `decision_routes` is a dict; import `answered` from `wuwei.decision` only when
    `routes` is non-empty (the same lazy import `scan` uses at line 208).
  - `result['plugin'] = integrity.version()` and `result['template'] =
    config['template_version'] if config is not None else None` (`integrity` is already
    imported at line 278).
  Every existing key stays (`seats`, `running`, `cap_bound`, `restart`, ...): `--json`, the
  dashboard, the board and the SwiftBar plugin read them.
- New `_groups(data, shown=None)` returns `[now, work, attention]`, each a list of tokens:
  - now (first match): `data['restart'].split(' (plugin ', 1)[0]`; `'gate waiting'` when not
    `gate_approved` and `data.get('plan')`; `'no plan yet'` when not `gate_approved`;
    `f'decision {decisions[0]} waiting'`; else empty.
  - work: `f'{phase} {count}/{cap}'` for `data['phases']` (as today), then the seat token when
    `gate_approved` or a seat runs: roles = `[role for _, role, _ in data.get('running', [])
    if role != 'checks']` (rows are oldest first already); `names = roles[:shown] + ([f'+{n}
    more'] if cut)`; token `f'seats {len(roles)}/{cap}'` plus `f' ({", ".join(names)})'` when
    names is non-empty. Rows may be tuples (snapshot) or lists (JSON round trip, the board):
    unpack, never index by type.
  - attention: `pages N`, `nudges N`, and `data['posture']` when not in `(None, 'guarded')`.
  Use `data.get(...)` for the four new keys so older snapshot dicts (the board's cockpit,
  tests) still render.
- `line(data, width=WIDTH)` replaces the body at lines 325-362:

```python
def _render(groups):
    return 'WUWEI ' + ' | '.join(' · '.join(group) for group in groups if group)

def line(data, width=WIDTH):
    roles = len(seat_roles)  # same filter as _groups
    for shown in range(roles, -1, -1):
        groups = _groups(data, shown)
        if len(_render(groups)) <= width:
            return _render(groups)
    while len(_render(groups)) > width and sum(map(len, groups)) > 1:
        next(group for group in reversed(groups) if group).pop()
    return _render(groups)
```

  Keep it this shape: the cut loop and the drop loop are the whole truncation rule (FR-004).
  A small `_roles(data)` helper shared by `_groups` and `line` is fine; nothing more.
- New `full(data)`:
  - now line: `data['restart']` (full text) when set, else the `_groups` now token.
  - work line: the `_groups` work tokens plus `f'bound {cap_bound}'` when set and
    `'builders ' + state.goal_split(data['seats'])` when non-empty.
  - one `'running ' + state.in_flight_text([row])` line per `data.get('running', [])` row
    (seats and checks, oldest first; reuse, do not reformat).
  - attention line: the `_groups` attention tokens, then, as today's conditions in `line`:
    `phone answers N`, `loops N`, `prs N changed`, `obligations.SOLO`, `traces: N gaps`.
  - health line: `watch <w>`, `listen <l>`, `health <h>` when set, `sessions N`.
  - calendar line: `reply <due>` when set, `meeting <next or unmeasured>`.
  - versions line: `plugin <plugin or unmeasured> · template <template or none>`.
  Joined with ` · ` inside a line; `'WUWEI ' + '\n'.join(non-empty lines)`.
- `run(args)`: `if args.json` as today; `elif args.line: print(line(data, args.width))`; else
  `print(full(data))`. On error: JSON `{'status': 'unmeasured'}` for `--json`, otherwise
  `WUWEI ? unmeasured`; exit `UNRUN` as today.
- Remove the parts of `line` that moved; the `SOLO` lazy import moves into `full`.

### `cli/wuwei/__main__.py`

Fast path (line 83): `SimpleNamespace(command='status', line=True, json=False,
width=status.WIDTH)`. The `argv == ['status', '--line']` test stays exactly as it is, so the
fast path still skips argparse (`tests/test_hooks.py::test_status_line_skips_parser_and_hashlib`).

### Docs and design spec (FR-009)

- `docs/specs/2026-09-24-wuwei-design.md`: 5.2 availability (line ~460): the line names the
  running seats by role; `wuwei status` and `wuwei next` name items and start times. 5.3 cap
  (line ~498): "the plan, the gate card and `wuwei status` name what bound it". 5.8.2 (line
  ~831): `status` shows `loops N`. 5.9 status line (line ~854): the line's three groups, width
  100, `--width`, and `wuwei status` for the detail; `WUWEI ? unmeasured` unchanged.
- `docs/site/reference.md`: the `status` row (line 67) names `status`, `--line [--width N]`
  and `--json`; Watch state (lines 163-175): watch, listen, sessions, PRs changed and solo show
  in `bin/wuwei status`; the no-plan example becomes `WUWEI no plan yet | pages 0 · nudges 0`;
  heartbeat and traces bullets (lines 201-203): `status` instead of `status --line`, running
  rows in `status`; restart (lines 229-231): new text, and the line starts with it; posture
  (line 376): unchanged meaning, new separator; loops (line 119): `status`.
- `docs/site/daily.md` (example at line 229 and the lines that read the line: 235-237, 273-277,
  340, 367, 376, 435), `docs/site/configuration.md` (lines 28, 167, 170, 557, 574, 648-653):
  name `wuwei status` where a moved part is described; keep the phrases `listen dead`,
  `phone answers`, `loops N` (tests/test_docs.py reads them) and change only the surface named.
  Update the example line to the new shape.

## Existing tests that change (and only these)

Rule: an assertion on a part that moved to `status` asserts on `wuwei status` (or
`status.full(data)`) instead; an assertion on the old separators or order takes the new
shape; nothing is deleted without its replacement. Expected touch list (from a scan of tests
that call the line):

- `tests/test_signal_status.py`: `test_status_line_and_json_share_snapshot`,
  `test_status_line_names_running_seats_and_checks` (running rows to `status`),
  `test_status_counts_every_nonzero_phase`, `test_status_line_names_a_solo_pr`,
  `test_no_plan_yet_before_the_gate`, `test_approved_gate_has_no_plan_yet_prefix`,
  `test_reply_due_at_1500_appears_in_status_line`, `test_status_calendar_failure_is_unmeasured`,
  `test_routed_decision_nudges_until_answered`, the phone answer acceptance tests, the
  heartbeat tests (`health` to `status`), the `pr.changed` tests, the loops tests,
  `test_restart_on_the_status_line` (new text, first token), `test_issue_acceptance_adapter_none_is_silent`,
  `test_status_line_shows_running_seats_per_goal` (becomes roles on the line, goal split in
  `status`), `test_unreadable_state_fails_closed` (also `status` with no flag).
- `tests/test_quiet_sweeps.py` (watch tokens), `tests/test_listen.py` (listen tokens),
  `tests/test_sessions.py` and `tests/test_remote.py` (sessions, phone answers),
  `tests/test_traces.py` (trace gaps), `tests/test_watch.py::test_fresh_day_before_the_plan_is_clean`,
  `tests/test_heartbeat.py`, `tests/test_parallel_dispatch.py`, `tests/test_operator_records.py`,
  `tests/test_pr_actions.py`, `tests/test_shadow.py`, `tests/test_e2e_day.py`,
  `tests/test_setup.py`, `tests/test_board_mcp.py`, `tests/test_docs.py`: only where they
  assert a moved token or the old separator.
- `tests/test_config_transition.py` (lines 185-193) and `tests/test_doctor.py`
  (`test_in_use_row_names_the_restart`): the new restart text.

## What must not change

- `scan` and `attention` (nudges, session start, doctor, next read them), the pages and nudges
  counts, the event classification, one pass over `events.jsonl`.
- `status --json` keys and values that exist today; `WUWEI ? unmeasured` with exit 2.
- The status-line fast path and its latency test; `init`'s status-line snippet
  (`status --line`, no width).
- `state.in_flight`, `state.in_flight_text`, `state.running_by_goal`, `state.goal_split`;
  `wuwei next` and its wait rows (they already carry items and start times).
- `integrity.RESTART`, restart detection (`other_versions`, `newer_template`).
- The remote `status` verb and the board keep calling `status.line(...)` unchanged.

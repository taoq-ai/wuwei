# Implementation Plan: nudges expire, repeats combine and the list is capped

**Branch**: `786-nudge-hygiene` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

All of it lands in `status.scan`, the one function every attention surface reads. The
fallback key `(kind, number)` becomes `(kind, subject)` for non-page rows, so repeats fold into
one row with `count` and `ts`, and the existing silent-event pop now clears its subject. One
small helper at the end of `scan` drops nudges older than `nudges.ttl_hours` and keeps the
newest `nudges.max_open`, appending one `nudges.dropped` row with the counts. `wuwei nudges`
sums `count` and prints the age. Two schema keys, three `count`-aware sums, docs. Observe and
the status line token need no code (spec, Root cause).

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, no new event kind, no new state key,
no new file read on the status line path (`scan` already loads `config.toml` at
`status.py:243-244`).

## Constitution Check

- I stdlib only: yes (`datetime`, `timedelta` already imported in `status.py`).
- II exits: unchanged. `scan` cannot gain a new failure: subjects are keyed as text, and a
  timestamp without an offset is read with `.astimezone()` (local), as `workspace.now` reads
  `WUWEI_NOW`.
- III one behaviour, one function: keying in `scan`, ageing and capping in `status._tidy`, the
  printed form in `nudges.line`.
- IV test first: `tasks.md` orders each test before its code.
- V ponytail: one key change at the shared spot, one helper, two schema rows. No event is
  written, no new clearing rule, no change to classification, producers or `surfaced`.
- VII: no guard, refusal or decision rule changes; no 9.2 invariant row.

## Changes, by file

### `cli/wuwei/workspace.py`

- `SCHEMA['nudges']` (`workspace.py:158`) becomes
  `{"mode": (str, "", ("", "off", "next", "all")), "ttl_hours": (int, 24, 1), "max_open": (int, 20, 1)}`
  with a `# #786:` comment on the two new keys. The loader's existing integer minimum check
  (`workspace.py:574`) refuses 0.

### `cli/wuwei/commands/status.py`

1. Unreadable lines (needed: on a first unreadable line `stamp` is unbound): in the `else:` branch at `status.py:133-134`
   (`kind, payload = 'unreadable event', {}`) also set `stamp = None`, so a row never takes
   the previous line's timestamp.
2. Key (`status.py:155-164`): add one branch before the final `else`:
   - `elif tier == 'page': key = (kind, number)` (pages keep one row per event);
   - final `else` (comment `# #786: one row per subject, so a repeat folds in and a later
     silent event of the kind clears it`):
     `subject = (payload.get('pr') or payload.get('item') or payload.get('reason', kind)) if isinstance(payload, dict) else kind`
     then `key = (kind, str(subject))`.
   The `if tier == 'silent': current.pop(key, None)` line stays as is; it now clears the
   subject's row.
3. Row (`status.py:183`): the dict gains
   `'count': current.get(key, {}).get('count', 0) + 1` and
   `'ts': stamp if isinstance(stamp, str) else None`. Every event-derived row gets both;
   state-derived rows (built after the loop) do not.
4. New module-level helper beside `surfaced`:

   ```python
   def _tidy(rows, now, limits=None):
       """#786: drop nudges quiet for nudges.ttl_hours, keep the newest nudges.max_open, the
       nudges.dropped row included. Pages, and rows without ts, never age out."""
   ```

   - `limits` defaults to `{key: rule[1] for key, rule in workspace.SCHEMA['nudges'].items()}`
     (a day without `config.toml`).
   - `seen(row)`: `datetime.fromisoformat(row['ts']).astimezone()` when `row.get('ts')`, else
     `now`.
   - `nudges = [rows with tier 'nudge']`; `fresh` = those with
     `now - seen(row) <= timedelta(hours=limits['ttl_hours'])`; `expired = len(nudges) - len(fresh)`.
   - If `not expired and len(fresh) <= limits['max_open']`: return `rows` unchanged (same list).
   - Else `kept = sorted(fresh, key=seen, reverse=True)[:limits['max_open'] - 1]`,
     `dropped = len(fresh) - len(kept)`; return the rows in their original order minus the
     nudge rows not in `kept` (compare by `id(row)`), plus
     `{'tier': 'nudge', 'source': 'nudges.dropped', 'lane': 'Work', 'reason':
     f'{expired} expired after nudges.ttl_hours = {ttl}, {dropped} dropped over nudges.max_open = {cap}',
     'expired': expired, 'dropped': dropped}`.
5. End of `scan` (`status.py:252`): sort the tidied rows instead of `current.values()`:
   `rows = sorted(_tidy(list(current.values()), datetime.fromisoformat(classified_state['now']), config['nudges'] if config is not None else None), key=...)`
   (same sort key as today). `classified_state['now']` is set by every caller (`scan` itself,
   `snapshot`, `nudges` via `attention`, lifecycle, next).
6. `snapshot` (`status.py:307`): `trace_gaps` sums `row.get('count', 1)` over `traces.gap`
   rows instead of counting rows.

### `cli/wuwei/commands/nudges.py`

- `ACTIONS` gains `'nudges.dropped': ('{reason}', None)` (its text, no command).
- `line(row, count, now=None)`: build the parenthesis from parts: `f'{count} times'` when
  `count > 1`; when `now` is given and `row.get('ts')`, the age of
  `datetime.fromisoformat(row['ts']).astimezone()`: whole minutes, floored at 0, printed
  `last <m> min ago` under 60, else `last <m // 60> h ago`. Join with `, `; no parts, no
  parenthesis (today's output for rows without `ts`, so `test_nudge_line_actions` holds).
- `run`: per `(tier, source, reason)` keep the summed `row.get('count', 1)` and the newest
  `ts` (by the same parse); call `line(dict(zip(...), ts=newest), count, workspace.now())`.
  `--json` prints the rows as `attention` returns them (now with `count`, `ts` and, when
  present, the `nudges.dropped` row).

### `cli/wuwei/commands/doctor.py`

- `doctor.py:622` and `:625`: `gaps` and `untraced` sum `page.get('count', 1)` over their
  source instead of counting rows.

### `templates/workspace/config.toml`

- Under the commented `# [nudges]` block (`config.toml:278-279`) add two commented lines:
  `# ttl_hours = 24 # A nudge with no new event for this many hours leaves the list.` and
  `# max_open = 20 # At most this many open nudges; the oldest go, counted in one nudges.dropped line.`

### `docs/site/configuration.md`

- Decisions table, after `nudges.mode` (`configuration.md:195`): rows for
  `nudges.ttl_hours` (`24`) and `nudges.max_open` (`20`) in the same words as the template,
  naming the `nudges.dropped` row (`expired` and `dropped` counts).
- The `bin/wuwei nudges` paragraph (`configuration.md:627-632`): repeats of one cause (same
  kind on the same PR, item or reason) are one entry with its count and the age of the newest
  event; a nudge clears when a later event clears its cause, leaves after
  `nudges.ttl_hours` without a new event, and the list keeps the newest `nudges.max_open`.

## What must not change

- `signal.classify`, every producer, `events.jsonl`, `surfaced` and the mode rules (#742).
- Pages: one row per event, never aged out, never dropped, never counted by the cap.
- Rows with a dedicated key (`pr.action`, `merge.policy_blocked`, `pr.changed`,
  `decision.one_way`, `draft.created`, `remote.refused`, `guard.would_refuse`, `watch: sweep`)
  keep their keys; the existing clearing rules keep working.
- State-derived rows (decision pending, answered and cruise, health, escalated, planner stale,
  guards.shadow) keep their exact shape (no `count`, no `ts`): exact-match tests in
  `tests/test_signal_status.py` and `tests/test_listen.py` rely on it.
- `scan`'s return tuple, `attention`'s signature, the shadow report.
- The skip regex fast path (`LINES`, `SKIP`): untouched.

## Existing tests to adjust (same intent, count-aware)

- `tests/test_signal_status.py::test_issue_acceptance_nudges_print_lines`: two `mcp.checked`
  events are one row with `count` 2 (was two rows); the printed line is unchanged.
- `tests/test_signal_status.py::test_scan_reads_the_day_with_universal_newlines` and
  `::test_scan_skip_matches_decoding_every_line`: assert the summed `count` of `hook.warning`
  rows (2 and 3), not the row count. Keep the `skipped == scan(...)` equality check.
- Any other test that turns out to count repeated generic rows: switch to summing `count`, do
  not weaken the check.

## Risk

- Latency: one dict lookup per event and one pass over the rows; no new I/O.
- Information: two events of one kind on one PR with different reasons now show as one row
  with the newest reason. Accepted (spec, Assumptions).

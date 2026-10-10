# Tasks: nudges expire, repeats combine and the list is capped

Test first: each test task is written, run and seen to fail for the expected reason before its
implementation task. New tests go in one new file, `tests/test_nudge_hygiene.py`, in process
(`status.attention`, `status.snapshot`, `status.line`, `main([...])`) with `WUWEI_WORKSPACE`
and `WUWEI_NOW` set (`NOW = '2026-09-28T12:00:00+02:00'`) and a day built under `tmp_path`
(`.wuwei/days/2026-09-28/events.jsonl`, `state.json` `{'cap': 1, 'items': {}}`, and a
`.wuwei/config.toml` with `[nudges]\nmode = "all"\n` plus what the test sets), the way
`tests/test_nudges_mode.py` builds its `day`. Events carry explicit `ts` values relative to
`NOW`. Neutral fixtures only (`acme/widget#1`, items `A`, `B`). Run the touched test files after
each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the settings (FR-003)

- [X] T001 Test in `tests/test_nudge_hygiene.py`: `workspace.load_config` of a `config.toml`
  with no `[nudges]` gives `ttl_hours == 24` and `max_open == 20`; `[nudges]\nttl_hours = 0`
  and `[nudges]\nmax_open = 0` each raise `workspace.ConfigError`.
- [X] T002 Add `ttl_hours` and `max_open` to `SCHEMA['nudges']` in `cli/wuwei/workspace.py`.

## Phase 2: repeats combine on their subject (FR-001, FR-002, US1)

- [X] T003 Test in `tests/test_nudge_hygiene.py` (issue acceptance 1): 50
  `watch: read-failed` events with payload `{'pr': 'acme/widget#1', 'reason': 'could not read'}`,
  `ts` one minute apart ending at `NOW`: `status.attention` has exactly one row with source
  `watch: read-failed`, `count` 50 and `ts` equal to the last event's. Same test, 25 more on
  `acme/widget#2`: two rows, 50 and 25.
- [X] T004 Test in `tests/test_nudge_hygiene.py` (subject change): a `tracker.call` with
  payload `{'item': 'A', 'exit': 2, 'reason': 'label not found'}`, one for item `B` the same,
  then `{'item': 'A', 'exit': 0}`: one `tracker.call` row, for `B`.
- [X] T005 Test in `tests/test_nudge_hygiene.py` (edges): an unreadable first line (`not json`)
  followed by two more unreadable lines gives one `unreadable event` row with `count` 3 and
  `ts` None, and `scan` does not raise; a `hook.warning` whose `reason` is a list folds with its
  repeat (one row, `count` 2); two `security.finding` events stay two page rows with `count` 1.
- [X] T006 Implement in `cli/wuwei/commands/status.py`: `stamp = None` in the unreadable branch,
  the `elif tier == 'page'` branch and the subject key in the final `else` of the key block,
  and `count` and `ts` on the row dict (plan, status.py items 1 to 3).
- [X] T007 Adjust in `tests/test_signal_status.py`: `test_issue_acceptance_nudges_print_lines`
  (one `mcp.checked` row with `count` 2; printed line unchanged),
  `test_scan_reads_the_day_with_universal_newlines` and
  `test_scan_skip_matches_decoding_every_line` (sum `count` of `hook.warning` rows: 2 and 3).
  Run the file; fix any other repeat-counting assertion the same way.

## Phase 3: counts that read rows stay true (FR-006)

- [X] T008 Test in `tests/test_nudge_hygiene.py`: three `traces.gap` events with the same
  payload (`{'reason': 'r', 'span': 's', 'session': 's'}`) and three identical
  `subagent.untraced` events (`{'agent_type': 'Explore', 'agent_id': 'a1', 'reason': 'no seat'}`):
  `status.snapshot(directory)['trace_gaps'] == 3`; `doctor._day(root, config, probes)` with the
  `probes` dict `tests/test_traces.py:732` uses gives the `traces` row `3 gaps today` and the
  `untraced subagents` row `3 stopped with no seat today`.
  Note: this test passed before any change, since repeats were separate rows then; it guards
  T009, which keeps the counts true once T006 folds the rows.
- [X] T009 Implement: `trace_gaps` in `snapshot` (`cli/wuwei/commands/status.py`) and `gaps`,
  `untraced` in `_day` (`cli/wuwei/commands/doctor.py`) sum `row.get('count', 1)`.

## Phase 4: expiry and the cap (FR-004, US2)

- [X] T010 Test in `tests/test_nudge_hygiene.py` (issue acceptance 2): `nudges.ttl_hours = 1`;
  a `retro.gap` at `NOW - 2 h`: no `retro.gap` row in `status.attention`, and one
  `nudges.dropped` row with `expired` 1, `dropped` 0, tier `nudge`, reason naming
  `nudges.ttl_hours = 1`. Add a second `retro.gap` at `NOW - 10 min`: the row is open with
  `count` 2 and no `nudges.dropped` row.
- [X] T011 Test in `tests/test_nudge_hygiene.py`: `nudges.max_open = 5`; 8 `tracker.call`
  failures on items `I1` to `I8` with `ts` increasing, plus one `security.finding` page:
  `status.attention` holds the page, the rows for `I5` to `I8`, and a `nudges.dropped` row with
  `dropped` 4 and `expired` 0; `status.line(status.snapshot(directory, line=True))` contains
  `pages 1` and `nudges 5`. With 5 or fewer nudges: no `nudges.dropped` row and the rows list
  is the uncapped one. Variant: add a pending decision route `D-1` to `state.json`
  (`decision_routes: {'D-1': {}}`); a row without `ts` counts as newest, so the kept nudges are
  `decision.pending` D-1 and `I6` to `I8`, with `dropped` 5.
- [X] T012 Implement `status._tidy` and call it in `surfaced`, before `round.ready` and
  `close.ready` are added (`cli/wuwei/commands/status.py`, plan items 4 and 5). `scan` keeps
  every row, so `trace_gaps`, doctor's gap and untraced counts and `nudges --all` see rows the
  cap or the TTL drop (review F1). T010 and T011 read `surfaced(...)`, not `status.attention`.

## Phase 5: the printed list (FR-005)

- [X] T013 Test in `tests/test_nudge_hygiene.py`: with the 50 events of T003 (last at
  `NOW - 2 h`, `ttl_hours` default), `main(['nudges', '--all'])` prints one line for the PR
  containing `(50 times, last 2 h ago)`; a single event at `NOW - 7 min` prints
  `(last 7 min ago)`; `nudges.line(row, 1)` for a row without `ts` is unchanged (the existing
  parametrized `test_nudge_line_actions` covers the rest). The `nudges.dropped` row prints its
  reason with no `Run:`. `main(['nudges', '--all', '--json'])` equals `status.attention` dumped.
- [X] T014 Implement in `cli/wuwei/commands/nudges.py`: `ACTIONS['nudges.dropped']`, `line`'s
  `now` parameter and age part, and `run`'s summed counts and newest `ts`.

## Phase 6: observe is a shadow line, not a nudge (FR-007, US3)

- [X] T015 Test in `tests/test_nudge_hygiene.py` (issue acceptance 3): config
  `[security]\nposture = "observe"\n[nudges]\nmode = "all"\n`, one `guard.would_refuse` appended
  with `state.append_event` and payload `{'guard': 'pr', 'area': 'publish', 'level': 'warn',
  'posture': 'observe', 'reason': 'refused', 'exit': 1, 'target': 'gh pr create', 'session': 's',
  'item': None}`: `main(['nudges', '--all', '--json'])` has no `guard.would_refuse` row, and
  `main(['shadow', 'report'])` prints exactly one line starting with `- pr: 1`. This pins
  behaviour already on main: it passes before any code change, which the implementer states
  in the task note instead of a red run. No implementation task.

## Phase 7: docs and template (FR-008)

- [X] T016 Test: `tests/test_docs.py::test_every_template_config_key_is_documented` covers the
  new keys once the template names them; add to `tests/test_nudge_hygiene.py` one assertion
  that the `nudges.max_open` row of `docs/site/configuration.md` names `nudges.dropped`.
- [X] T017 Add the two commented keys to `templates/workspace/config.toml`, the two rows and the
  paragraph change to `docs/site/configuration.md` (plan, last two sections).

## Phase 8: close

- [X] T018 Run the touched test files (the owner keeps the full suite for CI); all green. Check every file
  written for em-dashes, emojis and absolute local paths.
- [X] T019 Review fixes: F1 test `test_health_counts_and_all_see_rows_the_cap_drops` (the cap
  drops a `traces.gap` row and `trace_gaps` and doctor still count it, `nudges --all` lists every
  row); F2 `tests/test_workspace.py::test_config_defaults_and_independence` expects the two new
  `nudges` keys. Run the full suite; all green.

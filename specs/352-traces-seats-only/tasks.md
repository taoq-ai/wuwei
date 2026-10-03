# Tasks: Tool-sequence decisions apply to item seats only

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q` from the
repository root using the interpreter the task names. Design details are in plan.md.

## The registry question (US1, US2)

- [X] T001 Create `tests/test_traces_seats_only.py` with `test_registered_roles` calling
  `wuwei.sessions.registered(data, session_id)` on a plain dict: `planner_session_id: 'P'`
  gives `'planner'` for `'P'` and for `'P:agent1'`; a `sessions` row `{'role': 'shepherd'}`
  for `S` gives `'shepherd'`, `{'role': 'remote'}` gives `'remote'`; a row `{'role':
  'adhoc'}` gives `None`; an id with no row gives `None`; an empty dict gives `None`. Fails
  today with AttributeError: `registered` does not exist.
- [X] T002 Add `registered(data, session_id)` to `cli/wuwei/sessions.py` after `record`, as
  in plan.md section 1. T001 passes.

## The seeded day: decision count per posture (US1, US2)

- [X] T003 In `tests/test_traces_seats_only.py` add the `day` fixture from plan.md (Tests):
  a parametrisable config with `[adapters] scanner = "ziran"` and a posture, today's state
  written, a non-empty `traces.jsonl`, `wuwei plan session P` run through
  `wuwei.__main__.main`, and `registry.load` patched so the scanner port returns
  `Result(1, {'sessions_analyzed': 2, 'findings': rows})` where `rows` holds
  `{'chain': ['Bash', 'Write'], 'risk_level': 'critical', 'session_id': s}` and the same for
  `['Bash', 'Edit']`, for `s` in `P` and `U`, each row twice. Add helpers `decisions(root)`
  (sorted `D-*.md` names) and `events(root, kind)` (payloads).
- [X] T004 Add `test_seeded_day_decisions_per_posture` parametrised over `observe`,
  `guarded`, `strict`: call `scanner.trace_sweep(root, workspace.load_config(root))` twice.
  Assert: one `traces.noted` event with `role: 'planner'` and `summary: 'traces: planner
  session, chain noted'` and the digest of `P`; no decision and no `scanner.finding` for `P`
  in every posture; for `U` under observe and guarded one `traces.unmatched` event (with the
  posture) and no decision, and `scanner_owed` 0; under strict exactly one decision, whose
  text contains `Context: Session has no item reservation and no registration.` and the
  digest of `U`, `scanner.finding` events only for `U`, and `scanner_owed` 4 (the rows of
  `U`) on each sweep.
  Fails today: two decisions per session in every posture.
- [X] T005 Add `test_shadow_mode_is_observe`: config with `security.posture = "guarded"`
  and `[guards] mode = "shadow"`; unknown `U` gives one `traces.unmatched` with
  `posture: 'observe'` and no decision. Fails today with two decisions.
- [X] T006 Add `test_planner_subagent_and_registered_roles`: findings for `P:agent1`, and for
  `S` after `sessions.record(data, 'S', hook='shepherd', cwd=..., role='shepherd')` inside a
  `state._write_state`, under strict: no decision; one `traces.noted` for each, with roles
  `planner` and `shepherd`. And `A` with only an `adhoc` row (recorded the same way without
  `role`): one decision under strict. Fails today: decisions for all three.
- [X] T007 Add `test_seat_wins_over_registration`: a seat record `{'item': 'work', 'role':
  'builder', 'status': 'stopped', 'brief': 'x', 'trace_sessions': ['P']}` and item `work`
  in state, planner `P`, posture observe, findings only for `P`: the item is parked, one
  decision per chain (two), a `scanner.finding` per row, `scanner_owed` 4, no
  `traces.noted`. Passes today; it pins that the
  exemption never reaches a seat (run it before and after T009).
- [X] T008 Add `test_unreadable_events_are_unmeasured`: write a line without a trailing
  newline to today's `events.jsonl`, sweep for unknown `U` under guarded: the result has
  `scanner: 'unmeasured'` and `unreadable: 1`. Fails today because nothing reads the events.
- [X] T009 In `cli/wuwei/scanner.py` change `_trace_response` to take `posture`, classify the
  session and return whether it paged, change the no-reservation `Context:` text, and in
  `trace_sweep` compute the posture with `workspace.posture(config)[0]` and sum the returns
  into `scanner_owed`, all as in plan.md section 2. T004 to T008 pass.

## Event tiers and producers (US1, US2)

- [X] T010 Add `test_event_tiers` in `tests/test_traces_seats_only.py`:
  `signal.classify({'kind': 'traces.noted', 'payload': {}}, {})[0] == 'silent'`;
  `traces.unmatched` with `posture: 'observe'` is `silent`, with `guarded` or `strict` is
  `nudge`; `main(['event', 'traces.noted', '{}']) == 1` and stderr names `wuwei sweep`, the
  same for `traces.unmatched`. Fails today: `traces.noted` is a nudge and the producer is
  "its dedicated command".
- [X] T011 In `cli/wuwei/signal.py` add `'traces.noted'` to `SILENT` and extend the
  `guard.would_refuse` branch to `traces.unmatched`; in `cli/wuwei/commands/event.py` add
  both kinds to `EVENT_PRODUCERS` with `'wuwei sweep'`. T010 passes.

## Existing seat tests (US3)

- [X] T012 In `tests/test_watch.py` `test_trace_sweep_parks_queues_and_pages`, when
  `mapped` is false append `\n[security]\nposture = "strict"\n` to the config before the
  sweep and assert the decision text contains `Context: Session has no item reservation and
  no registration.`; leave the mapped cases as they are. Run the whole of
  `tests/test_watch.py` and `tests/test_quiet_sweeps.py`; all pass after T009 (the unmapped
  case fails before T012 under the default guarded posture, which is the intended change).

## doctor closes the old decisions (US4)

- [X] T013 In `tests/test_doctor.py` add `trace-decisions` to the set in
  `test_fix_allow_list_is_pinned`. Fails today.
- [X] T014 In `tests/test_doctor.py` add `test_trace_decisions_row_and_fix(ws, capsys)`:
  write `D-2.md` and `D-3.md` into today's `decisions` directory with the pre-#352 body
  (the exact text `scanner._trace_response` wrote before this change: the critical tool
  sequence question, `Context: Session has no matching item reservation.`, chains Bash ->
  Write and Bash -> Edit, `Outcome: pending`; keep the body as a module constant in the
  test), and `D-4.md` with the seat context. `doctor.diagnose()` has one row
  `trace decisions` with status `warn`, value naming `D-2, D-3` and `apply ==
  'trace-decisions'`. `fix(confirm)` with a confirming callback: the shown batch contains
  `[trace-decisions]` and both ids; afterwards both records contain `Outcome: superseded`
  and `Notes: superseded by wuwei doctor --fix`, exactly one `Outcome:` line each,
  `decision.evaluate` still accepts them, `state.read_state(root)['decision_outcomes']`
  holds `superseded` owner outcomes for both, `decision.answered` returns `superseded`,
  `cockpit_snapshot(day)['decisions']` lists only `D-4`, `doctor.fixed` records
  `{'fix': 'trace-decisions', 'exit': 0}`, and a second `diagnose()` has no
  `trace decisions` row. `D-4` is unchanged. Fails today: no such row or fix.
- [X] T015 In `tests/test_doctor.py` add `test_trace_decisions_changed_since_preview`: the
  confirm callback answers `D-2` (an owner outcome in `decision_outcomes`) before returning
  true; the fix prints `changed since the preview`, exits 1 for that fix and leaves `D-3`
  pending. Fails today: no such fix.
- [X] T016 In `cli/wuwei/commands/doctor.py` add `import re`, `LEGACY_TRACE`,
  `SUPERSEDED`, `_legacy_traces`, the `trace decisions` row in `_day`,
  `_supersede_preview`, `_supersede` and the `FIXES` entry as in plan.md section 4; in
  `cli/wuwei/state.py` extend `STATE_PRODUCERS['decision_outcomes']` with
  `or owner host wuwei doctor --fix`. T013 to T015 pass and `test_day_rows` still passes.

## Docs

- [X] T017 Run `tests/test_docs.py`; `test_doctor_is_the_first_stop` fails on the new fix.
  Add the `trace-decisions` row to the fix table and the item to the Day and sessions list in
  `docs/site/reference.md` (Doctor), the trace-chain paragraph after the floors list in
  `docs/site/security.md`, and the S2 amendment in `docs/specs/2026-09-24-wuwei-design.md`,
  all as in plan.md section 5. `tests/test_docs.py` passes.

## Verification

- [X] T018 Run `python -m pytest -q` from the repository root with the interpreter the task
  names; every test passes.
- [X] T019 Scan every file changed in this feature for em-dashes, emojis and absolute local
  paths, and remove any.

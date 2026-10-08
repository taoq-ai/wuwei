# Implementation Plan: Shadow-before-live promotion

**Branch**: `560-shadow-promotion` | **Spec**: `specs/560-shadow-promotion/spec.md`

## Summary

Put a shadow between the agreement count and the raise card. `propose` starts a shadow row in
`cruise.json` (promote writer); `mandate` writes what the shadow level would have answered;
the steward scores it against the live outcome; a passed shadow gets the one raise card; the
approved raise clears it. Everything reuses the #283 cruise module and the promote writer.

## Technical Context

Python 3.11 stdlib only; pytest for tests. No new module, no new dependency. Files:
`cli/wuwei/cruise.py`, `cli/wuwei/promotion.py`, `cli/wuwei/commands/decision.py`,
`cli/wuwei/commands/cruise.py`, `cli/wuwei/commands/__init__.py`, `cli/wuwei/steward.py`, `cli/wuwei/report.py`,
`cli/wuwei/workspace.py`, `cli/wuwei/state.py`, `cli/wuwei/commands/event.py`; docs
`docs/specs/2026-09-24-wuwei-design.md`, `docs/site/configuration.md`,
`docs/site/concepts.md`; tests `tests/test_cruise.py`, `tests/test_invariants.py`.

## Constitution Check

Stdlib only, test first, shortest diff, no refusal added (#530), one writer per trusted key
(`cruise.json` via `_cruise_write`; `decision_shadows` and `decision.shadow` reserved to
`wuwei decision route`), fail closed on a damaged `cruise.json`, no absolute paths. Pass.

## Changes

1. `cli/wuwei/workspace.py`: in the `decisions.cruise` schema add
   `"shadow_days": (int, 5, 1), "shadow_min": (int, 5, 1)`.
2. `cli/wuwei/cruise.py`
   - `running`: validate optional `shadow`: a dict keyed by known classes; each row a dict with
     `level` int 1..3, `started` str, `scored` and `agreed` int >= 0, `state` in
     `('running', 'passed', 'ended')`; else the existing `ValueError(... DAMAGED)`.
   - `rule(root, ident, fields, scores, config, data, run=None)`: `run or decision.running(root)`
     at line 69. The one change to `rule`.
   - New `shadow(root, ident, record, fields, scores, config, data)`: read `running`; if the
     record's class has a `running` shadow row, call `rule(..., run={**run, 'levels':
     {**run['levels'], name: row['level']}})`; when it returns a dict, write
     `decision_shadows[ident] = {'class', 'level', 'option': record['option'], 'at'}` through
     `state._write_state(..., reserved=False, kind='decision.shadow', payload={'id': ident, ...})`.
   - New `review_shadows(root)`: for each `running` shadow, walk `_days(root, days since
     started + 1)`; per day, each `decision_shadows` row of the class and level with `at >=
     started` and its same-day `decision_outcomes` row: scored when `decided_by == 'owner'`,
     or `decided_by == 'mandate'` and `window(row)` is None; agreed when `option` matches.
     First disagreement: `promotion.cruise_shadow(root, name, {**row, 'state': 'ended',
     'ended': now, 'record': path}, f'shadow ended: {name} at L{n}: {ident} answered {a},
     shadow {b}; agreed {x} of {y}', path)`. Passed (`now - started >= shadow_days`, scored >=
     `shadow_min`, agreed == scored): state `passed`, reason `shadow passed: {name} at L{n};
     agreed {s} of {s}`. Else write counts only if changed (`shadow scored: ...`).
   - `agreements`: `since = max(changed, shadow ended)` (one line).
   - `propose`: in the class loop, after the existing skip checks: a `passed` shadow writes the
     raise card (existing `_card` and text, card row gains `'shadow': row`), then
     `promotion.cruise_shadow(..., state 'ended', reason f'shadow asked {ident}')`; a `running`
     shadow continues; otherwise, when `count >= promote_agreements`, start the shadow
     (`promotion.cruise_shadow(root, name, {'level': level + 1, 'started': now, 'scored': 0,
     'agreed': 0, 'state': 'running'}, f'shadow started: {name} at L{level + 1}')`) and write
     no card. The `carded` window check stays.
   - `answered`: add `and card.get('shadow', {}).get('state') == 'passed'` to the raise
     condition; reason `f'raise approved {ident}; shadow agreed {a} of {s}'`.
   - `label`: append `' · shadow ' + ', '.join(sorted(names))` for running and passed rows.
   - New `shadow_lines(root)`: report lines, one per row, `none` when empty.
3. `cli/wuwei/promotion.py`
   - New `cruise_shadow(root, name, row, reason, evidence=CRUISE)`: `data = running(root)`,
     set `data.setdefault('shadow', {})[name] = row`, `_cruise_write(root, data, 'shadow',
     reason, evidence)`.
   - `cruise_level`: pop `name` from `data.get('shadow', {})` (drop the key when empty).
4. `cli/wuwei/commands/decision.py` `mandate`: after the record file write, before `return
   'mandate'`: `try: cruise.shadow(root, ident, record, fields, scores, config, data)` except
   `(OSError, ValueError)` print a `wuwei decision route: shadow not written: <reason>` warning
   to stderr. The live route above is untouched.
5. `cli/wuwei/steward.py` `review`: `cruise.review_shadows(root)` after
   `calibration_scores.evaluate(root)`.
6. `cli/wuwei/commands/cruise.py`: `shadow` in the action choices and help; print `class level
   started scored agreed state` rows from `cruise.running(root).get('shadow', {})`, `none` when
   empty; exit 0, 2 on error (existing except). Add `'cruise shadow'` to `READ_ONLY` in
   `cli/wuwei/commands/__init__.py` so the read-only command is never refused or carded.
7. `cli/wuwei/report.py`: `'', '## Shadow', *cruise.shadow_lines(root)` after the Calibration
   section.
8. `cli/wuwei/state.py` `RESERVED`: `'decision_shadows': 'wuwei decision route'`;
   `cli/wuwei/commands/event.py` reserved kinds: `'decision.shadow': 'wuwei decision route'`.
9. Docs: design 5.8.1 "Shadow promotion" paragraph after "Promotion and demotion" (rule,
   config keys, states, the status line part); amend the running-level sentence ("raises
   after a passed shadow and morning-gate approval"); kill switch paragraph gains `· shadow
   <classes>`; 9.2 rows I13 and I14. `docs/site/configuration.md` two rows after
   `promote_agreements`; `docs/site/concepts.md` cruise section one short paragraph; `docs/site/reference.md` cruise
   row and `docs/site/agent.md` read-only list gain `cruise shadow`.
10. `tests/test_invariants.py`: `shadow_rule()` (`functools.cache`, pure): for every class and
    every shadow level and state, `cruise.level(config, name, run)` equals the level with the
    shadow row removed (I13). I14: memoised on `rules.root`, a `raise` card row without a
    passed shadow in today's `cruise_cards`, `cruise.answered(root, ident, 'raise')` leaves
    `decision.running(root)['levels']` unchanged; clean the row afterwards. Add both to
    `INVARIANTS`.

## Shared helpers reused

`promotion._cruise_write` (atomic write and ledger line), `cruise.running`, `cruise.rule`,
`cruise._days`, `cruise.window`, `cruise._card`, `grants._record`, `state._write_state`,
`decision.running`, `decision.CLASSES`.

## Must not change

- The live route: `mandate`'s outcome row, payload, record file and return value; `rule`'s
  result for the live call (`run` defaults to today's read).
- `level()` never reads `shadow`.
- The #558 budget restore path and its no-card raise; the weekly sample cards.
- No refusal or exit-code change in any command because of a shadow.

## Test plan

All in `tests/test_cruise.py` (in-process, existing `ws`, `agree`, `calibrated`, `answer`,
`ledger`, `cards` helpers) plus `tests/test_invariants.py`. Update
`test_ten_agreements_propose_a_raise`, `test_the_owner_raise_lands_and_keep_does_not` and
`test_a_raise_never_passes_the_configured_level` for the shadow step. Run:
`python -m pytest -q tests/test_cruise.py tests/test_invariants.py tests/test_steward.py
tests/test_decision.py tests/test_promotion.py tests/test_calibration_scores.py
tests/test_budget_classes.py tests/test_docs.py` plus the report and status test files if touched.

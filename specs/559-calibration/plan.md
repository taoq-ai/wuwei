# Implementation Plan: Confidence calibration per class and per role

**Branch**: `559-calibration` | **Spec**: `spec.md`

## Summary

One new stdlib module, `cli/wuwei/calibration_scores.py`, scores taken records from the #558
window reader (`budget_classes.select`, widened by one keyword to every taken record) and
writes the uncalibrated class and role sets into the existing `memory/cruise.json` through
the promote writer. Three existing read points use the stored sets: `cruise.level` (cap at
L1), `decision.cisr` callers in routing (ambiguity high) and `cruise.label` (status line).
Promotion reads the live table. One command prints the table; report and retro share one
lines function.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures, reusing
`tests/test_budget_classes.py` helpers (`at`, `answers`, `reverse`) and its imports from
`tests/test_cruise.py` (`config`, `ledger`, `propose`, `raise_to`, `agree`, `status_line`)
and `tests/test_decision_classes.py` (`ws`, `record`, `route`). Time moves with `WUWEI_NOW`.

## Constitution Check

- One behaviour, one function: window and events only in `budget_classes.select`; the Brier
  rule only in `calibration_scores.measure`; cruise.json writes only in `promotion.py`. Pass.
- Exits: damaged stream or `cruise.json` raises ValueError; `wuwei cruise calibration` and
  `wuwei steward` turn it into exit 2 with the reason. Pass.
- No forgeable trust: counted events (`decision.decided`, `decision.reversed`,
  `cruise.carded`) are CLI-written reserved kinds; the stored sets live in `cruise.json`,
  already refused to seats (`cli/wuwei/guards/protect_state.py:304`). `confidence` and `role`
  enter the payload from the linted record by the CLI. Pass.
- #530: no new refusal. A capped class goes to the owner as a card (L1); an uncalibrated
  role's record goes Strategic, a card. Pass.
- #551: no planner prose step; the status part and the report line point at
  `bin/wuwei cruise calibration`. Pass.
- Ponytail: no new state file, no new event kind, no per-record storage. Pass.

## Changes

### `cli/wuwei/budget_classes.py`: `select(root, days, now=None, every=False)` (line 11)

- When `every` is true, `answers` also takes `decision.decided` rows whose `decided_by` is
  `seat` or `mandate` (a cruise answer's `decided_by` is its rule, already taken).
- Each answer dict gains `'confidence': payload.get('confidence')`, `'role':
  payload.get('role')`, `'undo_until': payload.get('undo_until')`.
- Default `every=False` keeps #558 behaviour byte for byte (table, propose untouched).

### New `cli/wuwei/calibration_scores.py`

```python
FORECAST = {'high': 0.9, 'medium': 0.6, 'low': 0.3}

def measure(pairs, cruise):
    """(brier, state) of [(forecast, outcome)]: calibrated, uncalibrated or too few."""

def scored(root, config, now=None):
    """[{class, role, forecast, outcome, labels}] from select(..., every=True): answers with a
    confidence and no open undo window; outcome 0 when an event names (day, id)."""

def table(root, config, now=None):
    """Rows {kind: class|role, name, scored, brier, state, broke: [labels]}: every class but
    merge, then every role with a scored record, sorted."""

def evaluate(root):
    """The steward step: store the uncalibrated sets through promotion.calibration when they
    changed. Returns the rows."""

def lines(root, config):
    """Report and retro section: the table as lines, then one line per uncalibrated role:
    '- <role> uncalibrated (Brier x.xx over n): <labels>; run bin/wuwei cruise calibration'."""
```

Brier is `sum((f - o) ** 2) / len(pairs)`; `brier` is None when nothing is scored.

### `cli/wuwei/promotion.py`: new `calibration(root, classes, roles, reason)` after `cruise_level` (line 44)

Reads `running(root)`, sets `data['calibration'] = {'classes': sorted, 'roles': sorted}`
(pops the key when both are empty), writes with the same `safe_path` and `atomic_write`, and
appends one ledger line (`target: CRUISE`, `action: 'calibration'`, reason naming the sets and
the broken records). `cruise_level` keeps the key (it rewrites `running()` data). Docstring of
`cruise.CRUISE` and `cruise_level` updated: two writers, both in `promotion.py`.

### `cli/wuwei/cruise.py`

- `running` (line 20): accept optional `calibration` dict whose `classes` are known classes and
  `roles` are strings; anything else is DAMAGED.
- `level` (line 42): cap at 1 when the class is in `running['calibration']['classes']`.
- `label` (line 86): append ` · uncalibrated <roles>` when stored.
- `propose` (line 162): `blocked |= {row['name'] for row in calibration_scores.table(root,
  config) if row['kind'] == 'class' and row['state'] != 'calibrated'}`; raise card text adds
  "and its confidence is calibrated".

### `cli/wuwei/decision.py`

- `OPTIONAL` (line 23) gains `'Role'`; one-line check (line 113) gains `'Role'`; `evaluate`
  refuses a Role not in `profiles.ROLES` (lazy import), same message shape as Class.
- `cisr(fields, scores, ambiguous=False)` (line 356): `ambiguous` forces high ambiguity,
  including the Routine-by-definition branch (returns Exploratory).
- New `uncalibrated(root, fields)`: the record's role when it is in the stored set, else None.
- `route_owner` (line 371): passes `ambiguous=bool(uncalibrated(root, fields))` to `cisr` and
  adds `'uncalibrated': role` to the row and payload when set (as `novel`).
- `seat_outcome` (line 465): adds `'confidence': fields['Confidence']` and `'role'` when
  present.

### `cli/wuwei/commands/decision.py`: `mandate` (line 104)

`kind = cisr(fields, scores, ambiguous=bool(decision.uncalibrated(root, fields)))`; the record
dict sets `'cisr': kind` so the stored row matches the route. `template()` (line 296) gains
`Role: builder` after `Class:`.

### `cli/wuwei/commands/cruise.py`

`action` choices become `('budget', 'calibration')`; `calibration` prints
`kind name scored brier state` rows from `calibration_scores.table`, exit 1 when any
`uncalibrated`, 2 on error (same except tuple as budget).

### `cli/wuwei/steward.py`: `review` (line 24)

After `budget_classes.evaluate(root)`, call `calibration_scores.evaluate(root)`.

### `cli/wuwei/workspace.py`: SCHEMA (line 145) and check (line 697)

`"calibration_threshold": (float, 0.15)`, `"calibration_min": (int, 10, 1)`; refuse a
threshold outside `0 < t < 1` with the budget_share message shape.

### `cli/wuwei/report.py` (line 102) and `cli/wuwei/retro.py` (after line 112)

`lines += ['', '## Calibration', *calibration_scores.lines(root, config)]`.

### Charter, design, docs

- `charters/_common.md` line 27: add "`Role:` your role (the charter name)" to the new-record
  fields; regenerate `agents/` with `python3 -P -m wuwei agents build` (from `cli/`) so the drift
  checks pass.
- Design 5.8: `Role:` bullet. 5.8.1: "Calibration (owner, 2026-10-08, #559)" paragraph, the
  two config keys in the config list, status line part in Kill switch. 9.2: row I12.
- `docs/site/concepts.md` (calibration), `reference.md` (`wuwei cruise calibration`, `Role:`),
  `daily.md` (status part, report section), `configuration.md` (two keys).

## Must not change

- `budget_classes.select` default behaviour, `measure`, `table`, `evaluate` (#558).
- The mandate's take conditions other than the CISR class; refusals anywhere.
- `cisr` result for any call without `ambiguous` (owner_outcome, seat_outcome callers).
- `cruise.json` level and budget semantics; the promote writer's ledger shape for levels.
- No new event kind; no new protected path.

## Tests

- `tests/test_calibration_scores.py` (new): measure, scoring, table, evaluate, command,
  promotion gate, level cap, routing, status line, report and retro section.
- `tests/test_invariants.py`: I12.
- Touched suites to run: `tests/test_budget_classes.py`, `tests/test_cruise.py`,
  `tests/test_decision.py`, `tests/test_decision_classes.py`, `tests/test_report_retro.py`,
  `tests/test_retro.py`, `tests/test_signal_status.py`, `tests/test_config_failure.py`,
  `tests/test_agents.py`, `tests/test_charters.py`, `tests/test_docs.py`,
  `tests/test_invariants.py`, `tests/test_steward.py`. Never the full suite.

# Implementation Plan: Decision classes (MIT CISR) and fewer cards

**Branch**: `530-decision-classes` | **Spec**: `spec.md`

## Summary

One derived class per record and one routing rule at the shared spot, the `decision route`
command (`cli/wuwei/commands/decision.py:decide`), behind one new config key
(`autonomy.mode`). Under autonomous a Routine, Consequential or scoring Exploratory record is
taken as recommended (`Decided-by: mandate`, no card); everything else and everything under
supervised goes through the legacy `route()` untouched. The digest, the report and close read
the new outcome; the charters and the planner skill tell seats to route before asking.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. All tests in process on neutral fixtures in
`tmp_path` (records written from `tests/test_decision.py`'s `VALID` and `save` helpers).

## Constitution Check

- III one behaviour one function: class in `decision.cisr`, margin in `decision.margin`
  (moved from `why.py`), routing in `decide()`. Pass.
- II exits: `route` keeps 0 on a decision, 1 on a lint finding, 2 on unreadable input. Pass.
- No forgeable trust: the report and close trust only `decision_outcomes` and
  `decision_routes`, both reserved to CLI writers (`state.RESERVED`). A seat writing
  `Decided-by: mandate` in a record gains nothing: the class is derived by the CLI at route
  time and the outcome is CLI-written. Pass.
- No new refusal under observe or guarded (FR-015). Pass.
- Config key added once, with docs row, template line and profile denial. Pass.

## Changes

### `cli/wuwei/workspace.py` (`SCHEMA`)

- Add `"autonomy": {"mode": (str, "autonomous", ("autonomous", "supervised"))},` next to
  `"decisions"`.

### `cli/wuwei/decision.py`

- `MARGIN = 0.2` with a `ponytail:` comment (design 5.8.1 default; `decisions.cruise.margin`
  is not in the schema).
- `ROUTINE = ('approach', 'retry', 'park', 'accept-residual')` (two-way by definition: fix
  round, task round, seat procedure, parked item's next step, residual note).
- `margin(fields, scores)`: the 5.8.1 margin, moved verbatim from
  `cli/wuwei/commands/why.py:209-210` (`_scored(fields)[2]` for the weights). `why.decided`
  calls it.
- `cisr(fields, scores)`:
  ```
  if fields.get('Class') in ROUTINE: return 'Routine'
  low_risk = fields['Reversibility'] == 'two-way' and re.match(r'(?i)\s*(?:item|own branch|own pr|day)\b', fields['Blast radius'])
  clear = fields['Confidence'] != 'low' and margin(fields, scores) >= MARGIN
  return {(True, True): 'Routine', (False, True): 'Consequential', (True, False): 'Exploratory', (False, False): 'Strategic'}[(bool(low_risk), clear)]
  ```
- `evaluate`: `Decided-by` allowed values become `('seat', 'owner', 'mandate')`; the
  missing-fields message uses `add the recommendation and the reasoning` when
  `Recommendation` is among the missing fields (keep the current hint otherwise).
- `_explained`: the missing `Reasoning` message becomes `missing fields: Reasoning; add the
  recommendation and the reasoning`.
- `lint`: OK line `f'OK: {option} ({scores[option]}), {cisr(fields, scores)}'` (style line
  unchanged).
- `seat_outcome(fields, scores, by='seat')`: the route check runs only for `by == 'seat'`;
  the snapshot gains `'decided_by': by` and `'cisr': cisr(fields, scores)`.
- `route_owner`: compute `kind = cisr(fields, _scored(fields)[3])`; add `'cisr': kind` to
  the `decision_routes` entry and to the `decision.routed` payload.
- `decided_record(text, option, by)`: `set_outcome` plus the `Decided-by:` line rewrite,
  extracted from `owner_record`, which now calls it with `'owner'` and appends its Notes
  line as before.
- `route()` is not touched.

### `cli/wuwei/commands/decision.py`

- `decide(args)`: after `evaluate` and the `--external` branch, when
  `workspace.load_config(root)['autonomy']['mode'] == 'autonomous'`:
  - `data = state.read_state(root)`; if `args.id` is in `decision_routes` return `0,
    'owner'`; if it is in `decision_outcomes` return `0, <its decided_by>`.
  - `kind = cisr(fields, scores)`; if `kind in ('Routine', 'Consequential')` or
    `(kind == 'Exploratory' and margin(fields, scores) > 0)`: `record =
    seat_outcome(fields, scores, by='mandate')`; one `state._write_state(update, root,
    reserved=False, kind='decision.decided', payload={'id': args.id, **record})` whose
    `update` refuses (RACE) if an outcome or route appeared meanwhile; then
    `workspace.atomic_write(path, decided_record(text, record['option'], 'mandate'))`;
    return `0, 'mandate'`.
  - Otherwise fall through to the legacy code below, unchanged.
- `show(args)`: with `--widget`, when `decision_outcomes[args.id]['decided_by'] ==
  'mandate'`, return `0, '[]'`.
- `owner_outcome`: the prior-outcome check accepts `decided_by` in `('seat', 'mandate')`;
  use `decided_record` through `owner_record` (no behaviour change).

### `cli/wuwei/commands/why.py`

- `decided`: replace the inline margin with `decision.margin(fields, scores)`.

### `cli/wuwei/watch.py` (digest, `:136`)

- `value.get('decided_by') in ('seat', 'mandate')`; the two-way filter and the header stay.

### `cli/wuwei/closing.py` (`:188`)

- Skip the pending-owner finding when `outcomes.get(identifier, {}).get('decided_by') ==
  'mandate'` (place the check before the `routes`/`route()` condition).

### `cli/wuwei/report.py` (`build`)

- `mandate_lines(data)`: from `data['decision_outcomes']` rows with `decided_by ==
  'mandate'`, sorted Consequential first then by id: `- D-n (<cisr>): <option>,
  decisions/D-n.md; reverse: bin/wuwei decide D-n <option>`; `none` when empty.
- `class_lines(data)`: ids from `decision_outcomes` and `decision_routes`; class from the
  outcome's `cisr`, else the route's `cisr`; skip ids with neither. For each of the four
  classes `- <Class>: <n> decisions, <m> cards` (cards = ids in `decision_routes`), then
  `Target: cards only for Strategic and for floors (publish, merge).`
- Insert `## Taken under mandate` and `## Decisions by class` right before `## Merged`, at
  every verbosity level.

### `cli/wuwei/profiles.py` (`DENIED`)

- `('autonomy.mode', lambda new, old: new == 'autonomous' and old == 'supervised')`.

### Text (short and plain, no em-dashes)

- `charters/_common.md` Decisions rule 2: replace with: run `wuwei decision route D-n` on
  every record; under `autonomy.mode = autonomous` (the default) it takes the
  recommendation of a Routine, Consequential or scoring Exploratory record (`Decided-by:
  mandate`, listed in the digest and the report) and only a Strategic record or a tie goes
  to the owner; under supervised it routes as before. A fix round after FIX verdicts is
  `retry`, a builder's task round or a choice between two seat procedures is `approach`, a
  parked item's next step is `park`: two-way by definition. Keep the existing sentences on
  the mandate and on citing a decision id. Bump the charter `version:`.
- `charters/lead.md` rule 2 of its second list: "Route each record with the common decision
  rule." in place of "Route beyond-item or one-way choices to the owner through the common
  decision rule."
- `skills/wuwei-plan/SKILL.md:10`: before asking a D-n card, run `wuwei decision route D-n`;
  `mandate` or `seat` means decided, do not ask; ask only on `owner`.
- Regenerate `agents/*.md` with `python3 -P -m wuwei agents build` (from `cli/`, or
  `bin/wuwei agents build`) so `agents check` passes.
- `templates/workspace/config.toml`: `[autonomy]` with `mode = "autonomous" # Or
  "supervised": Consequential and Exploratory decisions also ask.`
- `docs/site/configuration.md`: `[autonomy]` in the Sections table (Decisions row) and a
  key row under Decisions.
- `docs/site/reference.md:105`: `Decided-by: seat|owner|mandate`, `decision route` prints
  `mandate` under autonomous, the lint OK line names the class.
- `docs/specs/2026-09-24-wuwei-design.md` 5.8: a short dated paragraph "Decision classes
  (owner, 2026-10-05, #530)" with the two axes, the four classes, who decides under each
  mode, and `Decided-by: mandate`; 5.4: one sentence that under autonomous a decision the
  mandate covers is never a card; 5.8.1 Ceilings: one sentence that under autonomous the
  ceilings bind the action through its floor (merge policy 4.6, publish grants 4.7, outbound
  tiers 4.9), not the decision record (analysis finding A1).

## Must not change

- `decision.route()` and every caller of it except the new branch in `decide()`.
- Every CLI-owned card: `grants.py`, `commands/outbound.py`, `mcp.py`, `remote.py`,
  `pr_actions.py`, `plan gate` (they call `route_owner` directly; only the `cisr` field is
  added).
- The question guard (`guards/decision.py:check_question`), the records floor and every
  posture rule.
- Supervised behaviour of `decision route`, byte for byte in its outputs.
- `brief.mandate` and the cruise levels.

## Existing tests

The default flips to autonomous, so tests that route a one-way or wide record to the owner
through `decision route` and then answer it will see `mandate`. For each such failure whose
subject is the owner card flow, set `[autonomy] mode = "supervised"` in that test's workspace
config (one line in its fixture); do not change its assertions. Update the five
`decision.lint` OK-line asserts in `tests/test_decision.py` to the new suffix.

## Project Structure

Files touched: `cli/wuwei/workspace.py`, `cli/wuwei/decision.py`,
`cli/wuwei/commands/decision.py`, `cli/wuwei/commands/why.py`, `cli/wuwei/watch.py`,
`cli/wuwei/closing.py`, `cli/wuwei/report.py`, `cli/wuwei/profiles.py`,
`charters/_common.md`, `charters/lead.md`, `skills/wuwei-plan/SKILL.md`, `agents/*.md`
(generated), `templates/workspace/config.toml`, `docs/site/configuration.md`,
`docs/site/reference.md`, `docs/specs/2026-09-24-wuwei-design.md`. New test file
`tests/test_decision_classes.py`; additions to `tests/test_calibrate.py` (profile denial table), `tests/test_decision.py`, `tests/test_decision_digest.py` and `tests/test_report_retro.py`.

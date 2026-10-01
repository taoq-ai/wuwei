# Implementation Plan: risk-tiered gates computed from the diff, with per-repository floors and escaped-defect measurement

**Branch**: `280-tiered-gates` | **Date**: 2026-10-01 | **Spec**: `specs/280-tiered-gates/spec.md`

## Summary

`dispatch next` computes a tier once per item at its first initial-round dispatch, from
the worktree diff against its base, stores it in the existing empty `items.<item>.gates`
slot, and returns it on the `gates` action. One shared reader, `dispatch.gate_set(row)`,
replaces the hard-coded three-role constant in dispatch, the pre-PR guard and the merge
policy, so a LIGHT item can be gated by quality alone, raised and merged. The default
floor `standard` keeps every current behaviour. The surface around it is small: three
config keys per repository, an optional lead `tier`, a status field, one PR body line, one
metric.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Testing**: pytest (dev only), `python -m pytest -q` from the repository root with the
interpreter the task names. Vcs reads in new tests use `tests/fakes/vcs.py` (`Fake`
with explicit `results`) through `monkeypatch.setattr(registry, 'load', ...)`; no real
git, no network.
**Constraints**: exits 0/1/2; fail closed (an unmeasured diff never lowers the tier);
state keys and event kinds producer-only; no subprocess in the core; no absolute local
paths, emojis or em-dashes.

## Constitution Check

- I Stdlib only: yes (`fnmatch`, `re`).
- II Fail closed: an unmeasured diff is STANDARD; a malformed recorded gate set raises
  `ValueError`, which every caller already maps to exit 2.
- III One behaviour, one function: tier computation lives in `dispatch.tier`; the gate
  set in `dispatch.gate_set`; path globbing in `merge.matched` (extracted, reused).
- IV Test first: every task pair below is test then implementation.
- V Ponytail: reuses the dormant `gates` slot, the vcs port calls `brief.write` already
  makes, `commit_push.context` for the repository, `merge.never_auto_paths` and
  `brief.full_path_patterns` as forcing rules. Two gate sets only (no per-role forcing).
- VII Security: forcing paths and flags can only raise; a lead tier can only raise;
  `items.<item>.gates` and `gate.tiered` are reserved to `wuwei dispatch next`.

## Design

### 1. `cli/wuwei/workspace.py` (repository schema, line 43-47)

Add to the `repos` item schema, beside `"merge": MERGE_SCHEMA`:

```python
"gates": {"floor": (str, "standard", ("light", "standard", "full")),
          "light_max_lines": (int, 100, 0),
          "trust_paths": [(str, None), ["guards/*", "state.py", "adapters/*", ".claude-plugin/*",
                                        ".github/*", "ci/*", "workflows/*", "deploy/*", "infra/*"]]},
```

Same mechanism as `merge.never_auto_paths` (list rule with array defaults). No change to
`config check`; schema validation already refuses a bad value.

### 2. `cli/wuwei/merge.py` (extract the suffix glob, lines 242-244)

```python
def matched(path, patterns):
    """The first glob matching the path or one of its suffixes, else None."""
    parts = path.split('/')
    return next((pattern for pattern in patterns for i in range(len(parts))
                 if fnmatchcase('/'.join(parts[i:]), pattern)), None)
```

`check` uses it: `require(matched(path, policy['never_auto_paths']) is None, f'never-auto
path: {path}')`. In the verdict evidence loop (lines 247-256) replace `for gate in GATES`
with `for gate in dispatch.gate_set(data['items'][item])` (lazy `from wuwei import
dispatch`, next to the existing lazy `from wuwei.guards.pr import gate_check`; drop
`GATES` from that import if unused). `cli/wuwei/discovery.py:54-55` keeps its own copy
(out of scope; it is not touched).

### 3. `cli/wuwei/dispatch.py`

```python
TIERS = ('light', 'standard', 'full')


def gate_set(row):
    """The item's recorded gate roles; all three until a tier is recorded."""
    roles = (row.get('gates') or {}).get('roles')
    if roles is None:
        return ROLES
    if not isinstance(roles, list) or 'quality' not in roles or not set(roles) <= set(ROLES):
        raise ValueError('invalid recorded gate set')
    return tuple(role for role in ROLES if role in roles)
```

`tier(root, config, row)` returns the record `{'tier', 'computed', 'reasons', 'roles'}`:

1. `computed = 'light'`, `reasons = []`; a local `rise(level, reason)` sets
   `computed = max(computed, level, key=TIERS.index)` and appends the reason.
2. Track FULL: `rise('full', 'track FULL')`. Each true flag in `row['flags']`:
   `rise('standard', f'lead flag {name}')`.
3. Diff, in one `try`:
   - `row.get('worktree')` missing: raise `ValueError('no worktree')`.
   - `tree = (root / row['worktree']).resolve()`; `repo, _, vcs =
     commit_push.context(tree, {}, {}, root, identity=False)` (lazy import, as
     `commands/build.py:_repo` does).
   - `head = brief.read(vcs.head, str(tree), root=root)['sha']`;
     `base = brief.read(vcs.merge_base, str(tree), config['brief']['remote'] + '/' +
     repo['default_branch'], root=root)['sha']`;
     `changes = brief.read(vcs.diff_stat, str(tree), base, head, root=root)` (the same
     three reads as `brief.write`, lines 193-201).
   - `except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc`:
     `repo = None`; `rise('standard', f'diff unmeasured: {exc or type(exc).__name__}')`.
   - else, per change path: `merge.matched(path, repo['gates']['trust_paths'])` gives
     `f'{path} matches trust path {pattern}'`; `merge.matched(path,
     repo['merge']['never_auto_paths'])` gives `f'{path} matches never-auto path
     {pattern}'`; the first `config['brief']['full_path_patterns']` regex with
     `re.search(pattern, path, re.I)` gives `f'{path} matches FULL-track pattern
     {pattern}'`; each raises to `standard`. A row with `additions` or `deletions`
     `None`: `f'{path} binary change'`, `standard`. Total lines over
     `repo['gates']['light_max_lines']`: `f'{total} changed lines over light_max_lines
     {limit}'`, `standard`; otherwise, if `computed` is still `light`, append
     `f'{total} changed lines within light_max_lines {limit}'`.
4. `floor = repo['gates']['floor'] if repo else 'standard'`; `tier = max(computed,
   floor, key=TIERS.index)` (every tier comparison uses `TIERS.index`, never string
   order); if `floor` is above `computed`, reason `f'floor {floor}'`.
5. Lead: `lead = row.get('tier')`; if set and above `tier`, `tier = lead` with reason
   `f'lead tier {lead}'`; if below, reason `f'lead tier {lead} refused: below {tier}'`.
6. `roles = ['quality'] if tier == 'light' else list(ROLES)`.

`next_step` changes (lines 76-100):

- Fix phase (77-81) and delta phase (88-91): iterate `gate_set(row)` instead of `ROLES`.
- Gate phase (84-86): if `not row['gates']` and no `_record(data, item, role,
  'initial')` exists for any of `ROLES`, compute `record = tier(root,
  workspace.load_config(root), row)` and write it with
  `state._write_state(update, root, reserved=False, kind='gate.tiered',
  payload={'item': item, **record})`, where `update` re-checks `_item(fresh, item)`,
  refuses (`Refused('gate tier changed during dispatch')`) if `fresh['items'][item]['gates']`
  is already set, then stores the record. Use the record as `row['gates']` for the rest of
  the call. `roles = list(gate_set(row))`.
- The `gates` return (line 99) adds `'tier': row['gates']` when `phase == 'gate'` and
  `row['gates']` is non-empty. Other actions are unchanged.

`receive` (line 163): `role not in ROLES` becomes `role not in ROLES or role not in
gate_set(data['items'][item])`, with the refusal `gate role {role} is not in the item
gate set` for the second case (keep `unknown gate role or round` for the first). The
sibling HEAD check (line 207) keeps `ROLES`.

### 4. `cli/wuwei/guards/pr.py` (`_recorded_gates`, `gate_check`)

`_recorded_gates(root, sha, records, item, items=None)`: per candidate,
`roles = dispatch.gate_set((items or {}).get(candidate, {}))` (lazy import) replaces
`GATES` in the `initial`, `missing` and `zip` uses (lines 88-97) and in the final message
(line 130-132, `missing or roles` for the chosen candidate; keep `GATES` when there is no
candidate). `gate_check` (line 142) reads `data = state.read_state(root)` once and passes
`data['items']`. The glob fallback (lines 145-184, no recorded verdicts) is unchanged.
`GATES` stays defined. The `ValueError` from a malformed record is already caught by
`check` as exit 2.

### 5. `cli/wuwei/state.py` (`_producer_error`, line 265-271)

Add `'gates': 'wuwei dispatch next'` and `'tier': 'wuwei plan approve'` to the
per-item producer map. `ITEM_DEFAULTS['gates'] = {}` already exists; no schema change.

### 6. `cli/wuwei/commands/event.py` and `cli/wuwei/signal.py`

`EVENT_PRODUCERS['gate.tiered'] = 'wuwei dispatch next'`; add `'gate.tiered'` to
`signal.SILENT` beside `'gate.received'`.

### 7. `cli/wuwei/plan.py`

- `_proposal` (after the track check, line 78-79): `if 'tier' in item and item['tier'] not
  in TIERS: raise ValueError(f'{name}: tier must be light, standard or full')`, with
  `from wuwei.dispatch import TIERS` inside the function (avoid an import cycle).
- `approve` (line 183-187) and `add` (`admit`, line 251-252): add
  `**({'tier': candidate['tier']} if 'tier' in candidate else {})` so items without a lead
  tier keep their exact current shape. Imported items keep it through `**item`
  (line 169), and `gates` is still reset there.

### 8. `cli/wuwei/commands/status.py` (`snapshot`, line 161)

`result['gates'] = {name: row['gates'] for name, row in data['items'].items() if
row['gates']}`. `line` is unchanged.

### 9. `cli/wuwei/shepherd.py` (`raise_pr`, before the outward lint at line 264)

```python
row = data['items'][item]
if row['gates']:
    body += f'\n\nReview tier: {row["gates"]["tier"]} ({", ".join(dispatch.gate_set(row))})'
```

(`from wuwei import dispatch` is already imported lazily further down; hoist it.) The
lint and `create_pr` receive the extended body.

### 10. `cli/wuwei/metrics.py`

`_escaped_by_tier(root)`: over `watch.days(root)`, collect `merged = {item: computed}` for
items with `phase == 'merged'` and a non-empty `gates`, and the builder brief paths from
`_events(directory)` rows with `kind == 'brief written'` and `payload['role'] ==
'builder'` (`root / payload['path']`, `payload['item']`). An earlier item `X` is escaped
when a different merged item's builder brief text matches
`(?<![\w-])<re.escape(X)>(?![\w-])`. Return `{tier: {'merged': n, 'escaped': m}}`, or
`UNMEASURED` when `merged` is empty. `collect` sets
`event_metrics['escaped_defects_per_tier'] = _escaped_by_tier(root)` next to
`escaped_defects` (line 453). Retro and report already dump `collect()`.

### 11. Docs and charters

- `docs/site/configuration.md`: rows `repos.gates.floor`, `repos.gates.light_max_lines`,
  `repos.gates.trust_paths` after `repos.merge.auto`, stating the tier rules in one
  sentence each and that `standard` is the default until calibration.
- `docs/site/reference.md` line 22: candidate `tier` is optional (`light`, `standard`,
  `full`), raises the gate tier, a lower one is refused and recorded.
- `charters/_common.md` rule 4: the pre-PR gate set is the one `wuwei dispatch next`
  returns for the item's tier: arch, quality and security by default; quality alone for a
  LIGHT diff when the repository floor allows it; the goal gate for docs items as today.
- `charters/lead.md` rule 5: one sentence on the optional `tier`.
- Regenerate `agents/` with `bin/wuwei agents build` and confirm `bin/wuwei agents check`
  exits 0.

## What must not change

- The verdict contract and lint, `receive` evidence checks, the agent-surface scanner
  path, fix round and delta semantics, the escalate rules, post-PR behaviour and the rule
  that a `blocks: yes` finding blocks.
- The PR guard's glob fallback (no recorded verdicts) and `GATES` there.
- `brief.write` (its diff reads are copied in shape, not refactored).
- `discovery.start_decision` and its inline matcher.
- `status --line`, the merge policy's never-auto refusal text, the `gates` reset on import.
- At the default floor every existing gate set, phase, exit and event.

## Existing tests that change on purpose

Only the additive `tier` field on a first initial-round `gates` action:
`tests/test_dispatch.py` line 34 (`test_gate_dispatch_and_live_builder_refusal`) and
lines 613-614 (`test_logged_gate_brief_becomes_launch_action`), and
`tests/test_e2e_day.py` line 27. Compare the action without `tier` to the old expectation
and assert `tier['tier'] == 'standard'` and `tier['roles'] == ['arch', 'quality',
'security']`. Line 680 of `test_dispatch.py` stays as it is (verdicts exist before the
first dispatch, so no tier is recorded). Correction found while building: line 181 of
`test_e2e_day.py` (`test_agent_surface_without_scanner_is_unmeasured`) changes by the same
additive pattern, because the day fake's `gate` helper calls `dispatch next` before the
first verdict, so the tier is recorded there.

## Risks

- Extra vcs reads at the first gate dispatch (three port calls). Test fakes that return
  `Result(2)` or lack the method fall into `diff unmeasured`, which is STANDARD, so
  existing tests keep their gate sets.
- The tier is frozen at the initial gate; a fix round that adds a forcing path is not
  re-tiered (spec Assumptions). Never-auto paths still block auto-merge.
- Escaped defects per tier relies on builder briefs naming the fixed item; a fix brief
  that does not name it is missed (counted as not escaped). The metric reports counts,
  not a rate, so the denominator is visible.

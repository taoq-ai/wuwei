# Implementation Plan: the invariant walk runs with headroom under its budget

**Branch**: `626-fast-invariant-walk` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Cut the walk's CPU without dropping a case, an assertion or the budget: stop repeating
`check_bash` calls whose inputs do not change across answered grant states, stop repeating
I20's plain `calibrate.host` call, parse I35's configs once per cap and rotation instead of
once per triple, and keep imports and earlier tests' parse cache out of the clock. Add
`test_walk_overhead` so the loop's own cost is asserted and named. One file changes:
`tests/test_invariants.py`.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. The Tests job runs Python 3.11 and 3.12
on a 2-CPU `ubuntu-latest` runner. Measure CPU (`time.process_time`), never wall, and
compare `main` and this branch alternately in one session: this host's load moves single
walks by 0.1 s (see `quickstart.md`).

## Constitution Check

Test first per behaviour (tasks.md); stdlib only; no production code, so no guard, refusal
or posture change (#530) and no 9.2 table change; no budget, case count or fixture loosened
(#346). Pass.

## Design

All in `tests/test_invariants.py`.

### 1. `Rules.record` (lines 224-246): memoise the guard calls on what they read

Keep the outer memo key `('record', posture, grant)`, `self.configure(posture)`, the
`gate_asked` reset, `before`, the `record_gate` call when `grant != 'none'` and the
returned grant-row comparison. Move the loop over the two commands (lines 240-244) into an
inner `checks()` and call it through
`self.memo(('record checks', posture, grant != 'none'), checks)`. Comment at the memo:
protect_state reads the planner session, its gate topics, the posture and the D-1 record,
never the grant rows; if it ever reads them, add the grant to this key. The product order
(posture outer, grant inner: `none`, `asked`, ...) runs `checks()` after `record_gate` on
the first answered state, which is the state every later answered state reproduces.

### 2. `i20.compute` (line 687): reuse the budget-0 call

Replace the second `calibrate.host` call with `plain = plain if budget else found`, with a
comment that budget 0 runs first in the product and its result is the plain call for the
budget after it. Expected values, the comparison `found > plain` and the message stay.

### 3. `i35.compute` (lines 1033-1040): one parse per cap and rotation

```python
for cap, shift in itertools.product((1, 2, 3), range(3)):
    overrides = {tier: (0, 1, 3)[(index + shift) % 3] for index, tier in enumerate(dispatch.TIERS)}
    raw = (rules.base + f'[gates]\nmax_rounds = {cap}\ntier_max_rounds = {{ '
           + ', '.join(f'{tier} = {value}' for tier, value in overrides.items()) + ' }\n')
    config = workspace.load_config(rules.root, raw=raw)
    for row_tier in dispatch.TIERS:
        found = dispatch.max_rounds(config, {'gates': {'tier': row_tier}})
        if found != (overrides[row_tier] or cap):
            return f'max_rounds {cap}, {overrides}: a {row_tier} item gets {found}'
```

Each (cap, tier, override) triple of today's product appears once across the three
rotations; an unset tier is the schema default 0 (`cli/wuwei/workspace.py:138`), which is
what an explicit 0 gives. The `open_fix` half (from line 1041) is unchanged.

### 4. `test_invariants_hold` (lines 1120-1134): nothing but the rules inside the clock

Module constants above the test:

```python
BUDGET = 1.0  # CPU seconds for the whole walk on the runner (#346: never loosened)
OVERHEAD = 0.05  # the walk's own loop, without invariants, as a share of BUDGET (#626)
WALK_IMPORTS = (...)  # every module the walk imports, imported before the clock (#562)
```

Start `WALK_IMPORTS` from what the profile found imported inside the walk (dotted names
under `wuwei.`): `budget_classes`, `calibrate`, `calibration_scores`, `commands.build`,
`commands.config`, `commands.decision`, `commands.doctor`, `commands.drafts`,
`commands.hook`, `commands.init`, `commands.worktree`, `consolidation`, `cruise`,
`decision`, `dispatch`, `drafts`, `fast_checks`, `goals`, `grants`, `graph`,
`guards.agent_launch`, `guards.commit_push`, `guards.decision`, `guards.deploy`,
`guards.integrity`, `guards.outward`, `guards.pr`, `guards.protect_state`, `interview`,
`memory`, `merge`, `novelty`, `outward`, `pace`, `plan`, `promotion`, `shepherd`,
`tracker`, `undo`, `voice`. The assertion below, run with the file alone and in the full
suite, is what keeps the list complete; trim names it shows are not needed only if the
assertion still passes both ways.

In the test, after the case-count assertion and before `gc.collect()`:

1. `for name in WALK_IMPORTS: import_module(name)` (`import_module` is already imported).
   This re-imports guard modules `tests/test_hooks.py` dropped.
2. `workspace._CONFIGS.clear()` (import `workspace` from `wuwei` at the top of the test or
   the file), with a comment: earlier tests' texts would fill the cache past
   `CONFIGS_KEPT` mid-walk and clear it, so the walk starts empty and parses each of its
   texts once, inside the clock.
3. After `gc.freeze()`, `loaded = set(sys.modules)`; after the clock,
   `assert not set(sys.modules) - loaded, f'imported inside the timed walk: {sorted(...)}'`
   (`import sys` at the top of the file).

Keep `gc.collect()`, `gc.freeze()`, the `try/finally` with `gc.unfreeze()`, the failures
assertion, and replace the literal in `assert elapsed < 1.0` with `BUDGET` (same value).

### 5. New `test_walk_overhead(monkeypatch)`

```python
def test_walk_overhead(monkeypatch):
    """#626: the walk's own loop over every projection, with no invariant work, stays a small
    share of the budget; the message names the cost per case."""
    def nothing(case, rules):
        return None
    monkeypatch.setitem(globals(), 'INVARIANTS', dict.fromkeys(INVARIANTS, nothing))
    monkeypatch.setitem(globals(), 'PARTS', {name: tuple((reads, nothing) for reads, _ in parts)
                                             for name, parts in PARTS.items()})
    start = time.process_time()
    assert walk((None, None, '', None)) == []
    elapsed = time.process_time() - start
    cost = f'{elapsed * 1e6 / CASES:.2f} us per case, {elapsed:.3f} s for {CASES} cases'
    assert elapsed < OVERHEAD * BUDGET, f'walk overhead {cost}, over {OVERHEAD:.0%} of the {BUDGET} s budget'
```

PARTS keeps I1's two read sets with no-op checks (READS['I1'] is `None`, so PARTS cannot be
emptied). No `world` fixture: `Rules` only stores its arguments and no-op checks never
touch it, so the test costs milliseconds. Place it after `test_undeclared_read_raises`.

## What must not change

- `DIMENSIONS`, `CASES`, `READS`, `PARTS`, `INVARIANTS`, `OUTWARD`, `project`, `Unread`,
  `walk`, `BROKEN`, the `world` fixture (including the fsync patch), every invariant's
  expectations and messages other than I35's (which now names the override map).
- `gc.collect()` and `gc.freeze()` before the clock; `time.process_time`; the budget value.
- Everything under `cli/`, `hooks/`, `docs/`: no production change, no 9.2 table change.
- The other tests in the file (`test_reason_corpus_has_no_wall`,
  `test_undeclared_read_raises`, `test_a_pace_that_lowers_a_tier_is_caught`,
  `test_broken_rule_is_caught`, `test_table_matches_the_checks`, `test_no_stale_owner_marks`,
  `test_merge_only_at_the_gated_green_head`).

## Not done (and when)

- Per-invariant timing in the failure message: the overhead test and the A/B method cover
  the visibility the issue asks for; add it if a budget failure ever needs a hunt.
- Production cuts on shared paths (config copy per `load_config`, security material per
  argument in `protect_state._protected`): only if SC-001 misses after merge, as a
  follow-up issue.

## Project Structure

```text
specs/626-fast-invariant-walk/
  spec.md
  plan.md
  quickstart.md   # how to measure the walk A/B
  tasks.md
  checklists/requirements.md
tests/test_invariants.py   # the only file that changes
```

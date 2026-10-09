# Implementation Plan: one reviewer for a docs-only item

**Branch**: `622-docs-only-gates` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

One decision at the shared spot, `dispatch.tier`, where every caller (dispatch next, the
builder brief's depth prediction, `classes`, `sweep classes`) already gets its tier. A
measured diff whose every path is a document, with nothing else raising it, records tier
light and one role: `goal`, or `quality` for a spec or pre-registration. Two small enablers let
a `goal` gate run through the existing machinery (`gate_set`, the brief command). The report
gains one section. Everything after the record (seats, receive, fix, delta, PR guard, launch
guard) already reads the recorded gate set and needs no change.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new config key,
no new event kind, no new state key, no new port operation.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: an unmeasured diff stays standard with its reason, as today; a damaged gate set
  stays a refusal.
- III one behaviour one function: docs-only is decided once, in `dispatch.tier`; every reader
  takes the recorded roles.
- IV test first: each behaviour below has its failing test before the code.
- V simplicity: path globs, not content; no new tier name, no per-repository setting.
- VII security: review is lowered only when nothing raised it today; agent instruction files
  never count as documents; a `full` floor and `pace careful` still win. Invariant I34 holds it.
- Workflow: a changed decision rule adds its 9.2 row and `tests/test_invariants.py` check.
  The design 5.3 depth table conflict is raised in the PR body, not resolved here.

## Design

### cli/wuwei/dispatch.py

Constants beside `CLASS_PATHS` (one ponytail comment covers the heuristic and its escape
hatch, `repos.gates.trust_paths`):

```python
GATE_ROLES = (*ROLES, 'goal')  # #622: goal runs only as the single gate of a docs-only diff
DOC_DIRS = ('docs', 'specs')
DOC_SUFFIXES = ('.md', '.rst')
AGENT_DOCS = ('AGENTS.md', 'CLAUDE.md', 'SKILL.md', 'charters/*', 'skills/*', 'agents/*',
              'commands/*', '.claude/*', '.agents/*')
SPEC_DOCS = ('specs/*', '*spec*', '*prereg*', '*pre-registration*')
```

`_docs_role(paths)`: `None` unless `paths` is non-empty and every path is a document
(`path.endswith(DOC_SUFFIXES)`, or a `.txt` path under `DOC_DIRS`, and
`merge.matched(path, AGENT_DOCS) is None`); else `'quality'` when any path matches
`SPEC_DOCS` (via `merge.matched`), else `'goal'`.

`gate_set(row)`: validate against `GATE_ROLES`, and accept a set without `quality` only when
it is exactly `['goal']`; order with `GATE_ROLES`. The default for an untiered row stays
`ROLES`.

`tier(root, config, row)`, in the measured branch, after the per-path loop:

```python
docs = _docs_role([change['path'] for change in changes]) if computed == 'light' else None
if total > gates['light_max_lines'] and not docs:
    rise(...)                                   # unchanged text
elif computed == 'light' and not docs:
    reasons.append(...)                         # unchanged "within" text
```

`docs` starts as `None` before the `try` so the unmeasured branch keeps it `None`. Then:

- floor: `if docs and floor != 'full': floor = 'light'` before `effective` is computed, so
  neither the floor nor its `floor <t>` reason applies.
- lead: a new first branch `if docs and lead and TIERS.index(lead) > TIERS.index(effective):
  reasons.append(f'lead tier {lead} overridden: docs-only')`; the two existing branches
  follow as `elif`.
- after `pace.adjust`: `single = docs if docs and effective == 'light' else None`; when set,
  append `f'docs-only: 1 reviewer ({single})'`; `roles` is `[single]` when set, else
  today's expression.

`next_step`, `_seats`, `receive`, `delta_due`, `_delta_feedback`, `opinion` stay as they are:
they iterate `gate_set(row)`, so a `('goal',)` set yields one seat, one receive, a fix for
the FIX role only and the light re-read delta on the same seat.

### cli/wuwei/commands/brief.py

Line 42: map `dispatch.GATE_ROLES` (not `ROLES`) to `sentinel-<role>`, so the command
`_seats` prints (`wuwei brief goal A goal-A --gate ...`) writes a `sentinel-goal` brief.

### cli/wuwei/report.py

`seat_lines(data)`: one line per item with a non-empty `gates` record, sorted by item:
`- <item>: <n> reviewer seat(s) (<gate_set joined by ', '>); tier <tier>: <reasons joined by
'; '>`, where `n` counts `data['seats']` rows with that `item` and a role starting
`sentinel-` (a delta continues a seat; a second opinion is its own seat). `build` adds
`## Review seats` after `## Carry` only when the list is non-empty, before the brief-level
return so every verbosity shows it. Reuse `dispatch.gate_set` (lazy import) and
`brief.seats` for the validated reads.

### tests/test_invariants.py and design 9.2

I34: "A docs-only diff never lowers review when anything else would raise it: a lead flag, a
FULL track, a trust, never-auto, FULL-pattern, binary or agent-instruction path, or a full
floor keeps arch, quality and security at a standard or full floor". `i34` swaps `dispatch._changes` in a try/finally for
a stub returning `rules.config(...)['repos'][0]` (with `floor` set per case) and the case's
changes, calls `dispatch.tier` with a root that has no day state (steady pace), and walks
the product of {plain doc, doc plus each raising path kind, agent doc} x {no flag, each flag}
x {SLICE, FULL} x {standard, full floor}; any case with a raise must record `ROLES`, and the
plain doc case with no raise must record one role. `READS['I34'] = ()`; add `'I34': i34` to
`INVARIANTS`; one row in the 9.2 table (`test_table_matches_the_checks` reads it).

### Docs and charters (FR-009)

- `charters/_common.md` rule 4: a docs-only diff gets one gate, goal for a document and
  quality for a spec or pre-registration; its second round continues that seat; code, a flag
  or a trust surface gets the three. Replace "A docs item also receives the goal gate."
  Bump `version` 1.6.0 to 1.7.0.
- `charters/lead.md` rule 5: the candidate `tier` still raises a code diff; for a docs-only
  diff dispatch measures one reviewer and records the override. Bump 1.4.1 to 1.5.0.
- Regenerate `agents/*.md` with `bin/wuwei agents build`.
- `docs/site/concepts.md` Review tiers, `docs/site/reference.md` (lead `tier`),
  `docs/site/configuration.md` (`light_max_lines` and `floor` rows), `README.md` line 30.

### Existing tests whose fixtures change meaning

Several tests use `docs/guide.md` as "a small light diff". Under this feature that diff is
docs-only. Where a test is about the light code path, switch its path to `src/app.py`
(3, 1); where it is about docs-only, update the expectation:

- `tests/test_dispatch.py`: `test_issue_acceptance_docs_only_light_floor_runs_quality_only`
  becomes the goal acceptance (roles `['goal']`, reason `docs-only: 1 reviewer (goal)`,
  command `wuwei brief goal A goal-A ...`); `test_issue_acceptance_lead_tier_raises_and_cannot_lower`
  uses `src/app.py`; `test_light_item_records_one_docs_exempt` and
  `test_light_item_skips_the_ticket_until_its_tier_rises` keep passing (tier stays light).
- `tests/test_process_depth.py`: `test_builder_brief_names_its_depth` second half
  (`floor='standard'`) uses `cli/wuwei/report.py`.
- `tests/test_pace.py`: `test_steady_records_are_unchanged` and
  `test_careful_raises_light_to_standard` use `src/app.py` (careful on a docs-only diff gets
  its own new test).

The builder runs the full suite and fixes any other fixture the same way, never by
weakening a docs-only or three-gate expectation.

## What must not change

- The tier, roles and reasons of any diff that is not docs-only (code, empty, unmeasured).
- `ROLES` stays the three; the default gate set of an untiered row stays the three.
- The launch guard, `receive`, `delta_due`, the PR guard and `verdict.lint` are untouched;
  goal verdicts at light already lint without a class-sweep line.
- `pace.adjust` and invariant I15.
- The second opinion: still only above light.
- The design spec outside the 9.2 row.

## Project Structure

```text
cli/wuwei/dispatch.py           tier, gate_set, _docs_role, constants
cli/wuwei/commands/brief.py     GATE_ROLES mapping
cli/wuwei/commands/runtime.py   GATE_ROLES mapping (runtime dispatch goal runs as sentinel-goal)
cli/wuwei/report.py             seat_lines, ## Review seats
charters/_common.md, charters/lead.md, agents/*.md
docs/site/concepts.md, docs/site/reference.md, docs/site/configuration.md, README.md
docs/specs/2026-09-24-wuwei-design.md   9.2 row I34 only
tests/test_dispatch.py, tests/test_brief.py, tests/test_report_retro.py,
tests/test_invariants.py, tests/test_pace.py, tests/test_process_depth.py
```

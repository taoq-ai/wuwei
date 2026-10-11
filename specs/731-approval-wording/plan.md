# Implementation Plan: gate briefs carry the owner's approval wording

**Branch**: `731-approval-wording` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Record the approval once, on the item, at admission, and read it at the one shared spot every
seat brief passes through. `plan approve` and `plan add` write `items.<item>.approved_as`;
`brief.write` copies it into every builder and gate brief header as `Approved as:`; `why`
shows it as its own step. One sentence in `_common.md` tells every sentinel the line answers
the scope question; the planner charter, the plan skill and the daily docs name `--note`.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, no new event kind, no new config key,
no new adapter call. One new item field (`approved_as`, string), written only by two existing
dedicated producers. Every gate and builder brief is written by `brief.write`
(`cli/wuwei/brief.py:376`; `wuwei brief` and the dispatch `gates` action both reach it), so one
header line there covers every gate brief.

## Constitution Check

- I stdlib: nothing imported.
- II exits: `plan add --note` on an existing item is a `state.StateError` (exit 1, a finding
  naming the route); nothing else adds an exit path.
- III one behaviour one function: the value is composed in one helper, `plan._approval`,
  used by both writers; the brief and `why` only read the field.
- IV test first: every task pair in `tasks.md` is test then implementation.
- V simplicity: a string field, not a structured record; one plan-wide note on approve, not a
  per-item `ITEM=TEXT` syntax; one charter sentence in `_common.md`, not four copies; no event
  payload change; no gate card change.
- VII security: `approved_as` is producer-owned (not `items.<item>.note`, the one generic item
  field, `state.py:358`), set only at admission, so a seat cannot rewrite the owner's words on
  an existing item. The text is flattened to one line, so it cannot inject a header line
  (`Depth:` is read from the header by `launch_prompt`, `brief.py:20`) or end the header early.
  `why` output passes through the existing `render` redaction.
- No guard or decision rule changes, so no design 9.2 row and no `tests/test_invariants.py`
  check.

## Design

### cli/wuwei/plan.py

- New helper beside `approve`:

  ```python
  def _approval(scope, note):
      """#731: the item's recorded approval: the plan scope the owner approved, then the owner's words."""
      note = ' '.join((note or '').split())
      return '; '.join(part for part in (' '.join(scope.split()), note and f'owner: "{note}"') if part)
  ```

- `approve(items, root=None, *, ..., pace_label=None, note=None)`: in `update`, the new-item dict
  at `plan.py:444` gains `'approved_as': _approval(candidates[name]['scope'], note)`. `scope` is
  already validated non-empty by `_proposal` (`plan.py:87`). Imported items (`imported`, copied
  from the earlier day with `**item`) and adopted claims are untouched.
- `add(item, root=None, goal=None, size=None, title=None, ticket=None, source=None, note=None)`:
  - In the existing-item branch (`plan.py:478`), before the risk-evidence check:
    `if ' '.join((note or '').split()): raise state.StateError(f"item {item} is already in the
    plan; its approval is recorded once, at admission; record the owner's new words as a scope
    decision: bin/wuwei decision template")`.
  - In `admit` (`plan.py:557`), the item dict gains `**({'approved_as': text} if (text :=
    _approval('', note)) else {})`. A discovery candidate's `scope` is not used: the owner did
    not approve it.

### cli/wuwei/commands/plan.py

- `approve.add_argument('--note', help="The owner's own words on the gate card; recorded on each approved item and quoted in its briefs as Approved as:")`.
- `add.add_argument('--note', help="The owner's own words naming the item; recorded once and quoted in its briefs as Approved as:")`.
- Pass `note=args.note` to `plan.add` (line 81) and `plan.approve` (line 106).

### cli/wuwei/brief.py

- In `write`, the block at `brief.py:525-526` becomes:

  ```python
  if role == 'builder' or gate:
      header.append(LIVE.format(item=item))
      if current.get('approved_as'):  # #731: the owner's approval settles the scope question
          header.append(f'Approved as: {current["approved_as"]}')
  ```

  `current` is the item record read under the brief lock (`brief.py:398`); the `update`
  callback's existing `fresh['items'].get(item) != data['items'].get(item)` check already
  refuses a brief whose item changed while it was collected.

### cli/wuwei/commands/why.py

- `GROUPS` (`why.py:16`) gains `'approved'` after `'queued'` (not in `REQUIRED`, so an absent
  value prints nothing).
- In `item`, after `row = data['items'][name]` for the latest day (`why.py:210-211`), before
  `steps` is built: `if row.get('approved_as'): groups['approved'].append((f'approved as:
  {row["approved_as"]}', None, [rel(day / 'state.json')]))`. One line per item, from the latest
  day's record, so a carried item does not repeat it. `live` (`--json`) reuses `item`, so its
  `steps` carry the line with no change.

### cli/wuwei/state.py

- `_producer_error`'s item map (`state.py:341-351`) gains
  `'approved_as': 'wuwei plan approve or wuwei plan add'`. The field is already protected (only
  `note` is popped in `_protected`); this only names the producer in the refusal.

### Charters, skill, docs

- `charters/_common.md` `## Evidence and gates` rule 7, after its first sentence: "Your brief's
  `Approved as:` line quotes the owner's recorded approval of the item; it answers whether a
  change is in the item's scope." Bump `version` 1.9.0 to 1.10.0.
- `charters/planner.md` rule 3: the owner-named form becomes
  `wuwei plan add <item> --goal G-n --note "<the owner's words>"`, and one sentence: "Pass the
  owner's own words on the gate card with `wuwei plan approve --note`; briefs quote both as
  `Approved as:`." Bump its minor version.
- `skills/wuwei-plan/SKILL.md` line 20: the same `--note "<the owner's words>"` on the
  `plan add` form.
- `docs/site/daily.md`: line 208's approve command gains `[--note "<your words>"]`, and the
  intraday paragraph (line 235) says the planner records your words with `--note` and every
  builder and gate brief quotes them under `Approved as:`, which `wuwei why <item>` also shows.
- Regenerate `agents/` with `bin/wuwei agents build` (the checked-in agent files embed
  `_common.md` and `planner.md`; `tests/test_agents.py:87` fails until they match).

## What must not change

- The `Live:` line and the #667 rule: docs, ticket and spec values stay read live, never copied.
- The header stays one block with no blank line; `launch_prompt` (`brief.py:15`) is untouched.
- `plan.gate_widget` and its record command; the `plan.approved`, `plan.added` and
  `state.import` event payloads; `items.<item>.note` and `_generic_allowed`.
- Briefs and `why` output for items without `approved_as` (existing tests in
  `tests/test_brief.py` and `tests/test_why.py` stay green unchanged).
- The substring `wuwei plan add <item> --goal G-n` in the plan skill, the planner agent file and
  `docs/site/daily.md` (`tests/test_intraday_intake.py:323`).

## Files

- `cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py`, `cli/wuwei/brief.py`,
  `cli/wuwei/commands/why.py`, `cli/wuwei/state.py`
- `charters/_common.md`, `charters/planner.md`, `skills/wuwei-plan/SKILL.md`,
  `docs/site/daily.md`, `agents/*.md` (generated)
- Tests: `tests/test_plan.py`, `tests/test_intraday_intake.py`, `tests/test_brief.py`,
  `tests/test_why.py`, `tests/test_state.py`, `tests/test_charters.py`

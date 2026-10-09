# Implementation Plan: a round cap for every item kind

**Branch**: `623-round-cap` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

The round count already exists in one place every fix round goes through: the build
record's `fix_rounds`, written by `build.open_fix` (gate fixes and PR fixes both call it).
Make it count, compare it with a configurable cap there, and let `dispatch.next_step` open
the next round from a blocking delta instead of escalating. To record a third verdict without
touching every verdict reader, the round that opens moves each gate's `delta` record to
`initial` (keeping the old `initial` as `round<n>`): every reader keeps its two keys. After
the cap, today's paths do the rest: a delta without a blocking finding already raises with
its notes, and `escalate` already becomes a `plan park` card whose record carries the reason;
the reason now names the finding and the unpark step. One sentence in the delta brief and
the common charter stops scope widening. The report gets one section.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, no new port operation, no new
event kind, no new state key (the `round<n>` records live in `gate_verdicts`). Two config
keys under `[gates]`.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: `dispatch next` keeps exit 1 for `escalate`; a refused round stays a
  `ValueError` with its reason.
- III one behaviour one function: the cap is read by `dispatch.max_rounds`, the count by
  `dispatch.rounds_used`, the move by `dispatch.rotate`; the round opens only in
  `build.open_fix`.
- IV test first: tasks.md orders each test before its code.
- V simplicity: no per-round key scheme, no hunk diff, no new park writer.
- VII security: a trust-boundary security finding still blocks after the cap and parks;
  `gate_verdicts` is still written only inside CLI state writes (dispatch receive, and now the
  `open_fix` write that `dispatch next` makes).
- Workflow: the changed decision rule adds 9.2 row I35 and its `tests/test_invariants.py`
  check. Design 5.3's "one fix round plus one delta check" conflict is raised in the PR body.

## Design

### cli/wuwei/workspace.py

`SCHEMA['gates']` (line 135) gains:

```python
"max_rounds": (int, 2, 1),  # #623: fix rounds per item before notes ship or a blocker parks
"tier_max_rounds": {"light": (int, 0, 0), "standard": (int, 0, 0), "full": (int, 0, 0)},
```

### cli/wuwei/dispatch.py

Three small helpers beside `depth`:

```python
def max_rounds(config, row):
    """#623: the item's fix-round cap: its recorded tier's override, else gates.max_rounds."""
    gates = config['gates']
    return gates['tier_max_rounds'].get((row.get('gates') or {}).get('tier')) or gates['max_rounds']


def rounds_used(data, item):
    """#623: fix rounds the item opened in this stage (the count resets at raise); a delta
    follows at least one, even after a manual transition."""
    used = (data.get('builds', {}).get(item) or {}).get('fix_rounds', 0)
    return max(used, int(data['items'][item]['phase'] == 'delta'))


def rotate(data, item, used):
    """#623: the next round answers each gate's delta verdict, so it becomes the gate's
    initial record and the record it replaces is kept as round<used>. Every verdict reader
    keeps reading initial and delta."""
    verdicts = data['gate_verdicts']
    for gate in gate_set(data['items'][item]):
        delta = verdicts.pop(f'{item}:{gate}:delta', None)
        if delta is not None:
            verdicts[f'{item}:{gate}:round{used}'] = verdicts[f'{item}:{gate}:initial']
            verdicts[f'{item}:{gate}:initial'] = delta
```

`next_step`, phase `gate`: move the feedback comprehension into
`_fix_feedback(data, item, roles, round_name)` (same text, `file` of that round's record) and
call it here and below. The tail of `next_step` (today lines 344-347) becomes:

```python
    blocking = [role for role, result in zip(roles, results) if result['blocks']]
    if blocking:
        cap = max_rounds(config, row)
        if rounds_used(data, item) >= cap:
            finding = next(text for text in results[roles.index(blocking[0])]['findings']
                           if re.search(verdict.BLOCKS_YES, text, re.I))
            return {'action': 'escalate', 'reason': (
                f'round cap {cap} reached: {blocking[0]} still blocks: '
                f'{" ".join(finding.splitlines()[0].split())}; unpark after a design change '
                'that closes it is recorded in the spec')}
        from wuwei.commands import build
        build.open_fix(item, _fix_feedback(data, item, blocking, 'delta'), root=root)
        return _fix(item, blocking)
    notes = [note for result in results for note in result['notes']]
    return {'action': 'raise', 'notes': notes}
```

Phase `fix` and the gate phase stay as they are: after `rotate` no `delta` key is left, so the
`fix round already used` check (line 304) only fires for a PR-stage fix, as today; the delta
phase reads the moved `initial` records, so the third round's roles are the gates whose
round-two verdict was FIX, and `_seats`, `delta_due`, `receive` and `opinion` continue the
same seats unchanged (their `first['head']` is the round-two head, which is the head the seat
stopped at).

`_delta_feedback`, standard variant only, appends: `A new finding on lines this fix round did
not change is blocks: no, unless it is a trust-boundary security finding.` The light re-read
text is unchanged.

### cli/wuwei/commands/build.py

`open_fix` (lines 169-221):

- Replace the literal check at line 190 with
  `cap = dispatch.max_rounds(workspace.load_config(root), data['items'][item])`,
  `used = dispatch.rounds_used(data, item)`, and
  `if used >= cap: raise ValueError(f'round cap {cap} reached (gates.max_rounds); park {item} for the owner (bin/wuwei why {item} shows the rounds)')`
  (lazy `from wuwei import dispatch`, as line 164 does).
- Line 193: accept `('gate', 'raised', 'delta')`.
- Line 200: the fresh brief name is `{item}-{"pr" if phase == "raised" else "gate"}-fix`,
  with `-{used + 1}` appended when `used`, so a second round never reuses a brief name.
- `update(fresh)`: when `phase == 'delta'`, call `dispatch.rotate(fresh, item, used)`;
  write `'fix_rounds': used + 1` instead of `1`.
- The event payload becomes `{'item': item, 'round': used + 1, 'cap': cap}`.

### cli/wuwei/guards/pr.py

`_recorded_gates` line 99: compare heads only among round-one records, and allow none:

```python
if len({row['head'] for row in initial if row.get('round', 'initial') == 'initial'}) > 1:
```

Line 104 onward is unchanged: a gate whose moved `initial` is FIX is judged on its `delta`,
a gate that passed earlier keeps today's head tolerance.

### cli/wuwei/retro.py

`_second_opinion` line 176: pair with the base gate's round-one record by value, so a moved
record never pairs with a later round:

```python
first = next((row for row in records.values() if row.get('item') == item
              and row.get('role') == role and row.get('round') == 'initial'), {})
```

### cli/wuwei/report.py

```python
def round_lines(rows):
    """#623: fix rounds per item today, and the items whose rounds reached their cap."""
```

From the `build.fix_opened` payloads: one line per item, sorted, `- <item>: <n> fix round(s)`
plus `, round cap <cap> reached` when any of its payloads has an integer `round >= cap`.
`build` adds `## Rounds` after `## Review seats`, only when non-empty, reading the day's
events with `watch.records(day / 'events.jsonl')` as the spec warnings already do.

### cli/wuwei/state.py

`RESERVED['gate_verdicts']` producer text: `wuwei dispatch receive or wuwei dispatch next`.

### tests/test_invariants.py and design 9.2

I35: "No item opens a fix round past its round cap: `build.open_fix` refuses at the cap and
`dispatch next` turns a blocking finding at the cap into `escalate`, for every cap and tier
override". `i35` walks `gates.max_rounds` in {1, 2, 3} x tier {light, standard, full} x
override {0, 1, 3}: `dispatch.max_rounds` equals the override when set, else `max_rounds`, and
`build.open_fix` on an item whose build record holds `fix_rounds` equal to that cap raises
`round cap`. Model the fixture on `i34`; add the 9.2 row (`test_table_matches_the_checks`
reads it), `READS['I35']` and `INVARIANTS['I35']`. Renumber if another branch took I35
first.

### Charters and docs

- `charters/_common.md` rule 5, replacing "Negotiation budget": "Round cap: at most
  `gates.max_rounds` fix rounds per item (a tier may set its own), counted the same for code,
  spec and document items and for the spec-done gate. A FIX verdict opens the first round;
  after a delta only a blocking finding opens the next. After the cap, put the remaining
  non-blocking findings in the PR body's review notes (a document's review notes) and ship;
  a blocking finding parks the item with a decision record naming the finding and what
  replaces the approach, never another round. After round one a new finding on lines the fix
  did not change is a note (blocks: no). A trust-boundary security finding always blocks."
  Keep the light re-read sentence. Bump `version` 1.7.0 to 1.8.0; run
  `bin/wuwei agents build`.
- `docs/site/configuration.md`: rows for `gates.max_rounds` and `gates.tier_max_rounds`
  (`{ light = 0, standard = 0, full = 0 }`, the `sessions.rotate_after` row is the model).
- `templates/workspace/config.toml` `[gates]`: two commented lines with the defaults.
- `docs/site/concepts.md` line 469: "the round cap (`gates.max_rounds`) is what stops the
  rounds".
- Hero alt text "at most one fix round" in `README.md`, `docs/site/index.md` and the `<desc>`
  of both `docs/site/assets/hero-*.svg`: "within the round cap".

### Existing tests whose meaning changes

Tests that encode the one-round budget write `[gates]\nmax_rounds = 1\n` into their
fixture config and expect the new reason:
`tests/test_dispatch.py::test_blocking_delta_escalates_and_bad_verdict_is_unmeasured` and
`::test_second_opinion_fix_opens_the_fix_round_and_its_delta_escalates` (reason starts with
`round cap 1 reached:`). `test_fix_pass_then_only_quality_delta` and
`test_delta_nonblocking_residual_becomes_review_note` keep `fix round already used` (phase
`fix` with a delta record). The builder runs the full suite and fixes any other fixture the
same way (walking days in `tests/test_path_day.py` and `tests/test_e2e_day.py` included),
never by weakening a cap or park expectation.

## What must not change

- Round one: a FIX verdict opens the first round; PASS everywhere raises, as today.
- A delta without a blocking finding raises with its notes, at any round.
- The verdict lint, `receive`, `delta_due`, `_seats`, `opinion`, `merge.py` and the launch
  guard: no edit (they read the moved `initial` and the new `delta`).
- The reset of `fix_rounds` at delta to raised (`state.py:474-475`).
- The steward's third-round note and negotiation-loop nudge.
- The light re-read feedback text.
- The design spec outside the 9.2 row.

Known drift, accepted: `why` and the tracker progress line look a past `gate.received` event
up by its key, so an earlier round's line reads the newer record; the file is the same seat
file either way.

## Project Structure

```text
cli/wuwei/workspace.py          gates.max_rounds, gates.tier_max_rounds
cli/wuwei/dispatch.py           max_rounds, rounds_used, rotate, _fix_feedback, next_step tail, _delta_feedback
cli/wuwei/commands/build.py     open_fix: cap, count, delta phase, brief name, rotate, event payload
cli/wuwei/guards/pr.py          _recorded_gates round-one head check
cli/wuwei/retro.py              _second_opinion round-one pairing
cli/wuwei/report.py             round_lines, ## Rounds
cli/wuwei/state.py              RESERVED producer text
charters/_common.md, agents/*.md
docs/site/configuration.md, docs/site/concepts.md, docs/site/index.md, docs/site/assets/hero-*.svg,
README.md, templates/workspace/config.toml
docs/specs/2026-09-24-wuwei-design.md   9.2 row I35 only
tests/test_dispatch.py, tests/test_pr_guards.py, tests/test_report_retro.py,
tests/test_invariants.py, tests/test_process_depth.py, tests/test_charters.py (rule anchor),
tests/test_workspace.py (gates defaults)
scripts/build-hero.py           the hero alt text the SVGs are generated from
```

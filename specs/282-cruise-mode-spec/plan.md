# Implementation Plan: Cruise mode, graduated autonomy per decision class, promoted from the ledger, with ceilings

**Branch**: `282-cruise-mode-spec` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

A spec-only change. The amendment to `docs/specs/2026-09-24-wuwei-design.md` is already in
the working tree, written by the spec author. It replaces the 5.8 routing-by-reversibility
paragraph with routing by class, adds one subsection, 5.8.1 Cruise mode (levels, class
table with defaults and ceilings, config keys, conditions, ceilings, merge mapping,
promotion and demotion, kill switch), and rewords one sentence each in G1, 4.6, 5.4, 5.9
and 6.8 so nothing contradicts it. The builder shows the phrase check red on main and
green here, reviews the wording for consistency, and runs the suite. No runtime code, no
test changes.

## Technical Context

Markdown only. The verification check below is a throwaway stdlib script run from a
scratch directory, never committed (the issue's acceptance: only the spec changes). The
existing `tests/test_docs.py` reads the design spec only in
`test_guard_boundaries_are_stated_once` (4.5, 9.1, section 10), which this change does not
touch.

## Constitution Check

- I (stdlib), II (three-state exits), III (one behaviour, one function): no runtime code.
- IV (test first): the phrase check is run red against a `git archive main` export before
  the amendment is accepted, then green on the worktree. Red is never produced by stashing
  or reverting the working tree.
- V (ponytail): one subsection, one table, sentences replaced rather than added; no config
  for the promotion thresholds; classes reuse existing vocabulary (5.3 residual findings,
  5.3 park, 4.6 never-auto dependency paths, 4.9 messages, 5.7 `unplanned`).
- VII (security): no refusal is weakened. Every widening of autonomy is owner-approved
  (promotion at the morning gate) and capped by ceilings; every narrowing is automatic.
- Governance: the design spec is amended only by its owner; the owner's evidence line is
  in the issue, and the owner merges.

## What was changed (spec author, already in the working tree)

All in `docs/specs/2026-09-24-wuwei-design.md`:

1. G1: "one-way-door decisions (5.8)" becomes "decisions cruise mode does not answer
   (5.8.1)".
2. 4.6, end of the first paragraph: one sentence naming the policy as the `merge` class
   of cruise mode at L2 or L3 with its conditions unchanged.
3. 5.4: the owner is asked for "decisions cruise mode routes to the owner (5.8.1)"; the
   digest lists "the decisions cruise mode answered".
4. 5.8 heading gains "amended 2026-10-01, #282"; the record shape gains `Class:`;
   `Decided-by:` is `owner` (seat-written) or `cruise <class>@L<n>` (CLI-written);
   "Routing by reversibility" becomes "Routing by class" (two sentences, keeps "When
   unsure, it is one-way"); Enforcement adds "with an unknown class" and moves the
   metrics to class and cruise reversals.
5. New `#### 5.8.1 Cruise mode (owner, 2026-10-01, #282)`, numbered like 4.2.1.
6. 5.9 tiers: "one-way-door decision" becomes "owner decision" (page and nudge); nudge
   adds "an L2 cruise answer (5.8.1)"; silent replaces "seat-taken two-way-door
   decisions" with "L3 cruise answers".
7. 6.8 promote lint: the target may also be "one cruise level, 5.8.1".

Net growth: 75 lines (102 added, 27 removed).

## Design decisions the builder must check against the issue

- Levels: L0 ask (today's owner path), L1 recommend (preselected, batch confirm), L2
  notify (acts at once, nudge, one-reply undo until `undo_minutes` after delivery), L3
  digest. Both L0 and L1 hold the item.
- Classes and defaults (one table): `approach`, `retry`, `park`, `accept-residual` at L2
  (what seats took on their own before); `defer`, `scope-cut`, `re-plan`,
  `dependency-bump` at L0; `merge` at L3 but gated by `merge.auto` (default off);
  `message` and `other` at L0 with an L1 ceiling.
- Config: `[decisions.cruise]` `enabled` true, `margin` 0.2, `max_per_day` 20,
  `undo_minutes` 60, `levels.<class>`. The config check refuses an unknown class, a level
  outside 0 to 3, or a level above the ceiling.
- Margin: (recommendation minus best other option) over 10 times the sum of weights,
  musts ignored for the runner-up, owner interview weights where they exist.
- Ceilings: issue list, made checkable per record (security finding cited; `unplanned`
  item or goal change; one-way; outside the workspace blast radius values).
- Promotion: steward proposal after 10 agreements, no reversal, 14 days; `wuwei promote`
  lands it only with morning-gate approval and never above the ceiling (same pattern as
  goal changes in 5.7). Demotion: automatic, one level, through the promote writer, ledger
  line with the cause. Weekly blind sample, one per class.
- Kill switch: `decisions.cruise.enabled = false`; status line `cruise off | L<max>`.

## Consistency review (builder)

Read these against 5.8.1 and edit only the design spec, only for a real conflict, keeping
the phrases the check pins:

- 4.6 (merge cap, soak, breaker), 4.7 (no deploys), 4.9 (auto-send tiers are not decision
  records), 5.3 (residual findings, park, cycle budget), 5.5 (steward), 5.6 (escaped
  defects), 5.7 (`unplanned`, goal changes need morning-gate approval), 5.9 (tiers, status
  line), 6.8 (promote, ledger), 15.8 (budget governor, undo log).
- A grep of the design spec for `one-way-door`, `seat-taken`, `seat or owner` and
  `Routing by reversibility` finds nothing.

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `.github/`, `docs/site/`, `README.md`. The shipped
  routing (`cli/wuwei/decision.py` `route`, `seat_outcome`, the `Decided-by` values;
  `cli/wuwei/commands/build.py` `_park`; `charters/_common.md:28`;
  `docs/site/concepts.md:82`; `docs/site/reference.md:36`) stays as is until the
  implementation issue.
- `tests/`: no file changes.
- `.specify/memory/constitution.md`: unchanged.
- Design 4.5, 9.1 and section 10: untouched, so `test_guard_boundaries_are_stated_once`
  keeps passing.

## Verification commands

Run from the repository root. `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs | tar -x -C <scratch>/main
python3 <scratch>/check_282.py <scratch>/main   # must fail: AssertionError: `Class:`
python3 <scratch>/check_282.py .                # must print: OK: cruise mode stated once
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify   # must be empty
python -m pytest -q
```

`<scratch>/check_282.py`:

```python
import re, sys
from pathlib import Path
spec = (Path(sys.argv[1]) / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
flat = lambda text: ' '.join(text.split())
part = lambda pattern: flat((re.search(pattern, spec, re.S | re.M) or [''])[0])
framework = part(r'^### 5\.8 .*?(?=^#### )')
cruise = part(r'^#### 5\.8\.1 .*?(?=^### )')
asked, merge, signals = (part(rf'^### {n} .*?(?=^### )') for n in (r'5\.4', r'4\.6', r'5\.9'))
for phrase in ('`Class:`', 'with an unknown class', 'Routing by class',
               '`cruise <class>@L<n>` written by the CLI'):
    assert phrase in framework, phrase
for name, default, ceiling in (('approach', 2, 3), ('retry', 2, 3), ('park', 2, 3),
                               ('accept-residual', 2, 3), ('defer', 0, 3), ('scope-cut', 0, 3),
                               ('re-plan', 0, 3), ('dependency-bump', 0, 3), ('merge', 3, 3),
                               ('message', 0, 1), ('other', 0, 1)):
    assert re.search(rf'\| `{name}` \| [^|]+ \| L{default} \| L{ceiling} \|', cruise), name
for phrase in ('L0 ask', 'L1 recommend', 'L2 notify', 'L3 digest',
               'a new class is an amendment to this section, not config',
               '`enabled` (default true)', '`margin` (default 0.2)', '`max_per_day` (default 20)',
               '`undo_minutes` (default 60)', 'refuses an unknown class',
               'a level above the class\'s ceiling', '`Reversibility: two-way`',
               '`own branch`, `own PR` or `workspace`', 'owner\'s weights from the calibration interview',
               'a thin margin', '`Decided-by: cruise <class>@L<n>`', 'messages to people',
               'merges to a repository whose base deploys', 'trust-boundary findings',
               'anything one-way', 'outside the item\'s goals', '`merge.auto = true`',
               'after 10 agreements and no reversal in that class over 14 days',
               'owner approved it at the morning gate', 'three thin-margin escalations in a row',
               'escaped defect (5.6)', 'the ledger line records why', 'Once a week the steward',
               'counts as a reversal', '`decisions.cruise.enabled = false` runs every class at L0',
               '`cruise off | L<max>`', 'running level lives in `memory/cruise.json`',
               'only lowers a class', 'lowest of the running level, the config level and the ceiling',
               'scope agreed with other people', 'passing its musts or not',
               'replace the other conditions above, unchanged; the ceilings still apply'):
    assert phrase in cruise, phrase
whole = flat(spec)
for once in ('`margin` (default 0.2)', '`max_per_day` (default 20)',
             '`undo_minutes` (default 60)', 'after 10 agreements',
             'cruise off | L<max>', 'decisions.cruise.enabled'):
    assert whole.count(once) == 1, once
assert 'cruise mode routes to the owner (5.8.1)' in asked and 'one-way-door' not in asked
assert 'lists the decisions cruise mode answered' in asked
assert '`merge` class of cruise mode (5.8.1) at L2 or L3' in merge
assert 'L2 cruise answer (5.8.1)' in signals and 'L3 cruise answers' in signals
assert 'seat-taken' not in whole and 'Routing by reversibility' not in whole
assert 'decisions cruise mode does not answer (5.8.1)' in whole and "one class's running level in `memory/cruise.json`, 5.8.1" in whole
assert '\N{EM DASH}' not in spec
print('OK: cruise mode stated once')
```

## Deferred (the implementation issue, after #279 and the owner's first real day)

- `Class:` in `cli/wuwei/decision.py` FIELDS and the lint; `Decided-by` values; `route`
  and `seat_outcome` replaced by the cruise conditions; `_park` in
  `cli/wuwei/commands/build.py` writing `Class: park`.
- `[decisions.cruise]` in `templates/workspace/config.toml`, `docs/site/configuration.md`
  and the config check; the status line text; 5.9 tiers in `wuwei signal classify`.
- Promotion and demotion through `wuwei promote` and the ledger; the weekly sample.
- Charters (`_common.md`, `planner.md`, `steward.md`, `lead.md`) and the docs site.

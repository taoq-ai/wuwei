# Implementation Plan: Assume and record on two-way doors, the mandate block, external confirmation is never a seat precondition, time-boxed waits

**Branch**: `301-negotiation-spec` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

A spec-only change. The amendment to `docs/specs/2026-09-24-wuwei-design.md` is already in
the working tree, written by the spec author. It adds one subsection, 5.8.2 External waits
and negotiation loops, and replaces or extends sentences in 4.1, 4.6, 5.2, 5.3, 5.4, 5.8,
5.8.1 and 5.9 so each rule is stated once and nothing contradicts it. The builder shows
the phrase check red on main and green here, reviews the wording for consistency, and
runs the suite. No runtime code, no test changes.

## Technical Context

Markdown only. The verification check below is a throwaway stdlib script run from a
scratch directory, never committed (the issue's acceptance: only the spec changes). The
existing `tests/test_docs.py` reads the design spec only in
`test_guard_boundaries_are_stated_once` (4.5, 9.1, section 10, and the constitution's
"design reconsideration recorded in its spec" and "#222"), none of which this change
touches.

## Constitution Check

- I (stdlib), II (three-state exits), III (one behaviour, one function): no runtime code.
- IV (test first): the phrase check is run red against a `git archive main` export before
  the amendment is accepted, then green on the worktree. Red is never produced by stashing
  or reverting the working tree.
- V (ponytail): one subsection; sentences replaced rather than added; the budget restated
  in one place (4.6 now points to 5.3); no new mechanism where an existing one serves:
  assumptions reuse the spec and PR body `Assumptions:` section, the time box reuses the
  watch sweep, the loop signal reuses steward runs, the nudge and page tiers, the control
  plane and the status line; unnecessary asks reuse the 5.8.1 agreement count.
- VII (security): no refusal is weakened. The question guard widens to every runtime;
  `negotiation.loop` is CLI-written only; external drafts keep the 4.9 approve tier and the
  `message` ceiling L1.
- Workflow, Cycle budget: 5.3 now cites the constitution and agrees with it; the
  constitution is unchanged.
- Governance: the design spec is amended only by its owner; the owner's evidence line is
  in the issue, and the owner merges.

## What was changed (spec author, already in the working tree)

All in `docs/specs/2026-09-24-wuwei-design.md`:

1. 4.1 hook table, SubagentStop row: also flags a last message that asks the owner a
   question without a decision id (5.8).
2. 4.6 merge preconditions: "at most the cycle budget (one fix round plus one delta)"
   becomes "at most the negotiation budget (5.3)".
3. 5.2: new "Briefs" paragraph after the flow, the mandate block: decides alone, decides
   and records, goes to the owner, generated from class levels (5.8.1) and the calibration
   interview answers; closes with "nothing else is a question".
4. 5.3: new "Assume and record" bullet; "Cycle budget" becomes "Negotiation budget" with
   the lint sentence and the design reconsideration.
5. 5.4: "Never for what a seat's mandate lets it decide (5.2)."
6. 5.8: heading adds #301; "Every decision, whoever takes it, is a record" becomes "Every
   decision that the owner or cruise mode answers is a record ... a two-way open question
   inside the item is an assumption instead (5.3)"; Enforcement states the every-runtime
   question rule (PreToolUse plus SubagentStop) and adds owner asks per item and
   unnecessary asks to the steward metrics.
7. 5.8.1 class table: `approach` "an assumption, not a record, at L2 or L3 (5.3)";
   `message` "an external confirmation holds no reversible work (5.8.2)".
8. New `#### 5.8.2 External waits and negotiation loops (owner, 2026-10-01, #301)`:
   external confirmation, `decisions.wait_hours` time box, negotiation-loop detection.
9. 5.9: page adds "a negotiation loop on an item past its goal date"; nudge adds "a
   negotiation loop (5.8.2)"; the status line adds "the day's negotiation loops (5.8.2)".

Net growth: 50 lines (70 added, 20 removed).

## Design decisions the builder must check against the issue

- Assume and record covers two-way open questions inside the item, which is the
  `approach` class while it runs at L2 or L3. Below L2 the mandate moves approach to the
  owner as a record, so cruise demotion still means something.
- The mandate block is three generated lists plus a fixed closing line. Inputs: class
  levels (effective level per 5.8.1), the interview's `risk` and `manual` answers. Text
  shape and placement in `brief.launch_prompt` are #302's.
- External confirmation is a `message` record with `assumption: external` on the item;
  reversible work continues. The time box `decisions.wait_hours` (default 24 weekday hours
  in `owner.timezone`) is applied by the watch sweep, not the steward seat (5.5 forbids
  the steward to change item state): two-way proceeds per the recommendation, one-way
  parks with a decision record; both write an event.
- Negotiation budget: one fix round plus one delta per gate, stated once in 5.3; the lint
  sentence restates the shipped verdict lint (`cli/wuwei/verdict.py` SCENARIO and the
  probe row, `not run` still accepted); exceeding it parks for a design reconsideration.
- Loop signals per item in `steward.loop_window_hours` (default 4): decision and
  clarification records naming the item, gate verdicts, re-dispatches of a role already
  dispatched on it, fix-round continuations (gate or PR feedback, as from
  `cli/wuwei/commands/build.py` `open_fix`, not fast-check backpressure). Trigger: sum
  above `steward.loop_threshold` (default 9) or a second fix round at any gate. Output:
  one CLI-written `negotiation.loop` event per item per day with counts and the last two
  exchanges; nudge, page past the goal date (5.7); DM summary through the control plane
  within `control_plane.content`; `loops N` on the status line. It never parks or
  re-plans.
- Metrics: owner asks per item and unnecessary asks (owner answer equal to the
  recommendation) are steward metrics, stated in 5.8 Enforcement, and are the agreements
  5.8.1 promotion counts.

## Consistency review (builder)

Read these against the amendment and edit only the design spec, only for a real conflict,
keeping the phrases the check pins:

- G1 (asks the owner only for what cruise mode does not answer), 4.2 (watch sweep), 4.6,
  4.9 (external parties are the approve tier), 5.5 (steward never changes item state),
  5.7 (goal `date`), 5.8.1 (levels, `message` ceiling L1, promotion agreements), 5.9
  (tiers, status line), 15.4 (`control_plane.content`).
- The constitution's Workflow "Cycle budget" line agrees with 5.3 (one fix round plus one
  delta; then a design reconsideration agreed with the owner before more code).
- A grep of the design spec for `Cycle budget:`, `cycle budget (one` and `Every decision,
  whoever takes it` finds nothing.

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `.github/`, `docs/site/`, `README.md`. The shipped
  pieces #302 changes stay as they are here: `cli/wuwei/brief.py` `launch_prompt`,
  `cli/wuwei/steward.py` `review`, `cli/wuwei/metrics.py` `collect`,
  `cli/wuwei/guards/decision.py` `check_question`, `cli/wuwei/guards/agent_launch.py`
  (SubagentStop), `cli/wuwei/signal.py`, `cli/wuwei/commands/status.py` `line`,
  `charters/_common.md:21` and `:27-28`, `templates/workspace/config.toml`.
- `tests/`: no file changes.
- `.specify/memory/constitution.md`: unchanged.
- Design 4.5, 9.1 and section 10: untouched, so `test_guard_boundaries_are_stated_once`
  keeps passing.

## Verification commands

Run from the repository root. `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs | tar -x -C <scratch>/main
python3 <scratch>/check_301.py <scratch>/main   # must fail: AssertionError: mandate block
python3 <scratch>/check_301.py .                # must print: OK: negotiation rules stated once
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md .specify   # must be empty
python -m pytest -q
```

`<scratch>/check_301.py`:

```python
import re, sys
from pathlib import Path
spec = (Path(sys.argv[1]) / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
flat = lambda text: ' '.join(text.split())
part = lambda pattern: flat((re.search(pattern, spec, re.S | re.M) or [''])[0])
hooks = part(r'^### 4\.1 .*?(?=^### )')
flow, rules, asked, signals = (part(rf'^### {n} .*?(?=^### )') for n in (r'5\.2', r'5\.3', r'5\.4', r'5\.9'))
framework = part(r'^### 5\.8 .*?(?=^#### )')
cruise = part(r'^#### 5\.8\.1 .*?(?=^#### )')
loops = part(r'^#### 5\.8\.2 .*?(?=^### )')
for phrase in ('mandate block', "item's class levels (5.8.1)", 'calibration interview answers',
               'decides alone', 'decides and records', 'goes to the owner',
               'nothing else is a question', 'A seat does not ask what it may decide'):
    assert phrase in flow, phrase
for phrase in ('Assume and record', 'is not asked', '`Assumptions:`',
               'what was assumed, why, what would overturn it', 'Gates review assumptions as findings',
               'Only a one-way door', 'Negotiation budget', 'one fix round plus one delta check per gate',
               'become review notes', 'without a failure scenario', 'probe or mutation row',
               'design reconsideration, never another round', 'agreed with the owner before more code'):
    assert phrase in rules, phrase
assert 'Cycle budget:' not in rules
assert "Never for what a seat's mandate lets it decide (5.2)" in asked
for phrase in ('two-way open question inside the item is an assumption instead (5.3)',
               'A seat question that is not a decision record is refused, in every runtime',
               'SubagentStop flags', 'owner asks per item', 'unnecessary asks',
               'an owner answer equal to the recommendation', 'When unsure, it is one-way'):
    assert phrase in framework, phrase
assert 'Every decision, whoever takes it, is a record' not in flat(spec)
assert 'an assumption, not a record, at L2 or L3 (5.3)' in cruise
assert 'an external confirmation holds no reversible work (5.8.2)' in cruise
for phrase in ('never a precondition a seat may impose', 'a draft the owner sends', 'ceiling L1',
               '`assumption: external`', 'reversible work on it continues',
               '`decisions.wait_hours`', '(default 24', 'weekday hours in `owner.timezone`',
               "confirms the item's `assumption: external` reading", 'the draft stays unsent with the owner',
               'no other 5.8.1 ceiling applies', 'parks the item with a decision',
               '`steward.loop_window_hours` (default 4)', '`steward.loop_threshold` (default 9)',
               'decision and clarification records naming the item', 'gate verdicts',
               're-dispatches of a role', 'fix-round continuations', 'second fix round',
               'one `negotiation.loop` event per item per day', 'written only by the CLI',
               'last two exchanges', 'a page when the item is past the date of the goal',
               'control plane sends', '`control_plane.content`', '`loops N`'):
    assert phrase in loops, phrase
assert 'negotiation loop on an item past its goal date' in signals
assert 'a negotiation loop (5.8.2)' in signals and "the day's negotiation loops (5.8.2)" in signals
assert 'without a decision id (5.8)' in hooks
assert 'a 5.8.1 ceiling or trust-surface area, or a question outside the item' in flat(spec)
assert "which cruise mode answers under 5.8.1's conditions or routes to the owner" in flat(spec)
assert 'the reconsideration is recorded in its spec' in flat(spec)
assert 'at most the negotiation budget (5.3)' in part(r'^### 4\.6 .*?(?=^### )')
whole = flat(spec)
for once in ('decisions.wait_hours', 'steward.loop_window_hours', 'steward.loop_threshold',
             'one fix round plus one delta', 'negotiation.loop', 'mandate block',
             'what was assumed, why'):
    assert whole.count(once) == 1, once
assert '\N{EM DASH}' not in spec
print('OK: negotiation rules stated once')
```

## Deferred (#302, same chain)

- `brief.launch_prompt` mandate block; planner skill and role charters say it once.
- `Assumption:` finding kind in the verdict lint; gate briefs review assumptions.
- SubagentStop flag for a question without a decision id (Codex and headless paths).
- `decisions.wait_hours` in the config template, config check and docs; the watch-sweep
  time box and its events; `assumption: external` on the item.
- `steward.loop_window_hours`, `steward.loop_threshold`; the loop detector in
  `steward.review`; `negotiation.loop` reserved for the CLI producer; signal tiers; DM
  through the control plane; `loops N` in `status --line`.
- `asks_per_item` and `unnecessary_asks` in `metrics.py`, the report and the retro.

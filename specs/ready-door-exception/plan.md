# Implementation Plan: the ready and reviewer doors honour an owner exception the way wuwei evidence does

**Branch**: `fix/1168-ready-door-exception` | **Spec**: `specs/ready-door-exception/spec.md`

## Summary

`create_door` takes an optional PR reference. With one, it passes its gate gaps through
`evidence.excepted` at the head those gaps name. `ready_door` passes `<repo>#<number>`. `excepted`
drops the `verdict ... not counted` lines when it drops a gate gap.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_guards.py and tests/test_evidence.py. Runtime 3,321 lines at
8a92be7; this item may add 5.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the door and `wuwei evidence` now read one exception rule.
- III. An auditor: no new door; the ready door refuses less only where the owner accepted the gap.
- V. Test first: the new tests ran red on 646e462's code (37 failed, 33 passed) before the change.
- VI. Budgets: no config key; runtime within 5 lines.
- VII. Security first: the exception still needs the exact PR, the exact head and the exact gap or
  gate list; the create door is unchanged.

## Design

- `create_door(root, repo, branch, base, text, act=OPEN, ref='')`: keep the compare head in a name;
  after `gate_gaps`, `found = evidence.excepted(root, ref, head, found) if ref else found`. The
  "no plan item is named" line is added after, so it shows only when a gap stands.
- `ready_door` passes `ref=f'{repo}#{number}'`.
- `excepted`: keep the gaps no ruling names; if a dropped gap is a gate gap (`GATES.match`), also drop
  each kept gap that starts `verdict ` and holds ` not counted: `.

## Lines

guards.py +2, evidence.py +2: runtime 3,321 to 3,325.

## Probes

- `specs/ready-door-exception/route_probe.py` reads the route corpus through the guards with a
  ruling form per run (none; an approved exception on the draft `o/r#7` at its head by gap text and by
  gate list; one on `o/r#5`; one at another head; one not approved), at main and at the head.
- `specs/ready-door-exception/ruling_probe.py` crosses ruling PR spellings, heads, gap texts and
  approval through three ready routes against an oracle written apart from the code, then runs every
  ready and create route of the corpus under the exact ruling and under real bash with a stub `gh`.
- `specs/ready-door-exception/mutants.py` applies a mutant of each new condition to both copies.
- `specs/excepted-exact/probe.py` oracle: a not-counted line is named when the accepted gap names a
  gate gap of the list. Its generated pairs run in `test_no_generated_accepted_gap_waives_a_gap_it_does_not_name`.

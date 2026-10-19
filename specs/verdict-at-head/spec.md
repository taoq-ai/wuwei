# Feature Specification: a gate is read from its verdict at the newest head on this PR

**Feature branch**: `fix/verdict-at-head`
**Item**: verdict-at-head, tier full, goal G-2
**Input**: `evidence.gate_gaps` takes the last verdict per gate in ledger order. A PASS at an older
head attested after a FIX at the PR head clears the gate, and a PASS recorded for another PR of
the item counts here.

## The promise in my words

`gate_gaps` decides, per gate, which verdict holds. Today the last one attested wins, whatever
head it read. It should read each gate the way #1135 taught `breaking_gaps` to read Breaking:
walk the verdicts oldest first, and let a later verdict replace the held one only when it read
newer code on this PR's line. The walk is shared, not written twice. A finding still displaces a
pass, as it does today. The small-delta carry rule (a quality-only delta of at most 20 lines needs
no gate) stays as it is.

The acceptance scenarios, restated:

1. An arch FIX at the PR head, then an arch PASS at an older ancestor head attested after it:
   `evidence.gaps` still owes arch at the head.
2. A PASS whose head is not an ancestor of the PR head, or one recorded for another PR of the
   same item: it does not count.
3. A FIX at the PR head, then a PASS at the same head: the gate is still owed.

## Clarifications

### Session 2026-10-18

- Q: When does a later verdict replace the held one? A: When nothing is held; when its head differs
  from the held head, descends from it and is an ancestor of the PR head (the #1135 walk); or when
  it is a finding (FIX or ESCALATE) and the held one is a PASS.
- Q: A finding at an older head attested after a finding at a newer head? A: The newer one holds.
  Otherwise a PASS at the newer head could clear the newer finding through the older one.
- Q: A finding at an older head attested after a PASS at a newer head? A: It displaces the pass, as
  on main: the gate reads again.
- Q: Which PR does a PASS count for? A: The PR read (`owner/repo#n`, any case); a verdict that names
  only the repository (written before the draft PR existed); or an imported 0.34 verdict, which
  names none. A PASS for another PR or another repository counts nowhere.
- Q: A finding recorded for another PR of the item, at an ancestor of the PR head? A: It holds. It
  is a finding about code this PR contains. Only a PASS must be for this PR (see Assumptions).
- Q: The create and ready doors read no PR (`guards.create_door` passes no ref). A: A PASS counts
  there when its repository is the one the door reads.
- Q: The same head written short and in full? A: Heads compare on their first 7 characters, as the
  same-head rule on main did.

## Requirements

- FR-001: Each gate's verdicts are walked oldest first through one shared test (`newer`), the one
  `breaking_gaps` uses. A verdict is read only at an ancestor of the PR head.
- FR-002: A PASS is read only for this PR, its repository alone, or no PR (imported); with no PR
  read, only for the repository read.
- FR-003: A finding replaces a held PASS; a PASS never replaces a finding at the same or a newer
  head.
- FR-004: The small-delta carry rule and the delta gate choice are unchanged.
- FR-005: Runtime within the item's budget of 5 lines and at or under 3,400.
- FR-006: An arch `Breaking: no` clears a yes only when it names this PR or its repository alone
  (round 1, from the security gate's note); a yes holds from any PR of the item.
- FR-007: `gate_gaps` asks the code host once per verdict whether its head is under the PR head
  (round 1, from the quality gate's finding).

## How this fails

1. A PASS that did not read this PR's code at or below its head clears a gate: one from another
   PR, another repository, or a head off the PR's line. Bound: a PASS counts only for this PR (its
   repository at the doors) and only at an ancestor of the head. Held by fixtures through
   `evidence.gaps` (`test_a_gate_is_read_from_its_verdict_at_the_newest_head_on_this_pr`: a
   non-ancestor head, `acme/app#7`, `acme/other#42`) and through `gate_gaps` with no PR read
   (`test_before_its_pr_is_read_a_verdict_counts_on_its_repository`). The history probe checks it
   as the "ignored" property over every generated history.
2. A relaunched or stale seat clears a finding: a PASS at the same head as a FIX, or at an older
   head, attested later. Bound: a PASS replaces a held verdict only from a strict descendant of its
   head on the PR's line; an older finding never moves a newer one back. Held by fixtures (FIX then
   PASS at the head; FIX at the head then PASS at an older ancestor; FIX at the head, FIX at an
   older head, PASS at the head) and by the probe's "no-clear" property.
3. The doors refuse clean work: a verdict filter that drops the PR's own verdicts would hold every
   merge, ready flip and create. Bound: only a PASS naming another PR or repository is dropped.
   Held by the route corpus probe (`route_probe.py`): every route that moves names a PR or a
   repository other than the one its door reads. Left open: at the create and ready doors no PR is
   read, so a PASS for another PR of the item in the same repository still counts there.

## Probe results

Read at main `5fe8347` and at this branch's head (round 1; round 0 read main `d7c4f43`) with
`python3 -I specs/verdict-at-head/probe.py <main tree> <head tree>`; the main tree is
`git archive origin/main` in a scratch folder. Heads: OLD, MID, HEAD on the PR's line, NEW a
descendant of the PR head, OTHER off the line; PR forms: this PR, another PR, another repository,
repository only, imported; reads with the PR (`acme/app#42`) and with none (the doors); deltas of
10 and 300 lines.

Output (`PROBE_TMP=<scratch folder>` keeps its case folders off `/tmp`):

```
cases generated: 48592
cases whose gate result moves: 7479
  72: head owes less, from a PASS for another PR or repository
  244: head owes less, from the walk
  6189: head owes more, from a PASS for another PR or repository
  974: head owes more, from the walk
distinct verdict shapes where the walk owes less: 26; each holds a PASS at the head attested before the last verdict: True
main: ignored holes 6175, no-clear holes 864, compare calls 86944
head: ignored holes 0, no-clear holes 0, compare calls 84454
```

Round 0 made 86,095 compare calls; round 1 removed the repeated PR-head check. The moves file is
byte-identical to round 0's (sorted, sha256
`1069931ea5712ab2ac48c4f6bcf933795099915d01c73410178f15a169877ba8` both times), and main's
`gate_gaps` did not change between `d7c4f43` and `5fe8347`, so the head's result is unchanged on
every case.

Long histories (`python3 -I specs/verdict-at-head/calls.py <tree> <scratch folder>`): one line of
N heads, three gates verdicted per head, read at the last head, in three shapes (a FIX at every
head but the last, a PASS at every head, alternating). Every shape gives the same counts:

```
heads   main   round 0   head
   10     27        78     54
   20     57       168    114
   40    117       348    234
```

The head asks each verdict once whether it is under the PR head, as main does, and once whether
it descends from the verdict held: 2.0x main on a long history.

Every one of the 316 cases where the head owes less is a delta review on main ("no gate passed at
head") that is clean at the head, and each holds a PASS for this PR at the PR head: main moved its
last pass back to an older head attested later and asked for a delta review the head pass already
covers. Every other move owes more at the head. Both properties hold at the head with no hole;
main has 6,175 "ignored" and 864 "no-clear" holes.

Route corpus (`tests/fixtures/routes.json`, sha256
`9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0` at main 5fe8347 and at the
head), each route read through `guards.bash` with one quality PASS attested in each of six forms,
at main and at the head (round 1; round 0 read 251 routes at d7c4f43 with the same 142 moves):

```
reads 1542 1542 routes 257
moved 142
  13: PASS for acme/app#42: pass -> create
  23: PASS for acme/app#42: pass -> merge
  21: PASS for acme/app#42: pass -> ready
  1: PASS for o/r: pass -> merge
  2: PASS for o/r: pass -> ready
  1: PASS for o/r#5: pass -> merge
  2: PASS for o/r#5: pass -> ready
  23: PASS for o/r#7: pass -> merge
  2: PASS for o/r#7: pass -> ready
  13: PASS for other/x#5: pass -> create
  22: PASS for other/x#5: pass -> merge
  19: PASS for other/x#5: pass -> ready
```

Every move is pass to a door, and each names a PR or repository other than the one its door
reads. The 23 `o/r#7` merge moves are merge routes on `o/r#5`; every other `o/r`, `o/r#5` and
`o/r#7` move is a route naming `https://github.com/other/x/pull/...`, whose door reads `other/x`.
No route moves from a door
to pass, and no route moves for a PASS for the PR it reads. No guard code changed; the corpus file
is the same at main and at the head.

## Assumptions

- A finding for another PR of the item (or another repository) at an ancestor of the PR head
  holds here; only a PASS must be for this PR. Why: the promise's "on this PR" read for findings
  too would let a finding about code on this PR's line drop, a loosening the acceptance does not
  ask for (the acceptance names a PASS). Overturned if the owner wants findings read per PR too.
- A verdict that names only the repository, or an imported 0.34 verdict with no PR, counts for any
  PR of the item in that repository, as before. Why: those verdicts were written before a PR
  number existed.
- At the create and ready doors no PR is read, so a PASS for another PR of the item in the same
  repository counts there. Closing it needs `guards.ready_door` to pass its PR to `gate_gaps`, a
  guard change outside this item's files: a candidate item.
- Two distinct heads that share their first 7 characters read as one head, as main's same-head
  rule did.
- `breaking_gaps` compares heads on 7 characters through `newer` instead of in full; every arch
  verdict it reads is parsed, so its heads are 40 characters and the reading is unchanged.
- Runtime: +5 over main (3,026 at 5fe8347 to 3,031), measured with `cat cli/wuwei/*.py | wc -l`;
  budget 5. Round 1 removed a repeated call without a line.

Rollback: revert the commit; `gate_gaps` again takes the last verdict per gate in ledger order.

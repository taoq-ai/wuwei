# Feature Specification: a breaking change is read from the latest arch verdict

**Feature branch**: `fix/breaking-latest`
**Item**: breaking-latest, tier full, goal G-2, issue #1129
**Input**: `evidence.breaking_gaps` holds a PR for an announcement when any arch verdict the item
ever had said `Breaking: yes`. A later arch re-read that says `Breaking: no` does not clear it, so
a superseded verdict holds the merge on a false safety gap.

## The promise in my words

`breaking_gaps` asks two things. Did the author declare a break (a `!` before the colon in the
title, or a `BREAKING CHANGE:` line in the body)? Or did the arch gate find one? The second
question now reads the item's latest arch verdict instead of any verdict ever. `verdicts()`
already returns attested verdicts oldest first. A declared break counts on its own, whatever the
arch verdicts say. How the arch gate decides `Breaking:` is outside this item.

"Latest" is read safely (security round 1). The arch verdicts are walked oldest first, and the
current verdict is replaced only when:

- the new verdict says yes (a yes holds at any head), or
- it is the first arch verdict, or
- its head strictly descends from the current verdict's head and is an ancestor of the PR head.

So a later `no` clears a `yes` only when it read newer code on this PR's line. A `no` at an older
head, at a head off the PR's line, on another PR or repository, or at the same head as the `yes`
clears nothing. The same-head rule matches the one `gate_gaps` applies to a FIX verdict.

The acceptance scenarios, restated:

1. An arch verdict says `Breaking: yes` at head A; a later arch PASS says `Breaking: no` at head B,
   the PR head. Evidence shows no breaking gap.
2. An arch verdict says `Breaking: no` at A; a later one says `Breaking: yes` at B. Evidence shows
   "breaking change without an announcement".
3. A PR titled `fix(x)!: ...` whose arch verdicts all say `Breaking: no` still shows the
   announcement gap.

## Clarifications

### Session 2026-10-18

- Q: Two arch verdicts at one head, a yes then a no: which wins? A: The yes. A later no at the
  same head does not clear it, so relaunching arch until it says no cannot clear a break.
- Q: An arch `no` at an older head attested after a `yes` at the PR head? A: It clears nothing.
  The older head does not descend from the yes's head.
- Q: An arch `no` at a head that is not an ancestor of the PR head (another branch, a force-pushed
  head), or from the same item on another PR or repository? A: It clears nothing. Its head is not
  on the PR head's line.
- Q: A `yes` at an older head attested after a `no`? A: It holds; a yes replaces at any head.
- Q: Do file names decide? A: No. `verdicts()` walks the ledger's attest rows, so the name of a
  verdict file does not rank it.
- Q: An arch verdict whose file was edited after attesting keeps only its recorded gate, verdict
  and head, with no Breaking field. Does it count? A: No. Only arch verdicts that carry a Breaking
  field (every parsed verdict does) are read.

## Requirements

- FR-001: When the PR declares no break, the breaking gap follows the arch verdict reached by
  walking, oldest first, the arch verdicts that carry a Breaking field. A yes always replaces the
  current one. A no replaces it only when its head strictly descends from the current head and is
  an ancestor of the PR head.
- FR-002: A `!` title or a `BREAKING CHANGE:` line raises the gap whatever the arch verdicts say.
- FR-003: The runtime stays at or under 3,000 lines. The item's budget was 2. The safe reading
  takes 4 over main (2,976 to 2,980), an overrun the planner accepted.

## How this fails

1. An arch verdict that did not review newer code on this PR's line says `no` and clears a real
   break. Bound: a `no` clears a `yes` only from a strict descendant of the yes's head that is an
   ancestor of the PR head. Held by fixtures through `evidence.gaps` in
   `test_breaking_is_read_from_the_latest_arch_verdict`:
   - F1, a stale `no` at an ancestor;
   - F2, a `no` at a non-ancestor head;
   - F3, a `no` from another PR or another repository;
   - a `no` at the same head;
   - a `no` at a descendant of the yes's head that the PR head dropped
     (`test_a_no_on_a_dropped_descendant_of_the_yes_clears_nothing`).

   Left open: an arch seat at a descendant head on the PR's line that wrongly says `no`. That is
   the trust the arch gate already holds for its PASS.
2. A verdict whose file was edited after attesting (kept as a FIX record without its Breaking
   line) reads as "no" and drops a found break. Held: such records are skipped, tested by
   `test_an_edited_arch_verdict_that_kept_no_breaking_field_leaves_the_last_one_that_did`.
3. The vendored copy under `.claude/wuwei/` drifts and the evidence that runs keeps the old rule.
   Held by the vendored drift test; re-vendored with `setup.vendor('.')`.

## Assumptions

- Ancestry, not ledger order alone, decides whether a `no` supersedes a `yes`. Why: security
  round 1 showed (F1) that ledger order lets a stale seat clear a break. Overturned if the owner
  wants a `no` at the same head to clear a `yes`.
- An unreadable ancestry check (the code host fails) raises out of `breaking_gaps`. `gaps` then
  shows the PR as unreadable, never clean, as it does for the same check in `gate_gaps`.
- A verdict matched by its PR reference (not its item) counts as the item's verdict, as it does
  for every other gap today. Why: `verdicts()` already joins both. Overturned if the owner wants
  only the item's own verdicts read for Breaking.
- Runtime overrun: +4 lines over main against a budget of 2, measured with
  `cat cli/wuwei/*.py | wc -l` (2,980). The planner accepted it in the fix round.

Rollback: revert the commit; `breaking_gaps` again reads any arch verdict ever.

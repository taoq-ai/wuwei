# Feature Specification: a breaking change is read from the latest arch verdict

**Feature branch**: `fix/breaking-latest`
**Item**: breaking-latest, tier full, goal G-2, issue #1129
**Input**: `evidence.breaking_gaps` holds a PR for an announcement when any arch verdict the item
ever had said `Breaking: yes`. A later arch re-read that says `Breaking: no` does not clear it, so
a superseded verdict holds the merge on a false safety gap.

## The promise in my words

`breaking_gaps` asks two things: did the author declare a break (a `!` before the colon in the
title, or a `BREAKING CHANGE:` line in the body), or did the arch gate find one? The second
question now reads only the item's latest arch verdict: the last attested arch verdict in ledger
order. `verdicts()` already returns attested verdicts oldest first, so the last arch entry is the
latest. A declared break counts on its own, whatever the arch verdicts say. How the arch gate
decides `Breaking:` is outside this item.

The acceptance scenarios, restated:

1. An arch verdict says `Breaking: yes` at head A; a later arch PASS says `Breaking: no` at head B,
   the PR head. Evidence shows no breaking gap.
2. An arch verdict says `Breaking: no` at A; a later one says `Breaking: yes` at B. Evidence shows
   "breaking change without an announcement".
3. A PR titled `fix(x)!: ...` whose arch verdicts all say `Breaking: no` still shows the
   announcement gap.

## Clarifications

### Session 2026-10-18

- Q: Two arch verdicts at one head: which wins? A: The one attested last. Ledger order is the
  only order; the head does not rank them.
- Q: An arch verdict at an older head attested after one at the PR head? A: The promise says
  ledger order, so the later row wins. When it says yes, the gap shows (the safe direction).
  When it says no, it clears a yes at the PR head; see How this fails 1.
- Q: Do file names or file times decide? A: No. `verdicts()` walks the ledger's attest rows, so
  neither the name nor the mtime of a verdict file ranks it.
- Q: An arch verdict whose file was edited after attesting keeps only its recorded gate, verdict
  and head, with no Breaking field. Is it the latest? A: No. Only arch verdicts that carry a
  Breaking field (every parsed verdict does) are read; such a record says nothing about Breaking,
  so the last verdict that did decides.

## Requirements

- FR-001: When the PR declares no break, the breaking gap follows the `Breaking:` field of the
  last arch verdict, in ledger order, that carries one.
- FR-002: A `!` title or a `BREAKING CHANGE:` line raises the gap whatever the arch verdicts say.
- FR-003: The runtime stays at or under 3,000 lines; this item adds at most 2 (it adds 1).

## How this fails

1. A stale arch seat at an older head finishes after a re-read at the PR head and says
   `Breaking: no`, clearing a `yes` the newer read found. The gap goes quiet on a real break.
   Bounded: the promise picks ledger order; the arch gate still owes a pass at the head, and a
   stale seat finishing last is rare. A fixture that shows it overturns the assumption below.
2. A verdict whose file was edited after attesting (kept as a FIX record without its Breaking
   line) becomes the latest and reads as "no", dropping a found break. Held: such records are
   skipped, tested by
   `test_an_edited_arch_verdict_that_kept_no_breaking_field_leaves_the_last_one_that_did`.
3. The vendored copy under `.claude/wuwei/` drifts and the evidence that runs keeps the old rule.
   Held by the vendored drift test; re-vendored with `setup.vendor('.')`.

## Assumptions

- Ledger order of attest rows is the order the gates ran. Why: the attest hook records a verdict
  when its seat hands back. Overturned if a fixture shows a re-read attested before the verdict it
  supersedes.
- A verdict matched by its PR reference (not its item) counts as the item's verdict, as it does
  for every other gap today. Why: `verdicts()` already joins both. Overturned if the owner wants
  only the item's own verdicts read for Breaking.

Rollback: revert the commit; `breaking_gaps` again reads any arch verdict ever.

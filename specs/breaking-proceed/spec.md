# Feature Specification: a "Proceed" answer to the breaking: question records the owner's approval

**Feature branch**: `claude/breaking-proceed`
**Item**: breaking-proceed, tier full, goal G-2
**Input**: the owner answered "Proceed" to `breaking: taoq-ai/wuwei#1077 ... Proceed?` and the
ruling row was recorded with `approved: false`. The hook's yes test reads only answers starting
with yes, approve or accept, so the word the breaking: template invites does not count.

## The promise in my words

`hook._answers` decides yes or no with one shared test: the answer, trimmed and lowercased, starts
with one of a few words. Add "proceed" to those words. Then "Proceed" to the breaking: question
(whose template ends "Announced at <link>. Proceed?") records `approved: true`. The rule stays
shared by every question class, as it is today. No other word ("ok", "go") is added, and the
template is not reworded.

The acceptance scenarios, restated:

1. The question `breaking: acme/app#42 at aaaaaaa: drops v1 export. Announced at https://x.test/a.
   Proceed?` answered "Proceed": the PostToolUse hook records a breaking ruling with
   `approved: true`.
2. The same question answered "Do not proceed" or "No": the ruling has `approved: false`.
3. After the change the runtime size test still passes (the line is edited in place, net 0).

## Clarifications

### Session 2026-10-16

- Q: Does "proceed" count only for the breaking: class? A: No. The promise says the rule is
  shared by every class, as today; one tuple on one line.
- Q: Is "Do not proceed" safe? A: Yes. The test is a prefix test, so "do not proceed" starts with
  "do" and stays no.
- Q: Is "proceed." or "Proceed, announced" yes? A: Yes; any answer starting with "proceed".

## Requirements

- FR-001: An answer starting with "proceed" (any case, surrounding space trimmed) is yes.
- FR-002: "No" and "Do not proceed" stay no.
- FR-003: The runtime stays at or under 3,000 lines; this item is net 0.

## How this fails

1. A plan: question answered "Proceed with these changes: ..." now approves the plan instead of
   recording a change request. Bounded: the same is true today for "Yes, but ..."; the owner's
   free text is still recorded in the row.
2. An owner review: or exception: question answered "Proceed" now records approval where the owner
   meant something else. The word is an affirmative in plain English, so this matches intent.
3. The vendored copy under `.claude/wuwei/` drifts from `cli/wuwei/`, and the hook that actually
   runs keeps the old rule. Held by the vendored drift test; re-vendored with `setup.vendor('.')`.

## Assumptions

- "proceed" is a prefix, like the other words, so "proceeding" is also yes. Why: one rule for all
  words. Overturned if the owner wants whole-word matching.

Rollback: revert the commit; the yes tuple returns to yes, approve, accept.

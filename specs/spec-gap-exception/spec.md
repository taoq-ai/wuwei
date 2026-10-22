# Feature Specification: the owner may accept a full-tier spec gap, and a finding row is recorded whole

**Feature branch**: `leone/1223`
**Item**: 1223 (taoq-ai/wuwei#1223), tier full, goal G-2
**Input**: on main at 6828776 the question guard sends back `exception: o/r#n at <sha7>:
specs/<f>/tasks.md has 17 unchecked items. Accept?` as process fit, while `wuwei evidence` marks the
spec engine's gaps `kind='safety'` at full tier and the merge door holds on them. A spec-only PR at
full tier is deadlocked: the door holds, and the owner may not be asked.

## The promise in my words

The question guard lets an `exception:` question through when it names a spec engine gap
(`specs/...`, `openspec/...`, `no spec in the diff`). At full tier those are safety gaps, and
`_common.md` Done lets the owner accept a safety gap. A question that names a template, size or age
gap is still sent back as process fit.

When the owner says yes, the hook records the gap exactly as asked, a gap that holds a sentence break
included. The case is an `analysis.md` finding row such as `| A08 | HIGH | Spec says X. Plan says Y |`.
The merge door then waives that gap at that head, and the ruling and its follow-up item are on the
record. A question that names only the row's first sentence waives nothing.

Out of scope: reading unchecked tasks on a spec-only PR as expected (a scope change for the owner),
and any change to which gaps are safety. Files: `cli/wuwei/guards.py` (the AskUserQuestion branch),
`cli/wuwei/hook.py` (`exception_refs`), their vendored copies, `tests/test_guards.py`,
`tests/test_hook.py`, and the docs that state the question door. Runtime budget +2 lines.

The acceptance scenarios, restated:

1. A full-tier spec-only PR whose tasks.md has 17 unchecked items, every gate passed and an
   approval: the question `exception: o/r#n at <sha7>: specs/<f>/tasks.md has 17 unchecked items.
   Accept?` reaches the owner.
2. The owner answers Yes and the session transcript shows it: the merge door at that head waives the
   spec gap and passes, and the ruling and its follow-up item are on the record.
3. An analysis.md gap whose finding row holds a sentence break: the recorded gap equals the printed
   gap and waives it; a question that names only the first sentence waives nothing.
4. An `exception:` question naming the template's sections, a changed-lines count or an open-days
   age is still sent back as process fit.

## How this fails

1. A long finding row. `wuwei evidence` prints a row cut at 100 characters, so the printed gap may
   end inside a cell, after its last `|`. When that last partial cell holds `. ` or `?`, the hook cuts
   there and records a shorter text. The owner's yes then waives nothing and the merge stays held.
   This fails closed. Of the 702 finding rows in this repository's `specs/*/analysis.md`, 51 hold a
   sentence break inside the printed 100 characters and 2 hold one after the last `|`.
2. A question with a `|` in its own words (`Accept (yes|no)?`). The hook reads the gap up to that
   `|`, so the recorded text holds part of the question and equals no printed gap. The yes waives
   nothing: fails closed.
3. A process fit question that the guard now lets through: a spec gap asked below full tier. There
   `wuwei evidence` hides it as process fit, so the planner never sees it to ask; if asked, the yes
   records a ruling and a follow-up item and waives a gap that never held the merge. Harmless, but
   it costs the owner one question.

## Clarifications

### Session 2026-10-22

- Q: Which gaps still go back as process fit? A: The three the item names: the template's
  sections, a changed-lines count and an open-days age. The guard matches the same words as before;
  only `specs/`, `openspec/` and `no spec in the diff` leave the pattern. Other process fit lines
  (`no Rollback: line`, `not linked to a plan item`, `no reviewer requested`) were never sent back
  by the guard and stay as they are.
- Q: How does the hook find the end of a gap that holds a sentence break? A: The gap runs at least to
  the last `|` after the PR references, then to the first `. ` or `?` after it. A finding row ends in
  `|`, so its sentences stay in the gap. A gap without a `|` is cut as before, at the first `. ` or
  `?`.
- Q: Does the merge door's match change? A: No. `evidence.excepted` still needs the exact printed
  text (case, spacing, end marks and a printed `[waiting]` aside). A first sentence alone, or a text
  that holds part of the question, waives nothing.
- Q: Does the guard's shape check change? A: No. The exception still has to name the PR and head in
  the documented shape, and the gap still has to start with a letter or digit.

## User Scenarios & Testing

### US1: a spec gap at full tier reaches the owner and the yes opens the merge door (P1)

Acceptance 1 and 2: `test_an_exception_for_a_spec_gap_reaches_the_owner` and
`test_an_accepted_spec_gap_opens_the_merge_door_and_is_recorded` in tests/test_guards.py.

### US2: a finding row with a sentence break is recorded whole (P1)

Acceptance 3: `test_an_accepted_finding_row_waives_only_the_whole_row` in tests/test_guards.py and
`test_an_exception_gap_keeps_the_sentence_breaks_of_a_finding_row` in tests/test_hook.py.

### US3: process fit questions are still sent back (P1)

Acceptance 4: `test_an_exception_for_a_process_gap_goes_back_to_the_model` in tests/test_guards.py.

## Requirements

- FR-001: `guards.pre_tool` sends back an `exception:` question only when it names the template's
  sections, a changed-lines count or an open-days age.
- FR-002: `hook.exception_refs` returns the gap up to the first `. ` or `?` after the last `|` of the
  text after the references, or after its start when it holds no `|`.
- FR-003: runtime does not grow past the item's +2 lines; `.claude/wuwei/` matches `cli/wuwei/`.
- FR-004: the route corpus reads the same at main and at the head.

## Assumptions

- Below full tier the planner never sees a spec gap (`evidence.visible` hides process fit), so an
  exception asked there is harmless. Overturned if a seat prints process fit to the planner.
- The last-`|` rule is enough for the rows `wuwei evidence` prints: 49 of the 51 real rows with a
  sentence break in their printed part keep it. Overturned if the owner needs the two others; the
  fix then belongs in how `evidence._rule` cuts a row (at a cell boundary), outside this item.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; a ruling recorded before or
after reads the same.

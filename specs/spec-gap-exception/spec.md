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
`tests/test_hook.py`, and the docs that state the question door. Runtime budget +2 lines, raised
to +6 for fix round 1, which also edits `cli/wuwei/evidence.py` (see Assumptions).

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
   sentence break inside the printed 100 characters and 2 hold one after the last `|`. Fixed in
   round 1 (5 below).
2. A question with a `|` in its own words (`Accept (yes|no)?`). At b6d0635 the hook read every gap
   to that `|`, so `gates missing at head <sha7>: quality. Accept (yes|no)?` recorded a gap that
   waives nothing, where main recorded it right (the quality gate's finding). Round 1: a gap
   without a row reads as on main, and a row reads to its end. Still failing closed: a `|` right
   after the row (`<row> | Accept?`, as on main) and a row with no trailing `|`.
3. A process fit question that the guard now lets through: a spec gap asked below full tier. There
   `wuwei evidence` hides it as process fit, so the planner never sees it to ask; if asked, the yes
   records a ruling and a follow-up item and waives a gap that never held the merge. Harmless, but
   it costs the owner one question.

Fix round 1 (gates at b6d0635): the merge door must waive only the gap the owner saw. Evidence
printed only the first open finding row of an `analysis.md` and only the first checklist with an
unchecked box, so a yes to the printed gap also waived the ones never printed. Each now prints as
its own gap. The hook read every gap to its last `|`, so `Accept (yes|no)?` broke gaps that hold no
row; only a gap that holds a row (`: |`) now reads past its first break, to the row's end.

4. (round 1) A second open row or checklist hidden behind the first. Evidence printed one row and
   one checklist per file or folder, and the gate excepted by the printed text, so a yes to `A1`
   waived an unprinted `A2`. Fixed: each is its own gap; the door holds on `A2` until it is
   accepted by name.
5. (round 1) A row printed cut at 100 characters inside a cell. Fixed: the row is printed to its
   last cell edge within 100 characters, so it ends in `|` and the hook reads it whole. The owner
   sees the row's first cells (its ID among them), not the cut part of its last cell. Two rows
   that would print the same cut (no ID, or the same ID) print whole instead, or one yes would
   waive both.

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
- Q: (round 1) Where does the row end when the question holds its own `|`? A: At the row's last
  `|` that is followed by a `. `, a `?` or the end of the question. Only a gap that holds `: |`
  is read this way; any other gap ends at its first `. ` or `?`, exactly as on main.
- Q: (round 1) Does evidence print every open row and every checklist? A: Yes, each as its own gap,
  in file order. Rows whose cut would be the same print whole; two identical rows are one gap.
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
- FR-002: `hook.exception_refs` returns a gap that holds `: |` up to the first `. ` or `?` after the
  row's end (its last `|` before a `. `, a `?` or the end); any other gap up to its first `. ` or
  `?`, as on main.
- FR-003: runtime does not grow past +6 lines over main (round 1); `.claude/wuwei/` matches
  `cli/wuwei/`.
- FR-004: the route corpus reads the same at main and at the head, also with an approved exception
  for every gap on the PRs the doors read.
- FR-005 (round 1): `evidence._rule` returns one gap per open CRITICAL or HIGH row and one per
  checklist file with an unchecked box.
- FR-006 (round 1): a row longer than 100 characters is printed to its last `|` within the first
  100 characters, or its first 100 characters when no `|` follows the first. Rows whose printed
  text would be the same are printed whole, so one yes never waives two rows.

## Assumptions

- Below full tier the planner never sees a spec gap (`evidence.visible` hides process fit), so an
  exception asked there is harmless. Overturned if a seat prints process fit to the planner.
- (round 1, the planner's) The fix for a masked row or checklist belongs where the gap is printed,
  `cli/wuwei/evidence.py`, an owner path outside the item's first file list: this change made those
  gaps waivable, so it must print each one. Overturned if the owner wants the merge door, not the
  printer, to refuse an exception for a file that holds more than one open row.
- (round 1) A row cut at a cell edge shows the owner its first cells, not the cut part of its last
  cell. Measured on this repository's 717 `specs/*/analysis.md` rows: all 717 read whole at the
  head (665 with main's cut and hook, 715 with b6d0635's). Overturned if owners need the summary
  cell in the question; then print rows whole.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; a ruling recorded before or
after reads the same.

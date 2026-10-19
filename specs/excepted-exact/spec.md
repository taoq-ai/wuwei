# Feature Specification: an owner's exception waives only the gap it names, matched exactly

**Feature branch**: `fix/excepted-exact`
**Item**: excepted-exact, tier full, goal G-2
**Input**: the security gate on #1136 at 353b6f7 showed that `evidence.excepted` matched an accepted
gap to each evidence gap by substring in both directions. An accepted gap `e` waived every gap at
that head, the security gate and the owner review included.

## The promise in my words

`evidence.excepted` drops a gap at a head only when an approved `exception` ruling for that PR and
head names it. "Names" means one of two things, after case, runs of whitespace, trailing end marks
(`. , ; : ! ?`) and a printed ` [waiting]` are set aside:

- the accepted text equals the gap's text; or
- the gap is a gate gap (`gates missing at head <sha7>: <gates>` or `no gate passed at head <sha7>
  (a delta review by <gate>)`) and the accepted text equals the gates it names.

A shorter part of a gap, a longer text that holds the gap, a single letter or an empty gap waives
nothing. The report keeps listing each accepted exception (`- exception: <pr> at <head>: <gap>`), so
the waiver stays on the record. Files: `cli/wuwei/evidence.py`, `tests/test_evidence.py`, the vendored
copy, and the docs that state the rule. Runtime lines grow by 2 (budget 3).

The acceptance scenarios, restated:

1. An approved exception with gap `e` at a head that has a security gap and an owner review gap:
   evidence still shows both.
2. An approved exception whose gap equals the printed gap text: that gap alone is waived; the other
   gaps stay.

## How this fails

1. A planner writes the gap with a newline before the question (`: no test in the diff\nAccept?`).
   The hook records `no test in the diff\nAccept`, which no longer equals the gap, so the owner's
   yes waives nothing and the gap stays. This fails closed. The guard's refusal text already names
   the `<gap>. <question>` shape; the exception-parser follow-up owns the hook's cut.
2. A ruling recorded before this change with a loose gap (a fragment, or extra words) stops waiving
   its gap at an open PR, and the gap shows again. This fails closed too; the owner answers a fresh
   question in the exact shape.
3. A printed gap that holds `. ` or `?` (an `evidence unreadable:` error text, a check name) is cut
   by the hook at that mark, so no question can name it exactly. The gap stays; an owner who needs
   to pass it re-reads the evidence instead. None of the probe's 71 printed gaps holds one; the duty
   `review not requested in <place>: ...` does, and a duty never holds a merge.

## Clarifications

### Session 2026-10-18

- Q: What does "whitespace-normalised" cover? A: Case (`casefold`), runs of spaces, tabs and
  newlines collapsed to one space, leading and trailing whitespace, trailing `. , ; : ! ?`, and a
  printed ` [waiting]` with marks around it. `wuwei evidence` prints a waiting gap with ` [waiting]`,
  and the planner copies that line.
- Q: Does the "names its gate" form stay? A: Yes, as the promise says, but only exactly: the accepted
  text must equal the whole gate list a gate gap names. `security` waives `gates missing at head
  <sha7>: security` and `no gate passed at head <sha7> (a delta review by security)`. It does not waive
  `gates missing at head <sha7>: quality, security`, which still needs quality; `quality, security`
  does. A `(tier raised ...)` suffix is not part of the gate list.
- Q: Are leading marks stripped? A: No. The guard lets an exception gap start only with a letter or
  digit, and the hook strips the spaces and colons before it.
- Q: What does "listed in the report as waived by the ruling" need? A: `report.day` already lists
  every approved exception with its PR, head and gap. A test reads that line after a waiver. The
  promise names no report file, so the line's wording stays.
- Q: Why a set and a `str` check on the ruling's gap? A: A ledger row with a non-string gap (a
  hand-edited ledger) is skipped, never a crash; an empty gap after normalising is dropped, so it
  can never equal the empty gate list of a non-gate gap.

## User Scenarios & Testing

### US1: a short or partial gap waives nothing (P1)

Acceptance 1, plus fragments, superstrings, the owner path alone, a gate that is not missing, marks
alone, an empty, a `None`, a number and a list as the gap.

### US2: the printed gap waives itself alone (P1)

Acceptance 2 with extra spaces, a tab, an end mark and a printed ` [waiting]`; another head waives
nothing; the report lists the exception.

### US3: a gate gap is waived by its exact gate list (P1)

`quality, security` waives the two-gate gap; `security`, `quality`, `arch`, the reordered list, a
longer list and a list without commas do not. A delta gap is waived by its one gate only.

### US4: no generated accepted gap waives a gap it does not name (P1)

For 9,183 generated accepted gaps against 71 printed gaps, a gap is waived exactly when the probe's
own `canon` says the accepted gap names it.

## Requirements

- FR-001: `evidence.excepted` waives a gap only when an approved exception at that PR and head names
  it, as above.
- FR-002: a part or a superstring of a gap, a single character, or an empty gap waives nothing.
- FR-003: the report still lists each approved exception.
- FR-004: runtime grows by at most 3 lines; `.claude/wuwei/` matches `cli/wuwei/`.

## Assumptions

- Exact matching fails closed for gaps a hook records with a trailing line (How this fails 1) and for
  rulings recorded loosely before (How this fails 2). Overturned if the owner wants a first-line
  match before the exception-parser follow-up lands.
- The probe's full list of 26,826 changed pairs (about 4 MB) is not committed; the probe regenerates it
  and prints its sha256. Overturned if a gate needs the file in the tree.
- The report line's wording stays. Overturned if the owner wants it to say "waived".

## Rollback

Revert the commit. No config key, ledger kind or file format changes; rulings already recorded are
read again under the old rule.

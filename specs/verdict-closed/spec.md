# Feature Specification: closed findings go under Probes, and a refused verdict names the next free file

**Feature branch**: `fix/verdict-closed`
**Item**: verdict-closed (issue #1118), tier full, goal G-2
**Input**: Six gates failed their first verdict file on a delta round. Each listed the findings its
fix had closed under `## Findings`, and the strict shape check refused the line. The refusal then
said "Rewrite it in this shape", while the gate charter says never to edit a verdict once written.

## The promise in my words

A gate on a delta round writes the findings that the fix closed under `## Probes`, one line each,
as `closed: <finding> at <sha7>`. `## Findings` holds only the findings still open, or `none`. The
gate charter says so in rule 6 and in the verdict block, and the generated sentinel agents carry it.

When the hook refuses a verdict for its shape, it no longer says "Rewrite it". It says "Write the
corrected verdict to `<stem>-N.md` beside it (the next free number) in this shape". The number is
the first one from 2 up that no file and no symlink in the workspace's verdict folder holds. So a
seat that follows the refusal never edits a counted file, never overwrites another seat's file,
and never meets the symlink refusal. The two refusals that already said "beside it" (a copy-in
over a different verdict, and a verdict that replaced another seat's) use the same free name.

The acceptance scenarios, restated:

1. A delta verdict has `Previous findings at e418c1d: all closed.` under `## Probes` and `none`
   under `## Findings`. The hook lints it and records it as attested.
2. The same line sits under `## Findings` in `quality-abc1234.md`. The hook refuses it, and the
   refusal names `quality-abc1234-2.md` as the file to write next.
3. A reader of `agents/sentinel-quality.md` at the head finds that closed findings go under Probes.

## How this fails

1. The refusal names a file the seat cannot write. If `-2` is already a file, a later write there
   is refused as "already holds another verdict". If `-2` is a symlink, the copy-in refuses it as
   a link. The free name skips every name the folder lists, dangling links included, because
   `iterdir` lists the link itself. Tested for the -2, -3 sequence, a dangling and a live link at
   -2, and end to end: the named file is written and attested.
2. A verdict already at `-2` is refused and the hook names `-2-2`. The stem drops a trailing
   `-<digits>` that follows seven hex characters, so the base is `<gate>-<sha7>` and the next
   name is `-3`. A head of seven digits (`quality-1234567`) keeps its sha: the strip needs hex
   before the dash, and the gate name before the sha is not hex.
3. A gate that reads the new charter puts open findings under Probes too, and a blocking finding
   escapes the merge check. Rule 6 says Probes holds closed findings and Findings holds all open
   ones, and the shape check stays strict: a line under Findings is still a finding or `none`.
4. Two seats refused at the same moment are told the same free number. The first to write it
   wins; the second meets the copy-in refusal, which names the next free number. No write is
   lost, and the count of seats on one head is small.

## Clarifications

### Session 2026-10-18

- Q: Is "next free" counted in the workspace folder or the seat's worktree folder? A: The
  workspace folder (`<root>/.wuwei/verdicts/<item>/`), where WUWEI counts the bytes and where the
  copy-in refuses a held name or a link. A seat's worktree folder is its own, and the copy-in reads
  the workspace folder only.
- Q: Does a symlink at `-2` count as taken? A: Yes, live or dangling. A seat cannot write through
  it: the copy-in refuses any link on the path (verdict-symlink, #1137).
- Q: Do the other two "beside it" refusals change? A: Yes, to the same free name, at no line cost.
  Both already named `<stem>-2.md` without checking it was free, and the copy-in one named
  `-2-2.md` for a verdict already at `-2`. Recorded under Assumptions.
- Q: Does the shape check loosen? A: No. `verdict.FINDING` and `parse` are unchanged. The FORMAT
  text the refusal prints says where closed findings go, so a refused gate reads it there too.
- Q: Does the charter keep its word ceiling? A: Yes. `agents/sentinel-arch.md` is at 2,250 words,
  the ceiling (`AGENT_WORDS` in `tests/test_charters.py`); the verdict paragraph was tightened to
  pay for the new sentence.

## User Scenarios & Testing

### US1: a delta verdict with closures under Probes is attested (P1)

Acceptance 1. `test_a_delta_verdict_with_its_closed_findings_under_probes_is_attested`. This held
on main too: the parser never read Probes. The test pins it.

### US2: closures under Findings are refused with the next free file (P1)

Acceptance 2. `test_closed_findings_under_findings_name_the_next_free_file_to_write`, and the
generated cases in `test_a_shape_refusal_names_a_number_no_file_or_link_holds` (first, taken,
from -2, two taken, dangling link, live link, digit sha, from -12, flat path, no sha).

### US3: the named file can be written (P1)

`test_the_next_free_file_a_refusal_names_can_be_written_and_attested`: a dangling link at -2, the
refusal names -3, the seat writes -3 in its worktree, and the hand-back attests it.

### US4: the other refusals name a free file (P2)

`test_the_other_refusals_that_say_write_beside_it_name_the_next_free_file_too`.

### US5: the charter says closures go under Probes (P1)

Acceptance 3. `test_a_gate_puts_the_findings_its_fix_closed_under_probes` reads `charters/_gate.md`
and the generated `agents/sentinel-quality.md`.

## Requirements

- FR-001: `charters/_gate.md` rule 6 says closed findings go under `## Probes`
  (`closed: <finding> at <sha7>`) and `## Findings` holds only open findings, or none.
- FR-002: The verdict block in `charters/_gate.md` says the same in its Findings and Probes lines.
- FR-003: The shape refusal ends "Write the corrected verdict to `<free>` beside it (the next free
  number) in this shape", where `<free>` is the first `<base>-N.md` (N from 2) the workspace
  folder does not list.
- FR-004: The copy-in and replaced-verdict refusals name the same free file.
- FR-005: `bin/wuwei agents build` and `setup.vendor('.')` leave no drift.
- FR-006: Runtime lines grow by at most 1 (the item's budget).

## Assumptions

- Probes is where gates already put run evidence, so closed findings fit there (from the item).
  Overturned if the goal gate says closures must be machine-read.
- The other two "beside it" refusals take the same free name. The lead's brief asks that a refusal
  naming the next free file never name a path a seat cannot write; both refusals fell short of it.
  Overturned if the owner wants the shape refusal alone changed; the revert is two expressions.
- The FORMAT note in `verdict.py` is part of the refusal text, not a loosening of the shape check.
  Overturned if the goal gate reads it as outside the promise.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger kind or file format changes.

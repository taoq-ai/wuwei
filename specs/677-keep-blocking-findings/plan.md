# Implementation Plan: receive keeps every blocking finding

**Branch**: `677-keep-blocking-findings` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One parser and one lint are shared by every verdict reader. Widen the parser's id pattern
once (a module constant used at the two places that hardcode `F`), add one FIX rule to
`verdict.lint` beside the existing PASS rule, and sort the received blocks blocking first in
`dispatch.receive`. `receive` needs no new refusal: it already refuses on any lint failure.

## Technical Context

Python 3.11+ stdlib only, pytest dev-only. No new module, function, event kind, state key or
config key.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: the new failure is a lint finding (exit 1); `receive` turns it into `Refused`
  (exit 1) as today.
- III one behaviour one function: the id pattern lives in `verdict.FINDING_ID`, the FIX rule
  in `verdict.lint`. `receive`, the write guard, seat stop, the PR guard and obligations all
  reach it through `lint` or `lint_file`; none re-implements it.
- IV test first: tasks.md orders each test before its code.
- V simplicity: no id field, no per-role parser, no new refusal path in `receive`.
- VII security: a blocking finding can no longer be recorded as non-blocking, so a delta
  cannot raise past it.
- Workflow: the changed guard rule adds an invariant row to design 9.2 and its check to
  `tests/test_invariants.py`.

## Design

### cli/wuwei/verdict.py

Below `SEVERITY` (line 17):

```python
FINDING_ID = r'\[?(?:[FQSAGN]\d+|Finding\s+\d+)\]?(?:[\s(:.]|$)'  # #677: any role's ids
```

`finding_blocks` (line 56): line 62 becomes
`re.match(r'^\s*(?:\d+[.)]\s+|' + FINDING_ID + ')', line, re.I)` and line 71 becomes
`re.match(r'^\s*(?:#|\d+[.)]\s+|' + FINDING_ID + ')', current[0], re.I)`. Nothing else in
the function changes.

`lint` (line 87), right after the PASS rule at lines 122-124:

```python
if verdict == 'FIX' and not any(re.search(BLOCKS_YES, block, re.I) for block in blocks):
    lines = [line.strip() for line in text.splitlines() if re.search(BLOCKS_YES, line, re.I)]
    failures.append('FIX verdict but no blocking finding parsed; the lines that look like '
                    f'findings are: {"; ".join(lines) or "none"} (start each finding with its '
                    'severity, a number or an id such as Q1 or Finding 1; write Verdict: PASS '
                    'when none blocks)')
```

`text` there is already the active text (line 90), so fenced examples and comments are not
named. The order of the existing failures does not change (`test_source_refusal_order`).

### cli/wuwei/dispatch.py

`receive`, line 681:

```python
blocks = sorted(verdict.finding_blocks(text),
                key=lambda block: not re.search(verdict.BLOCKS_YES, block, re.I))
```

`sorted` is stable, so file order holds within each group. Lines 682-686 stay as they are and
now produce `findings` blocking first. The lint call at line 632 (and line 670 after the
scanner merge) already raises `Refused` / `OSError` with the lint message, which carries the
new failure; no change there.

### docs/site/reference.md

"Gate verdict layout", lint rules (lines 365-366): add "A FIX verdict needs at least one
`blocks: yes` finding; a verdict whose findings are all `blocks: no` is a PASS." and change
"a numbered or `F1` line" to "a numbered line or an id line (`F1`, `Q1`, `S1`, `A1`, `G1`,
`N1`, `Finding 1`, optionally in brackets)".

### docs/specs/2026-09-24-wuwei-design.md 9.2 and tests/test_invariants.py

Row (next free id after I35 on `main` at build time; I36 today): "A FIX verdict is accepted
only with a parsed blocking finding, whatever id form starts it | `verdict.lint` and
`verdict.finding_blocks` on a FIX verdict for each id form (`F1.`, `Q1.`, `S1.`, `A1.`,
`G1.`, `N1.`, `Finding 1.`, `[Q1]`, `1.`, severity first) with `blocks: yes` (accepted, one
blocking block) and with `blocks: no` (refused naming the FIX rule) | #677; one parser in
`verdict.finding_blocks`, one rule in `verdict.lint`".

`tests/test_invariants.py`: a function `i36(case, rules)` in the style of `i34` (pure, memoised
with `rules.memo(('fix needs a blocker',), compute)`), registered in `INVARIANTS` and in
`READS` with `()`.

### Must not change

- `BLOCKS`, `BLOCKS_YES`, `SEVERITY`, `CITATION` and the `start`, `explicit` and `row` rules
  of `finding_blocks`.
- PASS, PARK and ESCALATE lint behaviour; light depth gets the same FIX rule and nothing else.
- `next_step`, `_fix_feedback`, `_delta_feedback`, the round cap (#623) and the record keys
  (`blocks`, `notes`, `findings`).
- `cli/wuwei/guards/pr.py` (its delta-FIX branch is left as is, see spec Assumptions),
  `cli/wuwei/commands/why.py`, `cli/wuwei/tracker.py`: they read `finding_blocks` and gain the
  new ids without a change.
- Charters and agents: no charter text changes.

## Existing tests that encode the old rule

A probe of this design on a scratch copy of `main` fails exactly these, all because they
record or lint a FIX whose findings are all `blocks: no`. Each keeps its intent with the
verdict word fixed, never a weakened assertion:

| Test | Change |
|---|---|
| `tests/test_verdict.py::test_source_accepted_verdict_forms` | keep `blocks: yes` for FIX (replace with `blocks: no` only for PASS, PARK, ESCALATE) |
| `tests/test_verdict.py::test_assumption_is_a_finding_kind` | `ASSUMED` lint expectation: a FIX with only an assumption is refused with the FIX rule; a PASS with it is `OK: PASS` |
| `tests/test_dispatch.py::test_delta_nonblocking_residual_becomes_review_note` | the delta residual is `Verdict: PASS` with the `blocks: no` finding |
| `tests/test_dispatch.py::test_issue_acceptance_document_item_ships_its_notes_after_two_rounds` | the third verdict (`note`) is `Verdict: PASS` |
| `tests/test_pr_guards.py::test_pr_gate_accepts_nonblocking_delta_residual` | the delta file and its record are PASS with the `blocks: no` finding |

Any other failure the full suite shows is read before changing it.

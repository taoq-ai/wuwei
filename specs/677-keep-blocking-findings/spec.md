# Feature Specification: receive keeps every blocking finding

**Feature Branch**: `677-keep-blocking-findings`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #677 (owner, 2026-10-10, item 45): "receive dropped the quality
gate's blocking findings. The verdict said FIX with Q1 and Q2 blocking, but the parsed result
listed only the assumption notes and `blocks: false`." Deliver: the finding parser accepts any
role prefix (`F`, `Q`, `S`, `A`, `G` followed by digits) and the bare `Finding <n>` form;
`receive` refuses a FIX verdict that parses no `blocks: yes` finding, naming the lines that
look like findings; the parsed result lists blocking findings first with their ids; a test
per sentinel role.

## Root cause

Reproduced read-only on `main` against the owner's real quality verdict of 2026-10-10 (a
FIX with two blocking findings written `Q1. Severity: medium. File: <path>:80 ... blocks:
yes.`, four non-blocking findings `N1.` to `N4.` and six `Assumption:` findings), by calling
`verdict.lint` and `verdict.finding_blocks` on its active text:

| Call | Result today |
|---|---|
| `verdict.lint(text, quality=True)` | `(0, 'OK: FIX')` |
| `verdict.finding_blocks(text)` | six blocks, all `Assumption:` lines, none `blocks: yes` |
| `receive` record (dispatch.py:681-686) | `blocks: false`, `notes` and `findings` = the six assumptions |

The `Q1.` and `Q2.` lines both carry `blocks: yes` and are dropped, and so are `N1.` to
`N4.`.

In the code:

- `cli/wuwei/verdict.py:62`: a numbered line starts a finding only when it matches
  `\d+[.)]\s+` or `\[?F\d+\]?(?:[\s(:.]|$)`. Only the `F` prefix is accepted, so `Q1.` is not
  a start. Line 59 (`start`) needs the severity first, line 61 (`explicit`) needs a line
  starting `Severity:` or `Assumption:`, and line 65 (`row`) needs a bullet or table row, so
  nothing else catches it. Lines before the first start are skipped (line 76) and a `#`
  heading closes the open block (line 77), so every line of Q1 and Q2 is lost.
- `cli/wuwei/verdict.py:71`: `heading_only` repeats the same `F`-only pattern.
- `cli/wuwei/verdict.py:121-126`: `lint` refuses a PASS that carries a blocking finding and a
  non-PASS with no finding at all, but a FIX whose parsed findings are all `blocks: no`
  passes. The six assumption blocks satisfy "at least one finding", so the lint said OK.
- `cli/wuwei/dispatch.py:681-686` (`receive`): records `blocks`, `notes` and `findings` from
  `finding_blocks` as parsed, so the record says `blocks: false`. At round one `next_step`
  still opens a fix round for any FIX (dispatch.py:361), but the builder is told to fix only
  the `blocks: yes` findings (`_fix_feedback`, dispatch.py:591) and the record has none. At a
  delta the same loss makes `next_step` return `raise` (dispatch.py:367 and 380-381): the item
  would ship with its blocking findings open.

The issue names `cli/wuwei/commands/dispatch.py` (`receive`); that is the CLI wrapper. The
function is `dispatch.receive` in `cli/wuwei/dispatch.py:600`.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which id prefixes start a finding? A: `F`, `Q`, `S`, `A`, `G` and `N` followed by
  digits, optionally in brackets, and `Finding <n>`, each followed by whitespace, `(`, `:`,
  `.` or the end of the line (the trailing rule `F` has today). `N` is added because the
  reproduced verdict numbers its non-blocking findings `N1` to `N4`; without it they are lost
  from the notes that #623 ships in the PR body.
- Q: Where does the FIX cross-check live? A: In `verdict.lint`, the one function every
  verdict check routes through. `receive` calls it through `lint_file` (and again after the
  security scanner merge), the write guard and the seat stop call it before the seat stops,
  and the PR guard and obligations re-lint recorded files. `receive` then refuses with the
  lint message, as it does for every lint failure today, and the seat already saw the same
  message at write time.
- Q: Which lines does the refusal name? A: Every line of the active text that matches the
  shared `BLOCKS_YES` pattern (`blocks: yes` or a `| yes |` cell), stripped and
  joined with `; `, or `none`. Lines are not shortened: a cut can drop the `blocks: yes` the
  reviewer has to find. When a FIX has no parsed blocking finding, every
  such line is by definition outside a parsed finding.
- Q: Does the rule hold at a delta? A: Yes. A delta whose findings are all `blocks: no` is
  written `Verdict: PASS` (PASS already allows non-blocking findings, and `next_step` collects
  notes from every result). The outcome is the same as today: `raise` with the notes. This
  matches the design's merge precondition "every pre-PR gate verdict is PASS for this head".
- Q: "Blocking findings first with their ids"? A: `receive` orders `findings` blocking first,
  file order otherwise. Each block's text starts with its own first line, which carries the
  id (`Q1. ...`), so no separate id field is added.
- Q: "A test per sentinel role uses its charter's example"? A: The charters
  (`charters/sentinel-*.md`) carry no finding example. Each role's test uses the role's
  prefix (arch `A`, quality `Q`, security `S`, goal `G`) in the common verdict shape, plus
  `F`, `N` and `Finding 1`.

## User Scenarios and Testing

### User Story 1 - Role-prefixed blocking findings are recorded as blocking (Priority: P1)

A planner or builder reads the received record and sees the gate's real blocking findings.

**Acceptance Scenarios**:

1. **Given** a quality FIX verdict with `Q1.` and `Q2.` findings marked `blocks: yes`, a
   `## Non-blocking findings` heading with an `N1.` finding marked `blocks: no`, and an
   `Assumption:` finding, **When** `dispatch receive` records it, **Then** the record has
   `blocks: true`, its `findings` start with the Q1 block then the Q2 block, both containing
   `blocks: yes`, and its `notes` hold the N1 and assumption blocks.
2. **Given** the same verdict shape with each prefix `F`, `Q`, `S`, `A`, `G`, `N` and the
   form `Finding 1`, **When** `verdict.finding_blocks` parses it, **Then** each id line starts
   its own block, and `lint_file` accepts it for the matching sentinel role.

### User Story 2 - A FIX with no parsed blocking finding is refused (Priority: P1)

The reviewer fixes the format instead of the record losing the findings.

**Acceptance Scenarios**:

1. **Given** a FIX verdict whose blocking finding is written in a form the parser does not
   start a finding on (a heading `### Q1 high` followed by a prose line ending
   `blocks: yes`) and whose only parsed finding is a `blocks: no` assumption, **When**
   `dispatch receive` runs, **Then** it refuses with `FIX verdict but no blocking finding
   parsed; the lines that look like findings are: ` followed by that prose line, and no gate
   verdict is recorded.
2. **Given** a FIX verdict whose findings are all `blocks: no` and no line says
   `blocks: yes`, **When** it is linted, **Then** the same failure names `none` and says to
   write `Verdict: PASS` when no finding blocks.
3. **Given** the same text written to `decisions/gate-<name>.md` by a seat, **Then** the write
   guard refuses it with the same message (it calls the same lint).

### Edge Cases

- PASS, PARK and ESCALATE verdicts are unchanged by the new rule.
- A FIX with no finding at all keeps today's "no finding with severity" failure and also gets
  the new one.
- A delta FIX that carried only `blocks: no` residuals is now refused; the seat writes PASS
  and the item raises with the same notes.
- A continuation line inside a finding that starts with an id-like token (`S12 calls ...`)
  now starts a new block. That block lacks a severity or citation, so the lint refuses the
  verdict ("finding n: missing ..."); nothing is silently dropped.
- Table rows (`| Q1 | P1 | ... | yes |`), bullets and severity-first lines parse as today.

## Requirements

- **FR-001**: `verdict.finding_blocks` starts a finding on a line beginning with an id
  (`F`, `Q`, `S`, `A`, `G` or `N` plus digits, optionally bracketed, or `Finding <n>`)
  followed by whitespace, `(`, `:`, `.` or end of line, through one shared module pattern
  used at both places that hardcode `F` today (verdict.py:62 and :71).
- **FR-002**: `verdict.lint` fails a `FIX` verdict whose parsed findings carry no
  `blocks: yes` with one failure line: `FIX verdict but no blocking finding parsed; the lines
  that look like findings are: <lines or none>`, followed by a short hint to start each
  finding with its severity, a number or an id, or to write `Verdict: PASS` when none blocks.
- **FR-003**: `dispatch.receive` builds `findings`, `notes` and `blocks` from the blocks
  ordered blocking first, file order otherwise.
- **FR-004**: `docs/site/reference.md` (Gate verdict layout, lint rules) names the id forms
  and the FIX rule.
- **FR-005**: An invariant row in design 9.2 (the next free id; I36 on `main` today) and its
  `tests/test_invariants.py` check: a FIX verdict is accepted only with a parsed blocking
  finding, for each id form (constitution, Workflow: a changed guard rule adds its
  invariant).

## Success Criteria

- **SC-001**: The reproduced verdict shape is recorded with `blocks: true` and Q1, Q2 first.
- **SC-002**: No FIX verdict is recorded with `blocks: false`.

## Assumptions

- The cross-check is in `verdict.lint`, not only in `receive` as the issue words it: every
  caller routes through lint, and the seat learns at write time. Overturn if the owner wants
  the write guard to accept such a FIX.
- `N` is added to the issue's prefix list on the evidence of the reproduced verdict.
- #623 recorded "a FIX at round one still opens a round even when all its findings are
  `blocks: no`". That verdict can no longer be recorded; the issue asks for exactly this.
- `cli/wuwei/guards/pr.py:106-108` (a delta FIX with `blocks` false counts as complete)
  becomes unreachable for records received after this change. It stays: removing it changes
  the merge guard, which this issue does not ask for.
- Ids keep the trailing rule `F` has today (whitespace allowed after the id). A false split
  is loud (a lint refusal), so no stricter rule is added.
- Tests use neutral synthetic verdict text in the reproduced shape; no text from the owner's
  workspace is copied into the repository.

## Deferred

- An "orphan `blocks: yes` line" check for a PASS, or for a FIX where one blocking finding
  parses and another is lost. The delta catches the second case (once the parsed one closes,
  the lost one leaves a FIX with no parsed blocking finding). Add it if a verdict shows the
  first.
- Deleting the unreachable delta FIX branch in `cli/wuwei/guards/pr.py:106-108`.

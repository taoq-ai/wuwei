# Feature Specification: one verdict format for the lint and the charters

**Feature Branch**: `665-verdict-format`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #665 (owner, 2026-10-10, item 22): "several gates had their verdicts
rejected one to three times: a numbered list was read as findings, and the charter and the
lint disagree on the `CLASS:` line format. Each rejection costs a rewrite." Deliver: one
format table in `cli/wuwei/verdict.py` that the charters render from (`bin/wuwei agents
build` fails when a charter's verdict section differs from it); findings are recognised only
under a `Findings` heading or with the `F<n>` prefix, never by a bare numbered list
elsewhere; the lint's message quotes the offending line and the accepted form; a test runs
every charter's verdict example through the lint.

## Root cause

Reproduced read-only on `main` (1f1b07c) by calling `verdict.lint` in-process on neutral
verdict text (no orchestrator notes exist for this issue, so no dry-run workspace was named;
see Assumptions):

| Verdict text | `lint(text, class_sweep=True)` today |
|---|---|
| PASS with `Evidence:` then `1. ran the suite` and `2. read the diff` | exit 1: `finding 1: missing severity`, `missing file:line`, `missing blocks yes/no`, `missing failure scenario`, and the same for finding 2 |
| FIX with `## Findings` / `1. P1 cli/x.py:12 ... blocks: yes`, then `## Evidence` / `1. ran pytest` / `2. read cli/x.py` | exit 1: findings 2 and 3 (the two evidence lines) each miss all four fields |
| PASS with the class line written as `_common.md` shows it: `CLASS: PASS` | exit 1: `no class-sweep line (CLASS: PASS\|N.A.\|FINDING <id>)` |

In the code:

1. `cli/wuwei/verdict.py:63` (`numbered` in `finding_blocks`) starts a finding on any line
   that begins with `\d+[.)]`, wherever it is. A numbered list under `Evidence` or in prose
   becomes findings, each refused for missing fields. `dispatch.receive`
   (`cli/wuwei/dispatch.py:695-697`) reads the same blocks, so a verdict that passes with
   such a list would also record its lines as review notes.
2. `cli/wuwei/verdict.py:16` (`CLASSES`) accepts only a named class (`AUTH`, `VAL`, ...).
   `charters/_common.md:24` tells every sentinel to write `CLASS: PASS|N.A.|FINDING <id>`,
   and the lint's own refusal at `cli/wuwei/verdict.py:111-112` repeats that literal. A seat
   that copies it is refused with a message that shows the very line it wrote as the fix.
3. `cli/wuwei/commands/agents.py:39-60` (`render`) concatenates the charters with no check
   against the lint, so the two drift without a test noticing. No charter carries a verdict
   example; only `docs/site/reference.md` does (linted by `tests/test_docs.py`).
4. The per-finding refusals (`cli/wuwei/verdict.py:134-139`) say `finding 2: missing
   severity` without quoting the line the lint took as finding 2, so the seat cannot see
   that a numbered evidence line was read as one.

## User Scenarios & Testing

### User Story 1 - A numbered list in prose is not a finding (Priority: P1)

A sentinel writes an `Evidence` section as a numbered list. The lint reads no finding there,
and `receive` records none.

**Why this priority**: the most frequent cause of the rejections the owner counted.

**Independent Test**: lint a PASS and a FIX verdict that carry a numbered list under an
`Evidence` heading.

**Acceptance Scenarios**:

1. **Given** a numbered list under `Evidence`, **When** the verdict is linted, **Then** no
   finding is read (`finding_blocks` returns nothing from that list) and a PASS is accepted.
2. **Given** a FIX with `F1` carrying `blocks: yes` and a numbered list under `## Evidence`,
   **When** linted, **Then** it is accepted with exactly one finding.
3. **Given** a bare numbered list under a `Findings` heading, **When** linted, **Then** each
   numbered line is a finding and is checked for its four fields.
4. **Given** a numbered line whose text starts with a severity, `Severity:` or a finding id
   (`1. P1 ...`, `1. Severity: medium ...`, `1. F1 ...`), or that carries `blocks: yes|no`,
   **When** linted outside a `Findings` heading, **Then** it is still a finding (the I39 and
   #677 forms keep working, and a PASS still cannot carry a numbered `blocks: yes` line).

### User Story 2 - The charter shows the format the lint accepts (Priority: P1)

The verdict format lives in one table in `cli/wuwei/verdict.py`. `bin/wuwei agents build`
renders it as a `## Verdict format` section, with an example verdict, into every sentinel
agent. No charter source holds its own copy; build and `agents check` fail when one does, and
`agents check` reports drift when the table changes and the agents were not rebuilt.

**Why this priority**: the `CLASS:` disagreement is the second cause of rejections, and
without one home the two drift again.

**Independent Test**: lint the example from each generated sentinel agent with that role;
add a `## Verdict format` section to a charter in a plugin copy and run `agents.build` on it.

**Acceptance Scenarios**:

1. **Given** a `CLASS:` line written as the charter shows (the example line
   `VAL: FINDING F1`, or `VAL: PASS` per the class row), **When** linted with
   `class_sweep=True`, **Then** the lint accepts it.
2. **Given** the verdict example in each sentinel agent (`sentinel-arch`,
   `sentinel-quality`, `sentinel-security`, `sentinel-goal`), **When** it is linted with that
   role, **Then** it returns `OK: FIX`.
3. **Given** a charter source that carries its own `## Verdict format` section (a copy that
   can differ from the table), **When** `agents build` or `agents check` runs, **Then** it
   exits 2 naming the role and the Verdict format, and writes no agent file.
4. **Given** `FORMAT` changed and the agents not rebuilt, **When** `agents check` runs,
   **Then** it reports drift in the sentinel agents (exit 1).

### User Story 3 - A rejection names the line and the fix (Priority: P2)

**Why this priority**: each rejection costs a rewrite; quoting the line makes it one edit.

**Independent Test**: lint verdicts with one fault each and read the message.

**Acceptance Scenarios**:

1. **Given** a finding missing a field, **When** rejected, **Then** the message quotes that
   finding's first line and the accepted finding form from the table.
2. **Given** `CLASS: PASS`, **When** rejected for the class sweep, **Then** the message
   quotes `CLASS: PASS` and the accepted class form, which names real classes (`VAL: PASS`),
   never the bare literal `CLASS:`.
3. **Given** a bad `Head:` row, a second `Verdict:` line or a PASS carrying a `blocks: yes`
   finding, **When** rejected, **Then** the message quotes the offending line and the
   accepted form.

### Edge Cases

- A finding written as a Markdown heading (`### P1: empty input`) still starts a finding and
  does not open or close a `Findings` section.
- A label line that names a finding field (`File:`, `Location:`, `Scenario:`, `Severity:`,
  `blocks:`, `Probe:`, `Mutation:`) with its value on the next line stays inside the
  finding; it is not a section heading.
- A section heading after a finding closes that finding, so evidence below it cannot supply
  a missing field to the finding above (`test_findings_cannot_borrow_evidence`).
- Fenced blocks, quoted lines and comments stay ignored, so the example in a charter or a
  verdict never counts as evidence.
- Light depth: the class line stays optional; nothing else in the light shape changes.
- A workspace charter override (`.wuwei/charters/<name>.md`) goes through the same `render`,
  so it gets the rendered section in its sentinel agents and is refused the same way if it
  carries its own copy.
- Non-sentinel agents (planner, lead, builder, shepherd, steward) do not get the section;
  they write no verdict.

## Requirements

### Functional Requirements

- **FR-001**: `verdict.finding_blocks` MUST start a finding on a numbered line only under a
  `Findings` heading, when the number is followed by a severity, `Severity:` or a finding
  id, or when the line carries `blocks: yes|no`. Every other start rule (finding id, severity, `Severity:`, `Assumption:`, bullet or
  table row with evidence) is unchanged.
- **FR-002**: A section heading (a Markdown heading that does not itself start a finding, or
  a line holding only a label and a colon that is not a finding field) MUST close the open
  finding block and set whether the lines below it are under `Findings`.
- **FR-003**: `cli/wuwei/verdict.py` MUST hold one format table (`FORMAT`) giving, per
  verdict line, the accepted form and an example line; the class names in it and in the
  `CLASSES` pattern MUST come from one tuple.
- **FR-004**: `verdict.section()` MUST render the table and its example verdict as the
  `## Verdict format` Markdown section, and `agents.render` MUST put it into every
  `sentinel-*` agent, right after the common charter. `charters/_common.md` item 8 MUST NOT
  show the literal `CLASS:` form.
- **FR-005**: `agents.render` MUST raise `ValueError` (exit 2 in `build` and `check`) when a
  charter it reads carries its own `## Verdict format` section, before any write.
- **FR-006**: The lint's class-sweep, per-finding, `Head:`, duplicate `Verdict:` and
  PASS-with-blocking refusals MUST quote the offending line (when there is one) and the
  accepted form from `FORMAT`. Every existing refusal keeps its leading words, and
  `REJECT: send back to the seat` stays last.
- **FR-007**: A test MUST lint the example in every generated sentinel agent with that role.
- **FR-008**: The changed guard rule adds an invariant row to design 9.2 and its check to
  `tests/test_invariants.py`; I39 keeps passing unchanged.

### Key Entities

- **Verdict format table** (`verdict.FORMAT`): ordered map from a verdict line name
  (`Verdict`, `Head`, `Finding`, `Probe`, `Class`, `Simplicity`, `Design`, `Blocked`, `Gap`,
  `Change`) to `(accepted form, example line)`.

## Success Criteria

- **SC-001**: The three reproduced texts in Root cause give: PASS accepted, FIX accepted with
  one finding, and a `CLASS: PASS` refusal whose message names a real class form.
- **SC-002**: `agents check` on the repository passes; it exits 2 when a charter carries its
  own verdict section and 1 when the table changed without a rebuild.
- **SC-003**: Every sentinel role accepts its charter's example verdict.
- **SC-004**: The full suite passes with no weakened assertion.

## Assumptions

- The orchestrator notes for this issue do not exist, so no dry-run workspace was named. The
  failure was reproduced in-process on neutral synthetic text in the shapes the issue names.
  Overturn: a real rejected verdict that this design still refuses.
- "Only under a `Findings` heading or with the `F<n>` prefix" is read as applying to numbered
  lines. Bullets and table rows with evidence, severity-led lines, `Severity:` and
  `Assumption:` lines and every role id (`F`, `Q`, `S`, `A`, `G`, `N`, `Finding <n>`, #677)
  keep starting findings anywhere: dropping them would lose blocking findings (#677, #712),
  break I39 and break the documented example. A numbered line led by a severity, `Severity:`
  or an id also stays a finding, because I39 and existing tests write findings that way; so
  does a numbered line carrying `blocks: yes|no`, so a PASS cannot hide a blocking finding
  in a numbered list.
  Overturn: the owner wants a heading mandatory for every finding form.
- An evidence bullet with a `file:line` (`- cli/x.py:12 shows ...`) still reads as a finding
  (the rule that catches a finding whose severity was dropped). It is out of scope; the
  rejection now quotes the line, so the seat sees why.
- The literal `CLASS: PASS` stays refused: it names no class, so accepting it would let a
  class sweep pass without saying what was checked. The fix is on the charter side (show a
  real class) and in the message.
- "The charters render from" the table is implemented by rendering it into the generated
  sentinel agents at `agents build`, not by keeping a copy in `charters/_common.md`.
  `tests/test_process_depth.py::test_charters_follow_the_depth_line` pins `_common.md` plus
  `builder.md` at 65 lines (owner, #567: deletion over addition), and they are at 65 today;
  a copied section adds about 30. A probe of the copy design failed exactly that test.
  Rendering also removes drift by construction. "Build fails when a charter's verdict section
  differs" then means: build fails when any charter carries its own `## Verdict format`
  section, the only way a charter-side copy can exist to differ, and `agents check` already
  reports the agents as drifted when the table changes without a rebuild. Overturn: the
  owner raises the 65-line pin and wants the section in the charter source.
- One example verdict (a quality FIX with one finding) serves all four sentinels: the lint
  ignores rows a role does not need, and the table marks the quality-only and class rows.
- `charters/builder.md:20` keeps its `CLASS: PASS|N.A.|FINDING <id>` report line: it is the
  builder's handoff report, which the verdict lint never reads, and the per-class lines below
  it show the real names. Overturn: a builder report rejected for that form.
- `docs/site/reference.md` is updated by hand (its numbered-line rule), not rendered from the
  table; `tests/test_docs.py` already lints its example.

## Deferred

- none

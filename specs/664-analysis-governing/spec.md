# Feature Specification: the analysis step checks each assumption against the governing document the item names

**Feature Branch**: `664-analysis-governing`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #664 (owner, 2026-10-10, item 21): a spec-kit analysis checked the
spec only against itself, so a conflict with the item's pre-registration section reached
the gates. Deliver: when the item record or spec names a governing document (`governed_by:`
path or section in the plan item, or the `Governing:` line in the spec), the analyze step's
prompt includes that section's text and requires a row per assumption with `agrees`,
`conflicts` or `not covered` and the cited line; `wuwei spec analysis` refuses a report that
lacks the table when a governing document is named; the goal sentinel reads the same table.

## Root cause

Reproduced in-process on `main` with the spec-kit fixture (`tests/fixtures/spec/speckit`)
copied to a scratch worktree holding `docs/prereg.md` with a `## Pre-registration`
section, and the item row `{'governed_by': 'docs/prereg.md#Pre-registration'}`:

```text
builder: Spec: speckit strict; artifacts in specs/001-a; ... analyze (/speckit.analyze, then save its report with bin/wuwei spec analysis a < report (a subagent cannot write analysis.md)) -> analysis.md; ...
gate: Spec: speckit artifacts: specs/001-a
analyze status on a report with no governing table: None
```

WUWEI has no notion of a governing document anywhere in the spec path:

- `cli/wuwei/specmode.py:311` `brief_line` builds the builder's `Spec:` line from `STEPS`
  (line 28, the analyze row) and the gate's `Spec: <engine> artifacts:` line; neither reads
  the item row beyond `skip`, so nothing from the governing document reaches the seat that
  runs `/speckit.analyze`, and the goal sentinel is not told one exists.
- `cli/wuwei/commands/spec.py:25` `write` (`wuwei spec analysis`, #614) refuses only an
  unknown item, a missing worktree, a missing or doubled spec directory, a missing
  `spec.md`, a symlink and an empty report (lines 31 to 52); any other report is saved at
  line 53 whatever it says about the governing text.
- `cli/wuwei/plan.py:386` (`approve`) and `cli/wuwei/plan.py:489` (`add`) copy only `tier`
  from a candidate into the item, and `_proposal` (lines 37 to 105) does not know a
  `governed_by` field, so the lead has no way to put one on the plan item.
- `charters/builder.md:10` says "Read the governing requirement" but nothing asks the seat
  to hand it to the analysis; `charters/sentinel-goal.md:10` traces the governing
  requirement but has no table to read.

So the analyze step compares `spec.md`, `plan.md` and `tasks.md` with each other and the
constitution only (spec-kit's own scope), and a conflict between an assumption and the
governing section is first seen at the gates.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: How is the governing document named? A: One reference string, `<path>` or
  `<path>#<heading>`, the path relative to the item worktree (the repository the item
  changes). On the plan item it is the candidate field `governed_by`, which the lead writes
  in `lead.json` and `plan approve` and `plan add` copy like `tier`. In the spec it is a line
  `Governing: <path>#<heading>` in `spec.md`. The plan item wins when both are set (the seat
  cannot drop a requirement the plan set by editing its own spec).
- Q: Which heading matches `#<heading>`? A: The first Markdown heading whose text equals the
  given text or starts with it followed by a space (`#5.10` matches `### 5.10 Specification
  mode ...` and not `### 5.1 Roles`). The section runs to the next heading of the same or a
  higher level, or the end of the file. No `#` means the whole file.
- Q: What is "the analyze step's prompt"? A: The builder brief, which is where WUWEI tells
  the seat how to run `/speckit.analyze`. When the plan item names a governing document the
  builder brief ends with a `## Governing document` block: the reference, its line range,
  the instruction (pass this text to `/speckit.analyze` and end the report with the table)
  and the section text. When only `spec.md` names one (the spec is written after the brief),
  the builder charter carries the same instruction and the `wuwei spec analysis` refusal
  names the reference and its line range.
- Q: What is the table? A: A `## Governing` section in the report with a Markdown table whose
  columns are `Assumption | Verdict | Line`. Verdict is `agrees`, `conflicts` or
  `not covered`; Line cites `<path>:<line>` (a range such as `docs/x.md:12-20` for
  `not covered`). One row per assumption: the report needs at least as many valid rows as
  there are top-level bullets under `## Assumptions` in `spec.md`, and at least one row.
- Q: Does a `conflicts` row block? A: Not at `wuwei spec analysis`: the report is saved as
  written, so the seat can record a true conflict. The goal sentinel reports a `conflicts`
  row as a violated requirement (`blocks: yes`) unless a recorded decision rules on it, as
  it does any other violated requirement. The analyze rule `clean` (no CRITICAL or HIGH
  row) is unchanged.
- Q: Exit code for the refusal? A: 2 with the reason, like every other `wuwei spec analysis`
  refusal (#614); nothing is written.
- Q: What if the reference does not resolve (missing file, missing heading, a path outside
  the worktree)? A: Fail closed with the reason: the builder brief, the gate brief and
  `wuwei spec analysis` refuse (exit 2) naming the reference and what is missing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A governed item's analysis is checked against its governing section (Priority: P1)

The lead plans an item governed by a section of a document (a pre-registration, a design
spec section). The builder brief carries that section's text and tells the seat to give it
to `/speckit.analyze` and to end the report with one row per assumption. A report without
that table is refused when the seat saves it, so a conflict is found during the spec, not at
the gates.

**Why this priority**: the defect the owner reported.

**Independent Test**: a workspace with one item whose row has `governed_by`, a worktree with
the document and a spec-kit feature directory; write a builder brief and run
`wuwei spec analysis` with and without the table.

**Acceptance Scenarios**:

1. **Given** an item with `governed_by: docs/prereg.md#Pre-registration`, **When** the
   builder brief is written, **Then** it ends with a `## Governing document` block naming
   `docs/prereg.md#Pre-registration`, its line range, the table instruction and the
   section's text, and nothing from the rest of the file.
2. **Given** the same item and a spec with two assumptions, **When** the seat runs
   `wuwei spec analysis` with a report that has no `## Governing` table, **Then** it exits
   2, writes no `analysis.md`, and the reason names the reference, the line range, the
   missing table and the row format.
3. **Given** the same item, **When** the report's table has one valid row for two
   assumptions, or a row whose verdict is not one of the three words, or a row with no
   `<path>:<line>` citation, **Then** it is refused the same way.
4. **Given** the same item, **When** the report has a `## Governing` table with a valid row
   per assumption (any mix of `agrees`, `conflicts`, `not covered`), **Then** it is saved as
   today and the command prints its path.
5. **Given** a spec whose `spec.md` has a `Governing: docs/prereg.md#Pre-registration` line
   and an item row without `governed_by`, **When** the seat saves a report without the
   table, **Then** it is refused the same way.
6. **Given** a governed item at the gates, **When** a gate brief is written, **Then** its
   `Spec:` line names the governing reference and the `## Governing` table in
   `analysis.md`, and the goal sentinel charter tells the sentinel to check each row.

### User Story 2 - Items without a governing document behave as today (Priority: P1)

**Acceptance Scenarios**:

1. **Given** no `governed_by` on the item and no `Governing:` line in `spec.md`, **Then** the
   builder brief has no governing block, the gate `Spec:` line is unchanged, and
   `wuwei spec analysis` saves any non-empty report as today.

### Edge Cases

- `governed_by` names a missing file, a heading absent from the file, an absolute path or a
  path that leaves the worktree: the brief and `wuwei spec analysis` refuse with exit 2 and
  the reason; nothing is written.
- A spec with no `## Assumptions` bullets: the table still needs one valid row.
- The plan item and `spec.md` name different documents: the plan item's reference is used.
- Spec mode off, the engine not spec-kit, or the item's spec skipped: no governing block in
  the builder brief (there is no analyze step). `wuwei spec analysis` is spec-kit plumbing
  and still checks the table when a governed item's seat calls it.
- `governed_by` in a proposal that is not a non-empty string: `plan propose` refuses it like
  any other malformed candidate field.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A plan candidate MAY carry `governed_by`, a non-empty string; `plan propose`
  MUST refuse any other value; `plan approve` and `plan add` MUST copy it onto the item like
  `tier`.
- **FR-002**: The item's governing reference MUST be the item's `governed_by`, else the
  first `Governing:` line in the feature directory's `spec.md`, else none.
- **FR-003**: A reference MUST resolve to a file inside the item worktree and, with
  `#<heading>`, to that heading's section; otherwise every reader fails closed with the
  reason.
- **FR-004**: A spec-kit builder brief for a governed item (spec mode not off, spec not
  skipped) MUST end with a `## Governing document` block carrying the reference, its line
  range, the table instruction and the section text. Without a governing reference the brief
  MUST be byte-for-byte what it is today.
- **FR-005**: `wuwei spec analysis` MUST refuse (exit 2, nothing written) a report for a
  governed item that lacks a `## Governing` table with at least max(1, assumptions) rows,
  each with a verdict of `agrees`, `conflicts` or `not covered` and a `<path>:<line>`
  citation. The reason MUST name the reference, its line range and the row format.
- **FR-006**: A gate brief's `Spec:` line for a governed item MUST name the reference and
  the `## Governing` table in `analysis.md`.
- **FR-007**: The builder charter MUST tell the seat to name a governing document in
  `spec.md` with a `Governing:` line and to give its text to `/speckit.analyze` with the
  table; the goal sentinel charter MUST tell the sentinel to check each row against the
  cited line and report a `conflicts` row as a violated requirement; the lead charter MUST
  name the `governed_by` field. `agents/` MUST be regenerated with `bin/wuwei agents build`.
- **FR-008**: Design spec 5.10 and the owner docs that list `wuwei spec analysis` refusals
  (`docs/site/reference.md`, `docs/site/configuration.md`) MUST describe the governing
  table.

## Success Criteria *(mandatory)*

- **SC-001**: Tests pin acceptance scenarios 1 to 6 of User Story 1 and the unchanged
  behaviour of User Story 2.
- **SC-002**: `bin/wuwei agents check` is clean and the full suite passes.

## Assumptions

- The governing reference is resolved against the item worktree, because the documents the
  owner named (a pre-registration section, a design spec section) live in the repository
  the item changes. Workspace files (`.wuwei/...`) are not governing documents.
- `governed_by` is set by the lead in the candidate; there is no `plan set <item>
  governed_by=` and no `plan add --governed-by`. A wrong reference makes the item's brief
  refuse with the reason; the owner parks the item and re-adds it. Add a setter when that
  happens in practice.
- "The analyze step's prompt" is the builder brief (plan item route) and the builder
  charter (spec line route); WUWEI does not edit spec-kit's own `/speckit.analyze` command.
- The table check is mechanical (shape and row count). Whether each verdict is right is the
  goal sentinel's job, as the issue says.
- The analyze status rule (`specmode._clean`) is unchanged: a seat that writes
  `analysis.md` directly (a main-session seat can) is not checked for the table there; the
  goal sentinel reads it. Extending `_clean` would need the item row in `status`, which every
  hook calls; not needed for the issue.
- A whole-file reference puts the whole file in the brief; the lead names a section for
  large documents. No size cap.
- No orchestrator notes file exists for #664 (`notes/664-full.md` is absent); the issue is
  the only input, and the reproduction above was run in-process on a scratch copy of the
  spec-kit fixture.

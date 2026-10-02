# Feature Specification: README leads with what WUWEI does, WUWEI first in the comparison, short plain limits

**Feature Branch**: `314-readme-lead`
**Created**: 2026-10-02
**Status**: Ready for implementation
**Input**: Issue #314, docs(readme). References: `README.md`, `docs/site/index.md`,
`tests/test_docs.py`, #258 (the verified comparison, `specs/258-readme-comparison/`), #303
(writing checklist in `charters/_common-authoring.md`), #307 (Acknowledgements section,
landing in the same file). Owner feedback 2026-10-02: the comparison "puts wuwei in the
bottom", "Where WUWEI is worse" "reads heavy and not nice", and agreement with showing the
workflow instead of claiming an adjective.

## Current state (checked read-only in this worktree)

This is a docs change, so there is no failure to reproduce; the problems are where the text
sits and how it reads.

- `README.md:11-15` is the hero: tagline, the meaning of 无为 and the nav links. The next
  line, `README.md:17`, is `## What WUWEI is and is not`. Nothing between them tells a
  reader what a WUWEI day does.
- `README.md:36-79` is `## How WUWEI compares`. The table header (`README.md:44`) is
  `Tool | What it does | Layer | Unit of work | Enforcement | State`, a taxonomy, and WUWEI
  is the last row (`README.md:52`).
- `README.md:61-66` is `### How they compose`, four sentences, opening with a not-X-but-Y
  line ("WUWEI is the loop and the enforcement, not a spec format").
- `README.md:68-79` is `### Where WUWEI is worse`, six bullets, the last thing a reader sees
  before `## Install` (`README.md:81`). It repeats the guard scope that
  `docs/site/security.md` already states.
- The hero `alt` text (`README.md:5`) lists components; it does not say what the day does.
  `scripts/build-hero.py` holds the SVG `<title>` and `<desc>`, not the alt text.
- `docs/site/index.md:7` reads "It is a Claude Code plugin for a chartered team, workspace
  memory and action-time guards."
- `tests/test_docs.py:39-57` (`test_readme_compares_with_other_tools`) pins the
  `### Where WUWEI is worse` heading and its six phrases, so the section cannot change
  without the test.
- `tests/test_docs.py:510-525` (`test_hero_shows_the_current_day`) requires the alt text to
  contain `calibrat`, `tier`, `phone` and `heartbeat`.
- `tests/test_docs.py:452-468` pins the order What WUWEI is and is not, What ships today,
  How WUWEI compares, and the Quick start step order.
- `tests/test_docs.py:366` requires every relative README link to ship in the release asset.

## User Scenarios & Testing

### User Story 1 - A reader sees what WUWEI does before anything else (Priority: P1)

A reader opens the README and, right under the hero, reads two or three sentences that show
a WUWEI day: planned and ranked, reviewed by an agent that did not write the change, merged
by policy, closed by a retro that proposes rule changes.

**Independent Test**: `tests/test_docs.py` finds the lead between the hero nav line and
`## What WUWEI is and is not`.

**Acceptance Scenarios**:

1. **Given** the README, **then** the lead paragraph sits under the hero and before
   `## What WUWEI is and is not`.
2. **Given** the hero alt text and the first paragraph of `docs/site/index.md`, **then**
   both say what the day does in the same terms as the lead.

### User Story 2 - WUWEI is the first row of a comparison by question (Priority: P1)

A reader compares tools by the questions they have: who plans the day, who reviews the
work, what stops a bad merge, what is learned afterwards, where it runs. WUWEI answers first.

**Acceptance Scenarios**:

1. **Given** `## How WUWEI compares`, **then** WUWEI is the first table row, the columns
   are the tool plus at most five questions, and the six other tools keep their names and
   links, each described from its own docs, dated, never rated.
2. **Given** `### How they compose`, **then** it is two sentences.
3. **Given** the section, **then** it no longer contains "Where WUWEI is worse".

### User Story 3 - Limits are short, plain and found after Quick start (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the README, **then** `## Limits` sits after `## Quick start` and before
   `## Development installs`, and states in plain lines: needs Claude Code; one owner per
   workspace; the hook cost per tool call; early, proven so far by its author's own use,
   with the live rehearsal as the release check. It links `docs/site/security.md` for what
   the guards cover instead of listing that as a weakness.

### User Story 4 - The docs tests hold the new shape (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the docs tests, **then** they pass, and they fail if a limit fact or a tool
   link is removed, WUWEI stops being the first row, or "professional", "enterprise" or
   "best-in-class" is added to `README.md`.

### User Story 5 - The PR shows the change (Priority: P2)

1. **Given** the PR body, **then** it shows the old table and the new table one after the
   other and lists each external claim re-verified, with its URL (`research.md`).

### Edge Cases

- #307 adds an Acknowledgements section at the end of `README.md` and its own docs test. On
  rebase both changes are kept; nothing here touches the end of the README or that test.
- A claim about another tool that its current docs do not support is left out. Where the
  checked docs describe no step for a question, the cell says what the user does ("Your
  repository rules", "Your own review"), never that the tool lacks something.
- The table must render on GitHub and on a phone: at most six columns, no pipes inside
  cells, no nested lists.

## Requirements

- **FR-001**: A lead paragraph sits between the hero nav line (`README.md:15`) and
  `## What WUWEI is and is not`. It shows the workflow (planned and ranked, owner approves,
  reviewed by an agent that did not write the change, merges by policy, retro that proposes
  rule changes). No "professional", "enterprise-grade", "best" or similar; no not-X-but-Y
  sentence; no sentence that rates another project.
- **FR-002**: `## How WUWEI compares` keeps its heading, position and "As of <Month> <year>"
  date (now October 2026, the month the cells were re-checked). Table columns: `Tool`,
  `Who plans the day`, `Who reviews the work`, `What stops a bad merge`,
  `What is learned afterwards`, `Where it runs`. WUWEI is the first row. Each other tool
  cell links the tool and carries a short self-description from its own docs.
- **FR-003**: The intro is at most three sentences; the paragraph after the table keeps only
  the facts the table does not carry (roles, `gh` and optional adapters, signed release and
  ZIRAN audit). The section stays under 70 lines.
- **FR-004**: `### How they compose` is two sentences: specs can be written with Spec Kit or
  OpenSpec (this repository uses Spec Kit) and a seat can run superpowers' skills; Claude
  Code's hooks, subagents, skills and plugins are what WUWEI is made of.
- **FR-005**: `### Where WUWEI is worse` is removed. `## Limits` sits after `## Quick start`
  and before `## Development installs`, with four plain lines for the four facts and one
  line linking `docs/site/security.md` for the guard scope.
- **FR-006**: The README hero `alt` text and the first paragraph of `docs/site/index.md`
  describe the day in the lead's terms. The alt text keeps `calibrat`, `tier`, `phone` and
  `heartbeat`. The SVG `<desc>` and `scripts/build-hero.py` do not change.
- **FR-007**: `tests/test_docs.py` pins: the lead's position; WUWEI as the first table row;
  the five question columns; the six tool names and links; `## Limits` position and its
  four facts and links; no "Where WUWEI is worse"; and no "professional", "enterprise" or
  "best-in-class" anywhere in `README.md` (case-insensitive).
- **FR-008**: Every sentence written follows the writing checklist in
  `charters/_common-authoring.md` (humanizer in embedded mode when installed). No em-dashes,
  no emojis.

## Success Criteria

- **SC-001**: The first prose a reader meets under the hero says what a WUWEI day does.
- **SC-002**: WUWEI's answers are the first row a reader sees in the comparison.
- **SC-003**: The README no longer ends its pitch on a list of weaknesses; limits are four
  plain lines after Quick start.
- **SC-004**: `python -m pytest -q` passes.

## Assumptions

- Section title is `## Limits` (the issue allows "Limits" or "What to expect today"; the
  shorter one reads lighter).
- The hook cost keeps its measured range, "about 40 to 100 ms", with the latency budget
  link. The issue's suggested "a few tens of milliseconds" understates the 100 ms measured
  on 2-CPU runners (`docs/site/reference.md`, Hook latency budget); plain numbers are still
  light and stay true.
- "Heavier to set up" is dropped: the issue lists four facts, and Install shows the setup.
- "Needs Claude Code" keeps the true qualifier that Codex can run as an optional seat
  runtime.
- The guard-scope statement ("cooperative mistake prevention, not an isolation boundary")
  stays in `docs/site/security.md` and the design spec 9.1; README links it from Limits.
  `test_guard_boundaries_are_stated_once` already pins it there.
- The lead is a plain Markdown paragraph after the centered hero block; the tagline and the
  无为 line stay.
- The issue's "who plans the day" column is kept for every row; for per-feature tools the
  cell says how they plan a feature.
- Cells for other tools were re-checked on 2026-10-02 because every cell's wording changes
  (`research.md`). Where the docs describe no step for a question, the cell names what the
  user does instead.
- `scripts/build-hero.py` holds no alt text, so it does not change; regenerating the SVGs is
  out of scope.
- The old table for the PR body is the one on `main` (`README.md:44-52`).

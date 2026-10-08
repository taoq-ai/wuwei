# Feature Specification: The README explains the principles behind WUWEI and the comparison table goes (#561)

**Feature Branch**: `561-readme-principles`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #561, reopened 2026-10-08. The Mermaid workflow shipped in #589 and
stays as merged. This run does the rest of the body: Principles replaces Philosophy, the
comparison goes, the lead and "What WUWEI is and is not" stop repeating the principles, the
brand accent line goes, "What ships today" names what shipped and what is landing, and the
Acknowledgements credit the ideas the principles rest on.

## Root cause

- `README.md:106` `## Philosophy` is five bullets written before #530, #551 and #283. It names
  none of the mechanisms that now carry the framework: `wuwei next` (#551), the posture
  floors and invariant table (#530, design spec 9.2), the MIT CISR classes (design spec
  5.8), cruise levels and their safety properties (design spec 5.8.1, #556 to #560).
- `README.md:186` to `README.md:212` is `## How WUWEI compares` with its seven-row table and
  `### How they compose`. The owner (2026-10-08) wants it removed.
- `README.md:22` ends with "The brand accent is `#00C9A7`." and `README.md:24` ends with "It
  does not deploy, approve pull requests, or bypass branch protection.", which is principle 8.
- `README.md:26` to `README.md:38` "What ships today" has no line for the path (#551, shipped
  in #564) and does not say what is still landing.
- `tests/test_docs.py:136` to `:158` (`test_readme_compares_with_other_tools`) pins the
  comparison; `:184` to `:186` and `:229` to `:234` pin `## Philosophy` and the comparison
  heading in the section order; `:260` pairs Philosophy with `security`; `:122` pins
  `#00C9A7` in the README; `:775` pins the comparison heading after "What ships today".
- #589 shipped only the diagram (`specs/561-readme-principles/spec.md` Assumptions of that
  run), so no Principles section exists on main.

## User Scenarios and Testing

### User Story 1: A reader learns the principles in one place (Priority: P1)

A reader opens the README and finds one Principles section: nine numbered principles, one
short paragraph each, in plain words, each naming the mechanism that enforces it and
linking the docs page or the design spec.

**Independent Test**: `tests/test_docs.py` reads the Principles section and checks the nine
items, their order, their key phrases and their links.

**Acceptance Scenarios**:

1. **Given** the README after the change, **then** it has a `## Principles` section between
   `## What is inside` and `## Installation` with exactly nine numbered items in this order:
   the path, autonomy with floors, rules at the moment of action, decision classes, earned
   autonomy, records and cards, evidence over claims, security first, simplicity.
2. **Given** each item, **then** it names its mechanism and holds at least one link to a
   docs page, the design spec or the constitution.
3. **Given** the README, **then** there is no `## How WUWEI compares`, `### How they compose`
   or `## Philosophy` heading and no comparison table.

### User Story 2: What is landing is marked and the mark follows main (Priority: P1)

Principle 5 describes the five safety properties of earned autonomy: novelty gate (#556),
measured reversibility (#557), error budget (#558), confidence calibration (#559),
shadow-before-live promotion (#560). "What ships today" ends with one line of what is
landing. A property or item that is not on main is marked "landing" with its issue link.

**Independent Test**: a docs test reads every sentence that says "landing" and the five
property sentences, and compares them with the feature directories on main.

**Acceptance Scenarios**:

1. **Given** a property whose feature directory `specs/<issue>-*` exists on main, **then**
   its sentence carries its issue link and does not say "landing".
2. **Given** a property or item with no feature directory on main, **then** its sentence says
   "landing" and carries its issue link.
3. **Given** an issue that lands later, **when** its feature directory reaches main, **then**
   the docs test fails until the word "landing" is removed from its sentence.

### User Story 3: The rest of the README stops repeating the principles (Priority: P2)

**Acceptance Scenarios**:

1. **Given** "What WUWEI is and is not", **then** it no longer names the brand accent or the
   deploy, approval and branch-protection limits (principle 8 carries them).
2. **Given** "What ships today", **then** it has a line for the path (`wuwei next`) and the
   cruise line names the shipped safety properties in plain words.
3. **Given** the Acknowledgements, **then** OpenSpec, the MIT CISR framework, KU Leuven's
   vGOAL work, SRE error budgets and the Brier score are credited with their sources in the
   form of the existing lines, and NOTICE carries the same credits.

### Edge Cases

- The README must stay at most 300 lines (`tests/test_docs.py:182`).
- The glossary first-use rule (`test_glossary_words_link_at_first_use`) applies to the new
  text: the first `mandate`, `novel` and `unmeasured` in the README must link their glossary
  entry.
- The tone lint (#522) keeps the docs class within budget.

## Requirements

- **FR-001**: `## Philosophy` is replaced by `## Principles` at the same position, holding nine
  numbered items, one line each (soft wrap), at most 110 words each, each with a link.
- **FR-002**: The items, in order, carry these mechanisms: (1) `wuwei next` returns the one next
  action, skills and charters hold judgement; (2) under observe and guarded a guard is a
  warning or a card, the records floor, strict keeps refusals; (3) hooks check at the moment
  of action, the invariant table and its test, the code host carries the guarantee; (4) MIT
  CISR classes, Routine under mandate, Strategic and one-way on a card; (5) cruise levels
  with ceilings, the ledger, the five safety properties with issue links; (6) the workflow
  writes the records, a card answer is the confirmation, no hash or host terminal command;
  (7) unmeasured is never a pass, CI is the gate, counts from their live source; (8) ZIRAN,
  signed releases, posture per area, no deploys, no PR approvals, no admin merges; (9) stdlib
  only, no speculative abstraction, deletion over addition.
- **FR-003**: `## How WUWEI compares` and `### How they compose` are deleted.
- **FR-004**: "What WUWEI is and is not" drops the brand accent sentence and the deploy
  sentence; it says what WUWEI is (a Claude Code plugin running a chartered team across your
  repositories through the code host CLI, with workspace memory) and what it is not.
- **FR-005**: "What ships today" gains a path line linking `docs/site/agent.md`, and one
  closing "Landing next:" line naming #524, #567, #552, #579, #557, #560 and #586 with links.
- **FR-006**: Acknowledgements and NOTICE gain OpenSpec, MIT CISR, vGOAL, SRE error budgets and
  the Brier score; NOTICE's superpowers entry says "principles" where it said "philosophy".
- **FR-007**: `tests/test_docs.py` replaces every comparison and Philosophy assertion with
  Principles assertions of at least the same strength, adds the landing rule, and keeps the
  "professional", "enterprise" and "best-in-class" ban and the no em dash check.
- **FR-008**: The Mermaid block, the hero and its caption, the lead's pinned phrases, the
  commands, Quick start and Limits stay as they are.

## Success Criteria

- **SC-001**: `python -m pytest -q tests/test_docs.py tests/test_tone.py` passes.
- **SC-002**: The README has nine principles, each with a link, and no comparison heading or
  table.
- **SC-003**: The README is at most 300 lines.

## Assumptions

- The lead (`README.md:15` to `:18`) describes the day, not the principles, so it keeps its
  text; "rewrite the lead" is satisfied by checking it repeats no principle. No comparison
  sentence remains in it.
- Each principle is one numbered list line, like the "What ships today" bullets, so the
  README stays within its 300-line cap without loosening the test. Bold labels are avoided
  (humanizer checklist).
- "Landing" is decided by the feature directory: an issue is on main when `specs/<issue>-*`
  exists, because every feature lands with its spec directory. On this base #556, #558 and
  #559 are shipped; #557 and #560 are landing; #524, #552, #567, #579 and #586 are landing.
- #586 has no issue file in this run, so the landing line lists it as a bare issue link.
- The brand accent stays in the hero art and design spec 12; no docs-site text is added for
  it (the docs site already shows the hero).
- Source links: SRE error budgets link the Google SRE book chapter "Embracing Risk"; the
  Brier score links the 1950 paper's DOI (percent-encoded so the link parses); MIT CISR links
  the CISR site and names the briefing and its authors; vGOAL links KU Leuven until the owner
  gives the paper link. OpenSpec is credited as an external tool (MIT).
- The docs index (`docs/site/index.md`) has no Philosophy or comparison text, so it needs no
  change.
- No guard or decision rule changes, so no invariant row is added.

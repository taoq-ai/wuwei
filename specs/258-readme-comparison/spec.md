# Feature Specification: README comparison with Spec Kit, OpenSpec, superpowers and other ways to run coding agents

**Feature Branch**: `258-readme-comparison`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #258, docs(readme). References: README "What WUWEI is and is not";
`docs/site/concepts.md`; design sections 1 (goals and non-goals) and 9.1 (threat model and
guard scope). Owner request 2026-09-30.

## Current state (checked read-only in this worktree)

- `README.md:17-21` is "What WUWEI is and is not"; `README.md:23` starts "Install". Nothing
  in the README or `docs/site/` names Spec Kit, OpenSpec, superpowers, BMAD or Kiro, so a
  reader cannot tell how WUWEI relates to the tools they already use or whether they can
  keep using them.
- `tests/test_docs.py::test_readme_install_and_hero` pins README phrases but nothing about
  positioning, so an honest "worse" paragraph, once written, could be dropped silently.
- `tests/test_docs.py::test_release_asset_ships_every_linked_doc` requires every relative
  README link to resolve to a file in the release manifest (`docs/site/*.md` is shipped);
  external links (containing `:`) are skipped.
- `tests/test_docs.py::test_implemented_protections_are_not_planned` fails on any README
  line that contains "planned" together with "manifest", "canar" or "honeytoken".

## User Scenarios & Testing

### User Story 1 - A reader places WUWEI next to the tools they know (Priority: P1)

A reader who already uses Spec Kit, OpenSpec, superpowers, BMAD, Kiro or Claude Code's own
features opens the README and learns, in one table and three short paragraphs, what layer
WUWEI works at, what it adds, how it composes with those tools, and where it costs more.

**Independent Test**: `tests/test_docs.py` locates the section in `README.md` and checks its
position, date, tool names, links, the composition and "worse" subsections, and its length.

**Acceptance Scenarios**:

1. **Given** the README, **when** a reader reads past "What WUWEI is and is not", **then**
   the next section is the comparison, dated "As of <month year>", with one table, a "How
   they compose" paragraph and a "Where WUWEI is worse" paragraph.
2. **Given** each linked project, **then** its one-line description matches its own README
   or docs as of the date written, and the PR body lists the URL checked for each
   (`research.md` holds the list checked on 2026-09-30).
3. **Given** `tests/test_docs.py`, **then** it pins the section heading, the six tool names
   and the "worse" paragraph's points, so a later edit cannot silently drop the honest part.

### Edge Cases

- A claim about another tool that cannot be verified against its current README or docs is
  left out, not guessed.
- The table must render on GitHub and stay readable on a phone: at most six columns, no
  pipes inside cells, no nested lists; the axes that do not fit go in the paragraphs.
- The date will be refreshed by later edits, so the test pins the "As of <Month> <year>"
  form, not a fixed month.

## Requirements

- **FR-001**: `README.md` has a section `## How WUWEI compares` placed directly after "What
  WUWEI is and is not" and before "Install", under 70 lines, dated "As of September 2026".
- **FR-002**: One table with rows for Spec Kit, OpenSpec, superpowers, BMAD Method, Kiro,
  Claude Code's own plan mode, subagents, hooks and memory, and WUWEI itself; each other
  tool links to its repository or site; at most six columns.
- **FR-003**: The axes from the issue are all covered, either as table columns (layer, unit
  of work, enforcement, state) or in the first paragraph (roles and gates, code host,
  tracker and chat integration, security, the retro-to-charter loop); cost is covered in
  the "worse" paragraph.
- **FR-004**: `### How they compose`: WUWEI is the loop and the enforcement; an item's spec
  can be written with Spec Kit or OpenSpec (this repository builds WUWEI with Spec Kit); a
  seat can run superpowers' skills in its worktree; Claude Code's hooks, subagents and
  skills are what WUWEI is made of.
- **FR-005**: `### Where WUWEI is worse`: heavier setup, runs only in Claude Code, one owner
  per workspace, hooks add 40 to 100 ms per tool call depending on hardware, guards are
  cooperative mistake prevention and not an isolation boundary, and it is proven only by
  its author's own use so far, with the live rehearsal as the release criterion.
- **FR-006**: Other tools are described by what they do, in their own terms, never rated.
  No em-dashes, no emojis, no marketing adjectives.
- **FR-007**: `tests/test_docs.py` fails if the section moves, loses its date, a tool name
  or link, either subsection or any "worse" point, or grows to 70 lines or more.

## Success Criteria

- **SC-001**: A reader answers "how is this different and can I keep my current tool" from
  the README alone.
- **SC-002**: `python -m pytest -q` passes, including the existing release-asset link test.

## Assumptions

- Heading `## How WUWEI compares` and subsections `### How they compose` and
  `### Where WUWEI is worse`; the issue fixes the content, not the heading text.
- Date "As of September 2026", the month the claims were checked.
- Several issue premises differ from the tools' current docs (checked 2026-09-30, see
  `research.md`); the docs win and the section follows them:
  - superpowers is not Claude Code only: its README lists Claude Code, Codex, Cursor,
    Gemini CLI and others, loads skills through a session-start hook, and calls its skills
    "mandatory workflows". The section states this and does not call it advisory.
  - Kiro is an agentic IDE, CLI and web product built by AWS, and its hooks include
    PreToolUse, which can block a tool call. The section does not call Kiro advisory.
  - Claude Code's own PreToolUse hooks can deny a tool call with a reason; WUWEI's
    enforcement is built from them. The difference WUWEI claims is the shipped rule set
    and the day loop, not the hook mechanism.
  - BMAD's README now leads with a Clarify, Plan, Build and verify, Learn and adjust loop;
    its personas (analyst, product manager, architect, developer, UX designer) are in its
    docs reference, which is the URL cited for them.
  - OpenSpec's README shows change folders whose specs carry `## ADDED Requirements` and an
    archive step that updates the specs; "delta specs" is described that way, not by name.
- The issue's "state the model cannot forge" contradicts design 9.1 (any process running as
  the owner can forge any local file). The section says producer-only state: the CLI is
  its only writer and guards refuse other writes, which is cooperative, not a boundary.
- "Claude Code only" is stated as "runs only in Claude Code"; Codex remains an optional
  seat runtime adapter (`docs/site/adapters.md`), mentioned in the same sentence so the
  claim stays true.
- The owner's stance may be stated as WUWEI's own: prompt-level process is guidance a model
  can skip, so WUWEI anchors process in hooks; this is a statement about WUWEI's design
  choice, not a rating of another tool.
- The PR body lists the checked URLs; the builder re-checks each claim against the URLs in
  `research.md` on the day of writing and drops any that no longer hold.
- No change to `docs/site/`, the design spec, or any code outside `tests/test_docs.py`.

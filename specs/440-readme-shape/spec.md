# Feature Specification: The README borrows the shape of superpowers' README

**Feature Branch**: `440-readme-shape`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #440, docs(readme). Owner, 2026-10-03: borrow the shape of the superpowers
README (how it works, the basic workflow, when something goes wrong, what is inside,
philosophy, one installation section per harness). Shape and register only, never its text.
References: #314 (lead, comparison, Limits), #294, #340, #358, #366 (docs tests), #431 (hero
icons), #262 (Codex spike), #441 (harness support), #411 (specification mode), `NOTICE`.

## Current state (read on this worktree, based on main ea5aceb)

This is a docs change. The orchestrator notes name no dry-run workspace, so there is no
runtime failure to reproduce; the gaps are in the text and in the tests that pin it.

- `README.md:17-20` is #314's lead; `README.md:22` `## What WUWEI is and is not`;
  `README.md:28` `## What ships today`; `README.md:44` `## How WUWEI compares`;
  `README.md:72` `## Install`; `README.md:94` `## Quick start`; `README.md:133` `## Limits`;
  `README.md:148` `## Development installs`; `README.md:162` `## Development`;
  `README.md:189` `## Acknowledgements`. There is no story of a day, no numbered workflow,
  no recovery section, no inventory and no philosophy. Install is one Claude Code section
  after the comparison, and Codex appears only in Limits (`README.md:135`).
- The issue says superpowers "is already in NOTICE as a borrowed concept". It is not:
  `NOTICE:16-59` lists autoharness, ralph-starter, humanizer, Wikipedia, MCP, MCP Apps,
  release-please and ZIRAN, and no superpowers entry. The README names superpowers only in
  the comparison row (`README.md:56`) and in `### How they compose` (`README.md:69`). The
  credit is therefore a new NOTICE entry plus an Acknowledgements bullet, because
  `tests/test_docs.py:780` (`test_notice_credits_match_readme_acknowledgements`) requires
  every NOTICE URL inside the Acknowledgements section.
- `tests/test_docs.py:121-122` (`test_readme_compares_with_other_tools`) pins
  `What WUWEI is and is not < How WUWEI compares < Install`. Moving installation before the
  comparison needs that pin changed.
- `tests/test_docs.py:144-161` (`test_readme_lead_and_limits`) pins the lead (text between
  the nav line and `## What WUWEI is and is not`) and `Quick start < Limits < Development
  installs`.
- `tests/test_docs.py:638-654` (`test_readme_first_day_and_shipped_areas`) pins `What WUWEI
  is and is not < What ships today < How WUWEI compares` and the Quick start step order.
- `tests/test_docs.py:61-74` (`test_glossary_words_link_at_first_use`) requires the first
  prose use of each glossary word in `README.md` to be a link to its `concepts.md` anchor.
  New sections placed before the comparison will hold the first use of words such as seat,
  sentinel, shepherd, steward, carry, park, page, nudge and unmeasured.
- `tests/test_docs.py:551-585` (`test_release_asset_ships_every_linked_doc`) requires every
  relative README link to resolve to a file in the release manifest; a link to a directory
  (for example `skills/`) fails it.
- `tests/test_docs.py:278-295` requires `wuwei.tar.gz` to appear before the first
  `/plugin marketplace add` in `README.md` and `docs/site/index.md`.
- No test pins a README total length today.
- Specification mode (#411, design 5.10) is designed, not built: `cli/wuwei/workspace.py`
  has no `spec` table and no guard reads an engine step. Codex runs seats as an optional
  runtime (`adapters/runtime/codex.py`, `codex.command`, `gates.second_opinion`); the
  Codex plugin port the spike recommends (`docs/specs/2026-09-30-codex-plugin-spike.md:100`)
  is not built (no `.codex-plugin/`).

## User Scenarios & Testing

### User Story 1 - A reader follows one day before installing anything (Priority: P1)

A reader opens the README and, after the lead and the two short sections that follow it,
reads how a day goes in the second person, then the stations as a numbered list, then
what to do when something goes wrong, what the plugin contains and what it holds to.

**Independent Test**: `tests/test_docs.py` finds the six new sections in order between
`## What ships today` and `## How WUWEI compares`, each within its pinned size.

**Acceptance Scenarios**:

1. **Given** the README, **then** `## How it works`, `## The basic workflow`,
   `## When something goes wrong`, `## What is inside`, `## Philosophy` and
   `## Installation` exist in that order after the lead and before `## How WUWEI compares`.
2. **Given** `## How it works`, **then** it is four paragraphs, each addressing the reader
   as "you", following one day from the first `/wuwei:wuwei-plan` to the retro, naming the
   Ask card, the DM and the status line, and saying the hooks make the safe path the
   default.
3. **Given** `## The basic workflow`, **then** it is seven numbered entries (setup and
   calibration, plan and the morning gate, build, review by tier, shepherd to merge, close
   and retro, memory into tomorrow), each a bold name and one line, then one line saying
   the hooks enforce these steps in the configured posture.
4. **Given** `## When something goes wrong`, **then** it is five bullet lines naming
   `wuwei why last refusal`, `wuwei doctor --fix`, `wuwei next`, `wuwei shadow report`
   and where the records are.
5. **Given** `## Philosophy`, **then** it is five bullets in WUWEI's own words.
6. **Given** any of the new sections, **then** every `/wuwei:<skill>` names a directory
   under `skills/` and every `wuwei <command>` names a command `bin/wuwei --help --all`
   prints; there is no "professional" and no em-dash anywhere in the README.

### User Story 2 - What is inside matches what ships (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `## What is inside`, **then** each skill under `skills/` is linked to its
   `SKILL.md`, each charter under `charters/` (not the `_common` files) is linked, each
   hook event in `hooks/hooks.json` is named, and the docs site index is linked.
2. **Given** the adapters table, **then** for every port in `registry.INTERFACES` its row
   lists exactly the names `registry.known(port)` returns, and a name on the `Planned:`
   line is not an installed adapter of any port.

### User Story 3 - Installation grows one harness at a time (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `## Installation`, **then** it has `### Claude Code`, `### Codex` and
   `### Other harnesses (planned)` in that order; Claude Code keeps the signed release
   commands first and then names the GitHub marketplace as the development source.
2. **Given** `### Codex` while no `.codex-plugin/plugin.json` exists, **then** it describes
   Codex as an optional seat runtime (`adapters.runtime`, `codex.command`), says the plugin
   port is planned and links the spike document.
3. **Given** `### Other harnesses (planned)`, **then** it links issue #441, says a harness
   is listed as supported only after a measured run, and carries no install command.

### User Story 4 - Credit and the docs site follow (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `NOTICE`, **then** a superpowers entry credits the README structure (MIT, no
   text copied), and the README Acknowledgements has a matching bullet.
2. **Given** `docs/site/index.md`, **then** its page list orders Daily path, Concepts,
   Recovery, Adapters and ports, Security integration and Integrity the way the README's
   new sections link them (How it works, The basic workflow, When something goes wrong,
   What is inside, Philosophy, Installation).

### User Story 5 - Every README test still holds (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the README tests (#294, #314, #340, #358, #366), **then** they pass with the
   order pins updated, and the shipped-versus-planned rule is enforced for adapters
   (User Story 2) and harnesses (User Story 3).

### Edge Cases

- A glossary word first used in a new section must carry the `concepts.md#<term>` link
  there; the later occurrence that used to be first may keep or drop its link.
- A link to a directory fails the release-asset test; link files only.
- A line containing the word "planned" must not mention the manifest, canaries or
  honeytokens (`test_implemented_protections_are_not_planned`).
- A paragraph mentioning cruise must say "not built" (`test_cruise_mode_is_designed_not_built`);
  the same honesty applies to specification mode: the build entry says the spec engine
  steps are designed, not built (design 5.10).
- The new sections must not put a `/plugin marketplace add` before the Claude Code tarball
  commands.
- The comparison section, the lead, Limits, What ships today, the hero (#431 edits it in
  parallel), the pronunciation line and the existing Acknowledgements bullets stay as
  they are.

## Requirements

- **FR-001**: `README.md` section order: hero, lead, `## What WUWEI is and is not`,
  `## What ships today`, `## How it works`, `## The basic workflow`,
  `## When something goes wrong`, `## What is inside`, `## Philosophy`, `## Installation`,
  `## Quick start`, `## How WUWEI compares`, `## Limits`, `## Development installs`,
  `## Development`, `## Acknowledgements`. The old `## Install` body becomes
  `### Claude Code` under `## Installation`.
- **FR-002**: `## How it works`: exactly four paragraphs, each at most five lines, each
  containing "you"; covers the first `/wuwei:wuwei-plan`, the Ask card at the morning gate,
  the work through the day with the status line, an owner decision by DM, the retro, and
  the sentence that the hooks make the safe path the default so nothing has to be
  remembered.
- **FR-003**: `## The basic workflow`: exactly seven lines starting `N. **`, numbered 1 to
  7, in the station order of US1 scenario 3, each saying what starts the station and what
  it leaves behind; then one line containing "posture". The build entry states that
  specification mode is designed, not built (design 5.10, #411). Section at most 20 lines.
- **FR-004**: `## When something goes wrong`: exactly five lines starting `- `, naming
  `why last refusal`, `doctor --fix`, `wuwei next`, `shadow report` and `.wuwei/days/`.
- **FR-005**: `## What is inside`: skills (4) linked to `skills/<name>/SKILL.md`; seats
  linked to `charters/<role>.md` for every charter not starting with `_`; guards grouped
  by the six hook events in `hooks/hooks.json`; an adapters table `| Port | Shipped |`
  whose rows match `registry.known` for every port; one `Planned:` line for adapters the
  design names and the code lacks (Signal and WhatsApp owner channels, design 15); links
  to `docs/site/index.md` and `docs/site/adapters.md`.
- **FR-006**: `## Philosophy`: exactly five `- ` bullets covering: the safe path is the
  default; the workflow writes its own records and you answer questions; hooks are
  cooperative mistake prevention and the code host carries the guarantee; warn by
  default, block by posture; evidence over claims, unmeasured is never a pass; stdlib only
  at runtime.
- **FR-007**: `## Installation`: `### Claude Code` (requirements, the signed release
  commands, `/plugin marketplace add ../wuwei-plugin`, `/plugin install wuwei@wuwei`, then
  one line naming `/plugin marketplace add taoq-ai/wuwei` as the development source with a
  link to `#development-installs`); `### Codex` (optional seat runtime, `adapters.runtime =
  "codex"`, `codex.command`, `gates.second_opinion`, the plugin port planned, spike link);
  `### Other harnesses (planned)` (link to https://github.com/taoq-ai/wuwei/issues/441,
  the measured-run rule, the candidate names on one line, no code block).
- **FR-008**: `NOTICE` gains a `superpowers` entry under "Projects whose ideas or tools
  WUWEI uses (no code copied)": source https://github.com/obra/superpowers, MIT,
  Copyright (c) 2025 Jesse Vincent, used for the README section structure. The README
  Acknowledgements gains a superpowers bullet with that URL.
- **FR-009**: `docs/site/index.md` page list order: Daily path, What the session knows,
  Concepts, Recovery, Adapters and ports, Charter overrides, Security integration,
  Integrity, Configuration, Operator reference, Remote operation, Release rehearsal. Each
  README new section links its page: How it works `docs/site/daily.md`, The basic workflow
  `docs/site/concepts.md`, When something goes wrong `docs/site/recovery.md`, What is
  inside `docs/site/adapters.md`, Philosophy `docs/site/security.md`, Installation
  `docs/site/integrity.md`.
- **FR-010**: `README.md` stays at most 300 lines (215 today plus the new sections).
- **FR-011**: `tests/test_docs.py` pins FR-001 to FR-010 and the shipped-versus-planned
  rules; existing pins change only where the order moved or the NOTICE names grew.
- **FR-012**: All text written follows `charters/_common-authoring.md` (humanizer
  checklist); no em-dashes, no emojis, no sentence copied or closely paraphrased from the
  superpowers README.

## Success Criteria

- **SC-001**: A reader learns what a day looks like before the install commands.
- **SC-002**: Adding or removing an adapter, skill, charter or hook event without updating
  `## What is inside` fails `python -m pytest -q`.
- **SC-003**: `python -m pytest -q` passes.

## Assumptions

- "After the lead and before the comparison": `## What WUWEI is and is not` and
  `## What ships today` stay right after the lead, because #314's lead test ends the lead
  at `## What WUWEI is and is not` and #294 pins What ships today before the comparison.
  The six new sections follow them. `## Quick start` moves with Installation and sits
  between it and the comparison: a reader installs, then starts.
- Superpowers is not in NOTICE today, contrary to the issue; this change adds the entry
  instead of extending a line.
- "Marketplace and manual" for Claude Code: "manual" is the signed release tarball (which
  registers a local marketplace), "marketplace" is `taoq-ai/wuwei` on GitHub, the
  development source per `.claude-plugin/marketplace.json`. The signed release stays first
  (pinned by `test_entry_guides_install_signed_release_and_explain_development_checkout`),
  and `## Development installs` stays where #314 put it, linked from the Claude Code
  subsection.
- WUWEI is not listed in Anthropic's official marketplace (`claude-plugins-official`) or
  in Anthropic's directory; the README claims neither. A listing is an owner action
  outside this issue; when it exists, the Claude Code subsection gains one line.
- "Build with the engine's steps (#411)": specification mode is designed, not built, so
  the build entry describes today's builder (test first in the item's worktree, fast
  checks) and says spec engine enforcement is designed, not built.
- "Mandatory steps, not suggestions" is the owner's phrase; the line keeps the meaning
  without the not-X-but-Y form the writing checklist flags, and must contain "posture".
- Philosophy has five bullets for the six ideas the issue lists; two of them share a
  bullet (the builder picks which). The test pins five bullets and the phrases, not the
  grouping.
- "Every name linked" in What is inside applies to skills, seats, the docs site and the
  adapters page; adapter names in the table are plain text, since the table is checked
  against the code and per-module links add noise.
- The length budget is a new pin (none exists): 300 lines.
- The docs site index "mirrors the new section order in its links": the six pages the new
  sections link appear in that order in the index page list; the other six pages keep
  their relative order after them.
- The superpowers README was read once for its section shape only (headings, paragraph
  and list counts); no text is taken from it.
- The constitution's strict specification mode also lists clarify, analyze and checklist;
  this hand-off covers specify, plan and tasks, and the pipeline runs the rest.

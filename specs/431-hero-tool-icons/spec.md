# Feature Specification: The hero shows the tools behind each station

**Feature Branch**: `431-hero-tool-icons`

**Created**: 2026-10-03

**Status**: Draft

**Input**: Issue #431, docs(hero): the animated hero shows the concrete tools behind each
station as icons (Slack, GitHub, Linear, Notion, ZIRAN and the rest), shipped solid and
planned outlined. Owner request of 2026-10-03: "change the SVG animation to show the
options we have in each step of the workflow: show Slack, Notion, GitHub icons, so it is
more attractive and clear, instead of only abstract or conceptual." References: #220 (the
animated hero), #294 (Calibrate station), #370, #411/#412, #415, #416/#417, #418/#419,
NOTICE, Simple Icons (CC0).

## Current state (read on main at ed77b30)

This is a feature, not a bug; there is no failure to reproduce. What the hero does today:

- `scripts/build-hero.py` generates `docs/site/assets/hero-light.svg` and
  `hero-dark.svg` (lines 336-339) from one geometry and the palette table `PAL`
  (lines 14-19). `svg(p)` (lines 209-334) emits the stations as text in rounded boxes:
  Plan, Build, Review, Close (lines 299-304), Owner (306-309), Calibrate and Phone
  (310-315), the gate markers (293-297) and captions. No tool is named anywhere in the
  drawing; the only concrete name is "Slack DM" in `<desc>` (line 220).
- Motion: one 18 s cycle `T` (line 9). `window(times, values, begin, attr, calc)`
  (lines 141-148) animates any attribute over that cycle; tokens, pulses and the
  heartbeat use it. Reduced motion is one CSS rule (line 230) that hides `.tok`, `.pulse`
  and `.beat` and stops `.flow` and `.ring`.
- Tests in `tests/test_docs.py` pin the hero: `test_hero_files_match_their_generator`
  (line 311) compares both files with `svg(palette)`;
  `test_hero_variants_share_geometry_and_motion` (163) requires the two files to differ
  only in hex colours; `test_hero_shows_the_current_day` (696) caps each file at 20000
  bytes (line 702; both are 18250 today), checks words in the drawing, `<desc>` and the
  README alt, and requires every CSS class used in the file to appear in the
  reduced-motion block; `test_readme_install_and_hero` (102) and
  `test_readme_lead_and_limits` (144) read the README and index alt text;
  `test_notice_credits_match_readme_acknowledgements` (780) requires every URL in
  NOTICE to appear in the README Acknowledgements. No test checks that the hero has no
  external references, although the issue says one exists.
- The README alt (`README.md:5`) and the two index alts (`docs/site/index.md:5-6`) are
  one identical hand-written paragraph.
- Adapters are modules, not directories: `adapters/<port>/<name>.py`. Shipped today:
  `tracker/linear.py`, `chat/slack.py`, `inbound/slack.py`, `code_host/github.py`,
  `runtime/claude.py`, `runtime/codex.py`, `scanner/ziran.py`, `review_bot/greptile.py`,
  `checks/local.py`, `vcs/git.py`. pytest is what calibration finds and records as the
  fast check (`cli/wuwei/calibrate.py:96-100`). Remote Control is the default control
  plane (`cli/wuwei/control_plane.py:3`).
- Spec engines: #411 (merged) only amended the design spec (5.10); the `[spec]` engine
  and its hooks are #412, not built. No file under `cli/`, `adapters/`, `charters/`,
  `skills/`, `agents/` or `templates/` mentions spec-kit, superpowers or OpenSpec, and
  `.specify/` is not in the release archive (`scripts/build-release.py:14-16`); it is this
  repository's own development workflow.
- Simple Icons 16.33.0 (latest on 2026-10-03, checked on the jsDelivr CDN) has glyphs for
  linear, jira, github, claude, pytest, gitlab, notion, confluence, markdown, discord,
  pagerduty, grafana, sentry and datadog. It has none for slack, openai (Codex) or
  microsoftteams (all three return 404); those were removed at the brands' request.
- A render of the current light hero (QuickLook, `qlmanage -t`) shows these free regions
  in viewBox units: left of and below Calibrate (x 40-290, y 495-575), above Build
  (x 385-500, y 125-175), above Review (x 640-800, y 120-175), between the decision link
  and the shepherd caption (x 660-845, y 340-405), right of the memory path below Close
  (x 975-1175, y 525-590), and under the guard ring label (x 940-1170, y 40-90).

## User Scenarios & Testing

### User Story 1 - A reader sees which tools each station uses (Priority: P1)

A reader opens the README or the docs site. Under Plan, Build, Review, Close, Phone and in
an on-call note they see small monochrome tool icons with a one-word label each (Linear,
Jira, Claude, Codex, ZIRAN, pytest, GitHub, Notion, Slack and the rest). Each station
shows one row at a time; stations with two rows (Plan: tracker and spec engine; Close:
code host and docs) alternate them in the hero's 18 s cycle, and within the visible row
an accent highlight steps from tool to tool.

**Why this priority**: it is the owner's request.

**Independent Test**: `python3 scripts/build-hero.py`, render both SVGs to PNG and look;
`python -m pytest -q tests/test_docs.py -k hero`.

**Acceptance Scenarios**:

1. **Given** `python3 scripts/build-hero.py`, **When** it runs, **Then** both SVGs
   regenerate with the icon rows, contain no external reference (every `href` is a
   fragment `#...`), and the tests pin them to the generator.
2. **Given** either SVG rendered at the README's width (about 830 px), **When** the owner
   looks at it, **Then** icons and labels are legible and no row overlaps a node, a path,
   a gate marker or an existing caption.
3. **Given** the light and the dark file, **When** hex colours are masked, **Then** they
   are identical (the icons use palette tokens only, never brand colours).

### User Story 2 - The hero never shows a planned tool as shipped (Priority: P1)

Tools that exist today render as solid glyphs; planned ones render outlined and carry
`(planned)` in their `<title>`. One table in the generator says which is which, and a test
fails when the table disagrees with the repository.

**Why this priority**: the README and docs already refuse to call unshipped things
shipped; the hero must follow the same rule.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k hero_tools`.

**Acceptance Scenarios**:

1. **Given** the table, **When** a tool listed as shipped has no file at its recorded
   repository path, **Then** the test fails.
2. **Given** the table, **When** a planned tool gains an adapter module
   (`adapters/*/<slug>.py`) without the table changing, **Then** the test fails.
3. **Given** a planned tool, **When** its issue reference is not in the open-issues list
   kept in the test, **Then** the test fails.
4. **Given** the generated SVG, **When** it is read, **Then** every shipped tool appears
   as `<title>Name</title>` and every planned tool as `<title>Name (planned)</title>`.

### User Story 3 - Reduced motion shows every row at once (Priority: P1)

A reader with reduced motion on sees no stepping highlight and no alternating rows: every
row of every station is visible at once, stacked and slightly smaller, with every label
readable.

**Why this priority**: the issue requires it, and a reduced-motion reader would
otherwise see only half of the Plan and Close tools.

**Independent Test**: render a scratch copy of the SVG with the reduced-motion media query
forced on and look; the tests check the CSS and that every tool appears in the still copy.

**Acceptance Scenarios**:

1. **Given** `prefers-reduced-motion: reduce`, **When** the hero renders, **Then** the
   animated rows are hidden and a still copy with every row is shown.
2. **Given** the generated SVG, **When** it is read, **Then** each tool's `<title>`
   appears exactly twice (animated row and still copy), and every CSS class used in the
   file is named in the reduced-motion block.

### User Story 4 - Alt text names the tools in the same words (Priority: P2)

A screen-reader user gets the same tool list as a sighted one: `<desc>`, the README alt and
both index alts end with one generated sentence that names the tools per station, with the
planned ones after the word "planned". The docs index gains one sentence saying that solid
icons ship today and outlined ones are planned.

**Why this priority**: accessibility and the shipped-versus-planned rule apply to text as
much as to the drawing.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k "hero or readme"`.

**Acceptance Scenarios**:

1. **Given** the README and `docs/site/index.md`, **When** the tests read every hero
   `alt`, **Then** each contains the generator's tools sentence verbatim, and `<desc>`
   contains it too.
2. **Given** NOTICE and the README Acknowledgements, **When** the tests run, **Then**
   Simple Icons is credited in both with the same URL, and NOTICE names its version and
   CC0.

### Edge Cases

- A tool without a Simple Icons glyph (Slack, Codex, Teams, ZIRAN, spec-kit, superpowers,
  OpenSpec) gets a two-letter badge drawn in the same style (solid when shipped, outlined
  when planned).
- Claude Code and Claude mobile share the `claude` glyph; GitHub Projects reuses the
  `github` glyph. Each glyph is defined once in `<defs>` and drawn with `<use>`.
- Icon path data contains no `#` and no braces, so the hex mask test and the palette
  placeholder replacement in `svg()` keep working.
- Node, path and orbit geometry stays fixed: token timings are derived from path lengths,
  and moving a node changes every timeline.
- On-call has no place in the loop and no free path; it is drawn as a note row under the
  guard ring label, not as a new station.

## Requirements

### Functional Requirements

- **FR-001**: `scripts/build-hero.py` MUST hold one table of tools: for each, the row it
  belongs to, its full name, a one-word label, a glyph key (Simple Icons slug or a
  two-letter badge), and either the repository path that proves it ships or, when
  planned, the issue that will ship it (or none).
- **FR-002**: The rows MUST be: Plan tracker (Linear; planned Jira, GitHub Projects,
  #417); Plan spec engine (planned spec-kit, superpowers, OpenSpec, #412); Build runtime
  (Claude Code, Codex); Review gate tools (ZIRAN, pytest; the three gate markers and their
  labels stay); Close code host (GitHub; planned GitLab, #370); Close docs (planned Notion,
  Confluence, Markdown, #419); Phone and DM (Slack, Claude mobile; planned Teams, Discord,
  no issue yet); On-call note (planned PagerDuty, Grafana, Sentry, Datadog, #415).
- **FR-003**: Shipped tools MUST render as solid glyphs; planned tools as outlined glyphs
  (`fill="none"`, stroke) with `(planned)` in their `<title>`. All icons use palette
  tokens (`{text}`, `{muted}`, `{accent}`), never brand colours; icons are 18 to 22
  units; labels are at least 12 units.
- **FR-004**: Glyph path data MUST come from Simple Icons 16.33.0 (CC0), embedded in the
  generator once per glyph, with the source and version in NOTICE and the URL in the
  README Acknowledgements.
- **FR-005**: The animation MUST reuse `window()` and the cycle `T`: stations with two
  rows alternate them over the cycle; within the visible row one accent highlight steps
  across the tools (`calc='discrete'`). No new timing mechanism.
- **FR-006**: Under `prefers-reduced-motion: reduce` the animated rows MUST be hidden and a
  still copy with every row, stacked and smaller, MUST be shown.
- **FR-007**: A generated tools sentence MUST end `<desc>`, and the README alt and both
  `docs/site/index.md` alts MUST contain it verbatim; the index MUST gain one sentence on
  solid versus outlined icons.
- **FR-008**: Tests MUST check the table against the repository (FR-001, User Story 2),
  the titles and the still copy (User Story 3), no external references, the alt text, the
  NOTICE credit, and a size cap of 20000 bytes plus the embedded icon path bytes plus a
  fixed allowance for the row markup.
- **FR-009**: The generator stays stdlib only and the SVGs stay generated; no hand edits,
  no new dependency, no change under `cli/` or `adapters/`.

## Success Criteria

- **SC-001**: 23 tools across 8 rows appear in both SVGs, each with its correct status.
- **SC-002**: The full suite passes; the existing hero tests keep every assertion except
  the 20000-byte cap, which becomes the formula in FR-008.
- **SC-003**: Rendered PNGs of both themes, animated and with reduced motion forced, show
  no overlap and legible labels at 830 px wide (checked by the builder and the reviewer).

## Assumptions

- spec-kit is drawn as planned (#412), against the issue's list that calls it shipped.
  The issue's own rule is that the hero never presents an unshipped adapter as shipped:
  the plugin has no spec engine setting, enforces nothing about spec-kit, and does not ship
  `.specify/`. spec-kit is this repository's development workflow, not a product option
  yet. Flipping it is one table cell once #412 lands.
- pytest counts as shipped: calibration finds it and records `python3 -m pytest -q` as the
  fast check the build loop runs. Claude mobile counts as shipped: Remote Control is the
  default control plane. Their proof paths are `cli/wuwei/calibrate.py` and
  `cli/wuwei/control_plane.py`, not adapter modules.
- "No directory under `adapters/`" in the issue is read as "no adapter module": adapters
  are files `adapters/<port>/<name>.py`. A shipped tool records the path that proves it;
  a planned tool must have no `adapters/*/<slug>.py`, slug being its name in lower case
  with spaces as `_` and hyphens dropped.
- Teams and Discord have no issue; their planned entry records none, which the test
  accepts.
- Slack, Codex and Teams have no Simple Icons glyph (removed at the brands' request), so
  they get the two-letter badge the issue prescribes. Drawing the official Slack logo
  would need Slack's brand terms, not CC0 data.
- "The active tool lit in the accent, the others muted" is drawn as one accent highlight
  behind the active icon, stepped with one discrete `window()` per row; icons keep their
  resting colours (shipped in `{text}`, planned in `{muted}`). This is one animate element
  per row instead of one per icon, and the same `tool()` drawing serves the animated rows
  and the still copy.
- "The full set readable in the static render" is the reduced-motion render. A renderer
  that runs no SMIL shows the first row of each station.
- "Under the current limit plus the icon paths" cannot hold literally: about 14 KB of
  glyph data and about 10 KB of row markup cannot fit in the current 1750 bytes of
  headroom. The cap becomes 20000 plus the embedded path bytes plus a fixed row allowance
  no larger than 12000; the builder records the measured size in tasks.md.
- On-call is drawn as a note row under the guard ring label (the issue's fallback): the
  loop has no free path for a planned station without moving nodes.
- Row placement is set by rendering, not by formula; plan.md gives starting positions
  read from a render of the current hero.
- No clarifying questions were asked (AGENTS.md); these assumptions stand in for them.

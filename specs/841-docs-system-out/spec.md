# Feature Specification: delete the docs system

**Feature Branch**: `b7-leftovers` (feature directory `specs/841-docs-system-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #841, part 19 of the #789 deletion pass: "chore(docs): delete the docs system".

## Context

The docs system (design 5.12) is:

- the docs obligation: for an item tiered in `docs.required_tiers` under a `docs.system`, a
  recorded docs value (`plan set <item> docs=<page>|new|none --reason`), shown by `why --json`
  and the `next` `docs` row;
- the quality gate's wall on it: `dispatch.receive` refuses a quality PASS (or a FIX without
  `DOC: FINDING`) while the value is missing, the verdict lint refuses a finding that calls a
  recorded value missing, and the quality charter's step 7 makes the sentinel reason about it;
- the builder brief's `Docs:` line and the builder charter's docs sentence;
- the item docs page writer (`wuwei docs page`), the day page publisher (`wuwei docs publish`,
  called by `report` and `retro` when `docs.publish` lists the kind), the close lines
  (`docs.close`) and the report's `## Docs` section;
- the docs adapters (`adapters/docs/`: notion, confluence, markdown, none) behind the `docs`
  port, `adapters.docs` mirrored from `docs.system`, and the doctor `docs` row.

The owner's issue: the quality sentinel no longer blocks on a docs page. Every unit above makes
a seat or the planner reason about a process (which value, which command, which page) or adds
a wall at the quality gate. A change to documented behaviour is still reviewed by the quality
sentinel as code (the generic `DOC` finding class stays) and by the goal sentinel for a
docs-only diff.

Not the docs system, and kept: the `DOC` finding class (`verdict.CLASS_NAMES`,
`dispatch.CLASS_PATHS`); the docs-only tier rule (`dispatch` `DOC_DIRS`); the MCP `docs`
channel of the outward lint (Notion and Confluence tool names, `outward.humanize_kinds`,
`outbound.owner.pages` from part 16); the doctor `docs:` link field; `tests/test_docs.py` (the
documentation site).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The quality gate never blocks on a docs value (Priority: P1)

**Why this priority**: the owner named it in the issue.

**Independent Test**: an item tiered `standard` with a former `[docs] system = "notion"`
config reaches the quality gate with no docs value.

**Acceptance Scenarios**:

1. **Given** a quality PASS verdict for that item, **When** `dispatch receive` runs, **Then**
   it records the PASS; nothing refuses over docs.
2. **Given** a quality verdict with a finding "docs value missing", **When** the verdict lint
   runs, **Then** it is linted as any finding; no docs rule refuses it.
3. **Given** that item at `gate`, **When** `wuwei next` runs, **Then** the row is `verdicts`;
   no `docs` row exists.

### User Story 2 - No docs command, page or publish step (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei docs page X` or `wuwei docs publish report` runs,
   **Then** argparse refuses it; `wuwei plan set X docs=new` is refused as an unknown field.
2. **Given** `wuwei report` and `wuwei retro`, **When** they run, **Then** they publish nothing
   and the report has no `## Docs` section.
3. **Given** `wuwei close`, **When** it runs, **Then** no docs line holds it.
4. **Given** a builder brief, **When** it is written, **Then** it has no `Docs:` line, and
   `why --json` has no `docs` key.

### User Story 3 - `init --upgrade` removes the retired keys (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a config with a `[docs]` table and `adapters.docs`, **When** `init --upgrade`
   runs, **Then** both are removed and reported, and the config loads with no warning.

### Edge Cases

- A day state may hold `items.<item>.docs` and events `docs.set`, `docs.written`,
  `docs.exempt`. Nothing reads them after this part; old days stay readable.
- `NOTION_TOKEN` and `CONFLUENCE_*` stay in `env.py`'s credential list: they are still
  scrubbed from seat environments when a workspace's `.wuwei/env` holds them.
- Pages written before the upgrade stay where they are; WUWEI no longer links them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cli/wuwei/docs.py`, `cli/wuwei/commands/docs.py`, `adapters/docs/` and their
  tests and fixtures MUST be deleted. `specmode.governed` keeps working: the `_sections` helper
  it imports moves into `specmode.py` first.
- **FR-002**: `dispatch.receive` MUST NOT refuse a quality verdict over docs, and
  `verdict.lint` MUST NOT take or apply a docs value (`DOCS_MISSING`, `recorded_docs`, the
  `docs=` parameter go).
- **FR-003**: `next`, `why`, `brief`, `closing`, `report`, `retro`, `plan set`, `doctor`,
  `config`, `dispatch` (`docs.exempt`), `registry` (the `docs` port), `state`, `event` and
  `signal` MUST NOT import `wuwei.docs` or name the docs system.
- **FR-004**: The `[docs]` table and `adapters.docs` MUST leave the schema, the template and
  the `adapters.docs` mirror in `load_config`, and join `workspace.RETIRED` as `docs` and
  `adapters.docs`.
- **FR-005**: `charters/sentinel-quality.md` step 7 and the builder charter's docs sentence
  MUST go (versions bumped, agents rebuilt with `bin/wuwei agents build`).
- **FR-006**: The design spec 5.12, the docs site, README and the adapter table MUST name no
  docs system, docs obligation, docs page writer, day page publisher or docs adapter.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rnE "from wuwei import docs|wuwei\.docs|commands\.docs|docs page|docs publish|docs\.(system|required_tiers|publish|auto|strict_close|space|root)|adapters\.docs|docs obligation|docs value|recorded_docs|DOCS_MISSING"`
  over `cli/`, `adapters/`, `charters/`, `skills/`, `agents/`, `templates/` and `docs/site/`
  returns nothing.
- **SC-002**: A quality PASS for a standard item is received with no docs value
  (`tests/test_dispatch.py`).
- **SC-003**: `init --upgrade` removes `[docs]` and `adapters.docs`
  (`tests/test_config_transition.py`).
- **SC-004**: Every touched test file passes. No test is loosened.

## Assumptions

1. The whole docs system is (a): it makes a seat or the planner reason about a documentation
   process and walls the quality gate. No row of "process control kept" depends on it.
2. The MCP `docs` channel (Notion and Confluence tool names in the outward lint) is not the
   docs system: it decides the lint channel and the owner's own pages (#838) for an MCP send.
   It stays.
3. Credential names for Notion and Confluence stay in `env.py`: scrubbing a secret from a seat
   is a security floor, not docs machinery. Only `config`'s requirement rows for the docs
   adapters go.
4. `telemetry.ADAPTERS` keeps `'docs'` for stored weeks (its test lists it beside the retired
   `inbound`).
5. Part 16 (#838) lands first; it already removed the drafts paths of `docs.py` and the
   `docs.auto` branch of `outward.py`.

# Feature Specification: Documentation system: `[docs]` system and obligation per tier, docs page from the item's record, report and retro publishing, Notion by default with Confluence and repository Markdown adapters

**Feature Branch**: `419-docs-system`
**Created**: 2026-10-03
**Status**: Ready to build
**Input**: Issue #419, feat(docs). Implements design section 5.12 "Documentation system"
(amended by #418, commit 1a039ca), with its pointers in the 4.1 hook table and the section 8
adapter table. Related: #174 (draft queue), #280 (gate tiers), #282 (cruise classes), #420
(humanizer pass, on main), #417 (tracker hygiene, ticket record, same wave), #412 (spec mode,
`plan set spec=`, same wave).

## Root cause (read on main, 1a039ca)

A feature, not a regression. The orchestrator notes name no dry-run workspace, so the gap was
reproduced read-only in a scratch workspace whose `config.toml` holds only
`[docs] system = "notion"`:

- `wuwei config check` exits 0 with `warning: config.toml: unknown key docs at line 1`: there
  is no `[docs]` table in `SCHEMA` (`cli/wuwei/workspace.py:45`) and no `docs` kind in
  `PARAMETERS` (`cli/wuwei/registry.py:13`), so nothing validates or loads a docs adapter, and
  `adapters/docs/` does not exist.
- `wuwei docs page X` exits 2 `invalid choice: 'docs'`: no command module.
- `wuwei plan set X docs=new` exits 2 `invalid choice: 'set'`
  (`cli/wuwei/commands/plan.py:11`, `register`, has no `set` verb).
- The gate never asks about documentation: `dispatch.next_step` records the tier
  (`cli/wuwei/dispatch.py:178`, `gate.tiered`) and `dispatch.receive` records a quality PASS
  (`cli/wuwei/dispatch.py:364`) with no item-level check; the gate brief header
  (`cli/wuwei/brief.py:285`) carries no docs line; the quality charter has no docs step.
- The day close accounts for decisions, items and branches only (`cli/wuwei/closing.py:231`,
  `check`), so an item merges and the day closes whatever it did to the documentation.
- A docs write has no policy: `outward.classify` drafts every kind other than chat
  (`cli/wuwei/outward.py:345`), and the draft queue accepts only chat, code-host comment and
  tracker create (`cli/wuwei/drafts.py:10`, `OPERATIONS`).
- The HTTP helper only POSTs (`adapters/_http.py:41`, `request`), and Notion and Confluence
  reads need GET, Notion appends need PATCH and Confluence updates need PUT.
- The interview never asks where documentation lives (`cli/wuwei/interview.py:199` asks about
  tracker, chat and review bot), and `doctor` has no docs row.

## User Scenarios & Testing

### User Story 1 - The quality gate and the day close enforce the docs obligation (Priority: P1)

An item tiered `standard` or `full` must declare what it did to the documentation before its
quality gate passes and before the day closes.

**Independent Test**: a day fixture with `docs.system = "notion"` and one standard item:
`dispatch receive` refuses a quality PASS, `close` refuses naming `plan set`, and both pass
after `plan set <item> docs=none --reason "<why>"`.

**Acceptance Scenarios**:

1. **Given** a STANDARD item at the gate with no docs value, **When** the quality sentinel's
   verdict is received, **Then** a `PASS` is refused, a verdict without `DOC: FINDING` is
   refused, and a `FIX` verdict carrying `DOC: FINDING` is recorded; the quality brief carries
   a `Docs:` line naming `bin/wuwei plan set <item> docs=...`.
2. **Given** that item merged today with no docs value, **When** `wuwei close` runs, **Then**
   it exits 1 with a line naming `bin/wuwei plan set <item> docs=...`.
3. **Given** `wuwei plan set <item> docs=none --reason "<why>"`, **Then** the quality `PASS`
   is received, `close` has no docs line, and `wuwei report` shows the reason in its `## Docs`
   section.
4. **Given** a LIGHT item, **When** `dispatch next` tiers it, **Then** exactly one
   `docs.exempt` event is recorded and neither the gate nor close asks for a value.
5. **Given** `docs.strict_close = false`, **Then** close does not refuse for docs and the
   report's `## Docs` section lists the unmet lines instead.
6. **Given** `docs.system = "none"` (the default), **Then** nothing in this story applies: no
   brief line, no receive refusal, no close line, no event.

### User Story 2 - Pages are written from the item's records (Priority: P1)

**Independent Test**: `wuwei docs page <item>` against the Notion recorded fixture queues one
draft; with `auto = ["page"]` it writes and records one `docs.written` event.

**Acceptance Scenarios**:

1. **Given** `wuwei docs page <item>` with the Notion fixture, **Then** a pending draft
   (channel `docs`, operation `write`) holds a page with the item id and the first line of its
   scope as the title, the scope, PR title, goal outcome and evidence, the PR body's
   `How to use` section when present, and the PR and ticket links; the page holds no absolute
   path, no `.wuwei/` path and no credential, and no HTTP call was made.
2. **Given** `docs.auto = ["page"]`, **Then** the same command writes the page at once through
   the adapter, records one `docs.written` event (item, kind, adapter, page) and, when the value
   was `new` or unset, records the new page link as the item's value.
3. **Given** a pending docs draft, **When** the owner runs `wuwei drafts approve <id>`, **Then**
   the page is written, one `docs.written` event carries the draft id, and close no longer names
   the item.
4. **Given** a rendered page that would hold an absolute path, a `.wuwei/` path, a
   `state.json` or `events.jsonl` name, or a loaded credential, **Then** `docs page` refuses
   (exit 1) and names the reason; nothing is drafted or written.
5. **Given** a merged required-tier item whose value is `new` or a remote page, **When** close
   runs with no `docs.written` event for it since its merge, **Then** close names
   `wuwei docs page <item>`; with its draft pending, close names `wuwei drafts approve <id>`.

### User Story 3 - The Markdown adapter puts the page in the item's pull request (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `docs.system = "markdown"` and an item with a worktree, **When** the builder runs
   `wuwei docs page <item>`, **Then** `<root>/<item>.md` is written atomically under the item's
   worktree (never a draft), the item's value becomes that relative path, and one `docs.written`
   event is recorded; a second run appends a dated section.
2. **Given** markdown, **Then** `plan set <item> docs=new` is refused naming
   `wuwei docs page <item>`, and `plan set <item> docs=<path>` is refused for a path outside
   `root` or a file that does not exist in the worktree.
3. **Given** markdown and a merged item whose PR did not change its recorded path, **Then**
   close names the path; when the PR's files include it, close has no docs line.
4. **Given** markdown, **Then** `publish` has no effect and `doctor` warns when it is set.

### User Story 4 - The day's report and retro are published once (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `docs.publish = ["report"]` under notion, **When** `wuwei report` runs, **Then**
   it offers one draft holding the report's Merged, Parked, Decisions answered, Carry and Docs
   sections titled `Report <date>`; a second `wuwei report` the same day names the first draft
   and creates nothing.
2. **Given** `"retro"` in `publish`, **Then** `wuwei retro` does the same with the retro's
   Applied and Proposed sections titled `Retro <date>`.
3. **Given** `wuwei docs publish report|retro`, **Then** the same function runs on request.

### User Story 5 - Each adapter passes the docs port contract (Priority: P1)

**Acceptance Scenarios**:

1. **Given** each adapter (`notion`, `confluence`, `markdown`, `none`) and its recorded
   fixtures, **Then** the port contract test passes: `read(ref)` returns `id`, `title`, `link`
   and `updated`; `write(draft)` with an empty `ref` creates under `parent` and with a `ref`
   appends, returning `id` and `link`; an error body, a missing credential or a timeout is exit 2
   with no provider text in the reason; no test reaches the network.
2. **Given** `none`, **Then** each call records one `adapter: none` event and returns exit 2.

### User Story 6 - Setup, interview and doctor know the docs system (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the interview, **Then** it asks "Where does your documentation live?" with
   Notion, Confluence, Markdown and None, and a pasted Notion or Confluence link sets
   `docs.system` and `docs.space` together.
2. **Given** a configured repository whose README links `https://<site>.atlassian.net/wiki/...`,
   **When** setup runs the interview, **Then** the docs question offers that link as the Enter
   default; with no link found, Notion is the first choice.
3. **Given** `doctor`, **Then** a docs row reads `not used` under `none`; under notion or
   confluence it fails when `space` is empty, a credential is missing, or `read(space)` does not
   return a page; under markdown it fails when `root` is not a directory in a configured
   repository and warns when `publish` is set; each failure names its fix.
4. **Given** an unknown `docs.system` name, **Then** the config check refuses it naming
   `docs.system` and the known adapter names.

### User Story 7 - The board and `wuwei next` show an unmet obligation (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a required-tier item at `gate` or `delta` with no value, **Then** `wuwei next`
   returns a `docs` row whose command is `wuwei plan set <item> docs=...`, and the board's Work
   table shows `missing` in a Docs column.

### Edge Cases

- An item that never reached the gate has no recorded tier and no obligation yet; a carried or
  parked item keeps its tier and value and is checked the day it merges.
- A dropped docs draft leaves the item with neither a write nor a pending draft: close names
  `wuwei docs page <item>` again.
- A page whose text matches an `outward.patterns` entry is refused by the lint at write (auto)
  or approve time; no docs-only pattern set is added.
- A Notion or Atlassian MCP write tool used directly by a seat matches the new default
  `outward.tool_patterns` rows under channel `docs` and meets the same policy (its payload shape
  fails closed).
- `plan set` under `docs.system = "none"` is refused (no obligation exists).
- A remote read in `plan set` that cannot run (network, credential) refuses with exit 2; one
  that runs and finds no page refuses with exit 1.

## Requirements

### Functional Requirements

- **FR-001**: `config.toml` MUST accept `[docs]` with `system` (default `none`, validated
  against `adapters/docs/`), `required_tiers` (`["standard", "full"]`), `space` (`""`), `root`
  (`"docs"`), `publish` (`["report", "retro"]`), `auto` (`[]`) and `strict_close` (`true`).
- **FR-002**: The registry MUST have a `docs` port with `read(ref)` and `write(draft)`, and
  `adapters/docs/` MUST hold `notion`, `confluence`, `markdown` and `none`, each passing one
  port contract test with recorded fixtures.
- **FR-003**: `wuwei plan set <item> docs=<page>|new|none [--reason]` MUST record the item's
  value, reading a page through the port first; `none` needs a reason; markdown refuses `new`.
- **FR-004**: `dispatch next` MUST record one `docs.exempt` event when it tiers an item outside
  `required_tiers`.
- **FR-005**: The quality gate brief MUST carry the obligation and value; `dispatch receive`
  MUST refuse a quality `PASS`, or a quality verdict without `DOC: FINDING`, while a required
  value is missing.
- **FR-006**: `wuwei close` MUST refuse the four unmet cases of 5.12, each line naming its
  command, unless `strict_close = false`, which moves them to the report.
- **FR-007**: `wuwei docs page <item>` MUST render the page from the records, refuse raw
  records, absolute paths and credentials, pass the humanizer pass, write under markdown, and
  draft or (kind in `auto`) write under notion and confluence, recording `docs.written`.
- **FR-008**: `wuwei docs publish report|retro`, `wuwei report` and `wuwei retro` MUST publish
  the day's page once per kind per day when `publish` lists it, never under markdown.
- **FR-009**: `docs.written`, `docs.exempt` and `docs.set` MUST be written only by the CLI, and
  the item's `docs` field only by `plan set` and `docs page`.
- **FR-010**: Setup, the interview, `doctor`, `config check` credentials, the board, `wuwei
  next`, the charters and the site docs MUST cover the docs system as 5.12 says.
- **FR-011**: With `docs.system = "none"`, every existing behaviour MUST be unchanged.

## Success Criteria

- **SC-001**: Each acceptance scenario above has a test that failed before the change.
- **SC-002**: `python -m pytest -q` passes; no test reaches the network.
- **SC-003**: Under the default config the diff changes no existing test outcome other than
  tests that pin lists this feature extends (adapter calls, events, glossary, interview ids,
  template keys, commands).

## Assumptions

- `plan set` takes the form #412 and #417 use in this wave: `plan set <item> <key>=<value>`
  with `--reason`. `none` is written `docs=none --reason "<why>"`; the design's
  `none, <reason>` is the recorded meaning, not a second CLI form. Whichever of #412, #417 and
  #419 lands second merges into one `set` verb that dispatches on the key.
- #412 adds `('plan', 'set')` to the owner-only actions in `guards/protect_state.py`. 5.12 has
  the builder set the docs value, so at merge that guard entry must refuse only `spec=`
  assignments. This branch adds a test that a seat's `bin/wuwei plan set X docs=...` is not
  refused by the hook, so the conflict fails loudly at merge.
- `docs.system` is exposed to the registry as a derived `config['adapters']['docs']` set in
  `load_config`, so `registry.load`, `drafts.approve`, `config check` credentials and the
  existing adapter contract tests work unchanged. `adapters.docs` itself stays an unknown key.
- The item value is stored as `items.<item>.docs = {"value": <page>|"new"|"none", "reason": str}`.
- The ticket link reads 5.11's record (`tickets.<item>.id`, #417) when present and is omitted
  otherwise; nothing here writes tickets.
- The code host `pr()` result gains `title` and `body` (read with defaults of `""`), the
  smallest way to render "the PR title" and "How to use"; no new code-host operation.
- "Raw record" means a `.wuwei/` path or a `state.json`/`events.jsonl` name in the rendered
  text; a relative `decisions/D-n.md` pointer in the report's Parked section is a reference,
  not a record, and is allowed. An absolute path is any token starting with `/`, `~/` or a drive
  letter after whitespace or punctuation; URLs are allowed. A credential is any line that
  `redact.redact` changes.
- `plan set` refuses a page whose read returns exit 1 as a finding (exit 1) and exit 2 as could
  not run (exit 2); a Notion or Confluence 404 surfaces as exit 2 from the shared HTTP helper.
- Under markdown the adapter receives absolute paths in `draft.parent` and `draft.ref`; the
  docs module records only the path relative to the worktree, so no absolute path reaches state,
  events or a draft (markdown is never drafted).
- The markdown write is not routed through `registry.outward_operation`: it is a file in the
  item's PR, not an outward write. The port walk test in `tests/test_outward.py` gets a
  per-adapter exemption for `('docs', 'write', 'markdown')`; `docs page` runs
  `outward.humanize_lint` itself for markdown.
- Close checks "since its merge" against the first event today whose `phase_changes` moves the
  item to `merged`.
- A builder brief also carries the `Docs:` line (system and required tiers) so the builder
  knows to set the value before it stands down; the tier is computed later, at gate dispatch.
- The new interview question is asked once at the next morning gate in existing workspaces,
  like any added question; its answer goes through the calibration proposal as the others do.
- Setup's link detection offers the found link as the Enter default of the docs question;
  the table order (Notion first) is the fallback.
- The publish-once check counts any docs draft (any status) or `docs.written` of that kind
  today, so a dropped report draft is named, not recreated.
- Glossary entries "Docs system" and "Docs obligation" are appended to the glossary and to the
  `GLOSSARY` table in `tests/test_docs.py`.

- Found while building: a retro's `## Applied` and `## Proposed` lines name charter targets as
  `` `.wuwei/charters/<role>.md` ``, which the renderer refuses, so no retro with a landed proposal
  could ever publish. `publish` names them workspace-relative (`` `charters/<role>.md` ``), like the
  report's `decisions/D-n.md` pointers; every other `.wuwei/` path still refuses.
- Found while building: under markdown, `docs page` refuses (exit 1) when the recorded value names
  a file that is no longer in the worktree, instead of creating a page at a path nobody chose.
- `setup` exits 1 after a docs answer whose credentials are not yet in `.wuwei/env`, naming the
  variable, like any other adapter credential.

## Deferred

- None filed. If #417 lands with a different ticket record shape, the one ticket lookup in
  `docs.render` follows it.

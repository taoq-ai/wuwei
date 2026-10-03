# Feature Specification: Documentation system: a configured docs system (Notion by default, Confluence and repository Markdown as options) with a docs obligation per tier checked at the gate and at close, and pages written from the records

**Feature Branch**: `418-docs-system-spec`
**Created**: 2026-10-03
**Status**: Ready for verification (the amendment text is already in the working tree)
**Input**: Issue #418, spec(docs). New design section 5.12 "Documentation system", mirroring
the structure of 5.11 (tracker hygiene, #416, same wave), with pointers in the 4.1 hook
table and the section 8 adapter table. Related: #174 (draft queue), #282 (cruise classes),
#280 (gate tiers), #343 setup and #279 interview, #419 (the implementation, same chain).
Evidence: owner request 2026-10-03 ("Likewise, a config to enforce a documentation system.
Default is Notion, but Confluence and others could be options too."), and the owner's
follow-up on this run: the docs system "could be part of the interview even".

## Root cause (read on main, 0a37d8e)

This is a spec gap, not a runtime failure; the orchestrator notes name no dry-run
workspace to reproduce against. Nothing in WUWEI knows where documentation lives or
whether an item changed it:

- `grep -ril 'notion\|confluence'` over `cli/`, `adapters/`, `charters/`, `skills/`,
  `templates/`, `docs/site/` and `docs/specs/` finds nothing. There is no `docs` port in
  `cli/wuwei/registry.py:13` (`PARAMETERS`) and no `[docs]` table in the config schema
  (`cli/wuwei/workspace.py:45`, `SCHEMA`).
- The day close accounts for approved items, decisions and pushed branches only
  (`cli/wuwei/closing.py:150`, `unresolved`; the item loop at `:195`). An item merges and
  closes whatever it did to the documentation.
- The gate tier is computed and recorded once, at the first gate dispatch
  (`cli/wuwei/dispatch.py:40` `tier`, written at `:172`), and `dispatch.receive`
  (`:291`) records a quality verdict without any item-level check beyond the verdict lint.
  The quality charter (`charters/sentinel-quality.md`) has no documentation step; only the
  builder's `DOC:` class row exists (`charters/builder.md:26`).
- The outward policy drafts every write on a channel it does not know
  (`cli/wuwei/outward.py:312`, `classify`), and the draft queue accepts only chat, code-host
  comment and tracker create operations (`cli/wuwei/drafts.py:10`, `OPERATIONS`), so a
  docs write has no policy of its own today.
- The interview asks about tracker, chat and review bot (`cli/wuwei/interview.py:199`),
  never about documentation.

## User Scenarios & Testing

### User Story 1 - The owner configures one docs system (Priority: P1)

The owner, the #419 builder or a reviewer reads 5.12 and finds the `[docs]` keys with their
defaults, which adapter each `system` selects, and how setup and the interview propose it.

**Independent Test**: the phrase check in plan.md "Verification commands" passes on the
worktree and fails on a `git archive main` export.

**Acceptance Scenarios**:

1. Given the amended spec, then 5.12 defines `system` (`notion`, `confluence`, `markdown`,
   `none`; schema default `none`, recommended `notion`), `required_tiers` (default
   `["standard", "full"]`), `space` and `root` (default `docs`), `publish` (default
   `["report", "retro"]`), `auto` (default `[]`) and `strict_close` (default `true`).
2. Given 5.12, then the interview asks "Where does your documentation live?" with Notion,
   Confluence, Markdown and None or a page link, and setup proposes the system from links in
   each repository's README and CONTRIBUTING, Notion leading when none is found.
3. Given 5.12, then `doctor` has a docs row that fails when the system is configured and
   unreachable, missing its `space` or a credential.

### User Story 2 - Every required-tier item names its documentation (Priority: P1)

**Acceptance Scenarios**:

1. Given 5.12, then an item in a required tier carries one `docs` value (`<page>`, `new` or
   `none, <reason>`) set by `wuwei plan set <item> docs=<value>` or by `wuwei docs page`,
   and a `light` item has no obligation and one `docs.exempt` event.
2. Given 5.12, then before the gate verdict the quality brief carries the obligation, the
   quality sentinel checks it under the `DOC` class, and `wuwei dispatch receive` refuses a
   quality `PASS` while the value is missing.
3. Given 5.12, then `wuwei close` refuses an item merged today in a required tier with no
   value, with `new` or a remote page not written since its merge, with a pending docs
   draft, or (markdown) with a path its PR did not change, each line naming its command;
   `docs.strict_close = false` turns these into report lines.

### User Story 3 - Pages are written from the records under the outward policy (Priority: P1)

**Acceptance Scenarios**:

1. Given 5.12, then `wuwei docs page <item>` renders what changed, why, how to use it and
   the PR and ticket links from the item's records, creates (`new`) or appends to (a page)
   the page, and under `markdown` writes the file in the item's worktree to go out with
   the PR.
2. Given 5.12, then `wuwei docs publish report|retro` writes the day's page once per kind,
   from named report and retro sections, and `wuwei report` and `wuwei retro` publish when
   `publish` lists them; under `markdown` `publish` has no effect.
3. Given 5.12, then a remote write is direct only for a kind in `auto` and otherwise a
   draft (4.9), the lint applies to both, no page holds a raw record, absolute path or
   credential, and every write is one CLI-only `docs.written` event.
4. Given 5.12 and section 8, then the `docs` port has `read(ref)` and `write(draft)`, and
   the Notion, Confluence and Markdown adapters each name their operations and credentials
   and pass the port contract test with recorded fixtures.

### User Story 4 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the diff, then only `docs/specs/2026-09-24-wuwei-design.md` and
   `specs/418-docs-system-spec/` changed, and `python -m pytest -q` passes, including
   `tests/test_docs.py`.
2. Given the spec, then #419 can be built without further design decisions.

### Edge Cases

- An item that never reached the gate has no recorded tier; it is not merged, so the close
  carries or parks it and the obligation waits for the day it merges.
- A docs draft the owner drops leaves the item with neither a write nor a pending draft:
  close names `wuwei docs page <item>` again or `plan set <item> docs=none, <reason>`.
- A page whose text matches an `outward.patterns` entry (for example a feature about a job
  queue) is refused by the lint at write or approve time; the owner edits the draft or
  narrows the patterns. No docs-only pattern set is added.
- `markdown` with `publish` set: nothing is published and `doctor` warns.
- A seat using a Notion or Atlassian MCP write tool directly meets the same policy through
  the default `outward.tool_patterns`.

## Requirements

### Functional Requirements

- **FR-001**: 5.12 MUST define the `[docs]` keys and defaults listed in US1.
- **FR-002**: 5.12 MUST define the obligation per tier, its three value forms, who sets
  it, and the `light` exemption with its event.
- **FR-003**: 5.12 MUST define the two check points: the quality gate (brief, `DOC`
  finding, receive refusal of a `PASS` without a value) and the day close (four refusal
  cases, each naming its command, and `strict_close`).
- **FR-004**: 5.12 MUST define the write kinds (`page`, `report`, `retro`), the approval
  rule (`auto` or draft; markdown never a draft), the content rules and the
  `docs.written` event.
- **FR-005**: 5.12 MUST name the port operations and, per adapter, the remote operations
  and credentials; section 8 MUST list the port.
- **FR-006**: 5.12 MUST define what the day publishes (report and retro pages, once per
  kind per day) and the setup, interview and doctor behaviour.
- **FR-007**: No runtime code, test, charter, template or site page changes in this issue.

## Success Criteria

- **SC-001**: The phrase check fails on main and passes on the worktree.
- **SC-002**: `python -m pytest -q` passes unchanged.
- **SC-003**: #419's builder needs no design decision beyond 5.12 and this plan.

## Assumptions

- Spec-only, like #282 and #301: the spec author writes the amendment in the working tree
  and the builder verifies it (phrase check red on main, green here), reviews it and runs
  the suite. The issue names no constitution change, so `.specify/memory/constitution.md`
  is untouched.
- `system` keeps the issue's key name rather than `adapters.docs`; it is the port's adapter
  selector, validated against `adapters/docs/` like every adapter name.
- "Default is Notion" is read as the recommended answer: the schema default is `none`, so
  an existing workspace gains no obligation and no failing doctor row on upgrade. The
  issue's "default when configured" says the same.
- Tier names are lowercase (`light`, `standard`, `full`) as `repos.gates.floor` and
  `dispatch.TIERS` already spell them; the issue's uppercase spelling is prose.
- The tier that decides the obligation is the effective gate tier recorded at the first
  gate dispatch, not the lead's proposed tier, because only that one exists for every item.
- The obligation is checked at the gate as a declaration (no PR exists yet) and the remote
  page is written after the merge, so the page can link the merged PR. Markdown pages are
  written before the gate because they travel in the PR.
- The `docs` value is seat-writable by design: it is a declaration the quality gate
  reviews and the report shows, never trusted as an owner action. `docs.written` and
  `docs.exempt` are CLI-only events.
- One `space` key serves Notion and Confluence; a Confluence `space` must be the `https`
  link because it also names the site, so no separate URL key is added.
- An update appends a dated section instead of replacing the page, so people's edits stay
  and no merge logic is needed.
- "How to use it" comes from the PR body's `How to use` section when present; no new
  record is introduced for it.
- The published retro will often meet the outward lint (it talks about seats and
  charters); it is then a draft the owner edits or drops. No retro-specific lint relaxation.
- Section numbers 5.10 and 5.11 belong to #411 and #416 in this wave and are not on main;
  5.12 refers to 5.11 for the ticket link. If those sections land with other numbers, the
  merge renumbers the reference.
- The owner's addition of 2026-10-03 puts every docs write, `markdown` included, through
  the humanizer pass first (`[outward] humanize`, default true); #420 builds the pass and
  its configuration, 5.12 only names it in the outward rule. 5.11 (#416) has the same gap
  and is fixed in its own worktree.
- Under `markdown` a page must exist before the gate to travel in the PR, so `plan set`
  refuses `new` there and `wuwei docs page <item>` before the gate records the path.
- The doctor checks `space` and credentials only for `notion` and `confluence`; under
  `markdown` it checks that `root` is a directory in a configured repository.
- The owner's follow-up ("could be part of the interview even") is satisfied by the
  interview question; setup's link detection only orders its choices.

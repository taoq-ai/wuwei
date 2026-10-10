# Feature Specification: gate briefs carry the owner's approval wording

**Feature Branch**: `731-approval-wording`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #731 (owner, 2026-10-10, item 58): the arch gate's brief did not quote
the owner's approval wording that the builder brief carried, although that wording settles the
item's scope. The brief writer copies the item's recorded approval (the gate card answer text,
`plan approve` notes, the owner's wording from the plan) into every gate brief under
`Approved as:`; the sentinel charters say the scope question is answered by it. The record
stays the source (`why <item>` shows it).

## Root cause (read on main at d3b7066)

The owner's approval wording is recorded nowhere, so no brief can copy it; it reaches a seat
only when the lead retypes it into a brief body.

- `plan.approve` (`cli/wuwei/plan.py:359`) builds each approved item at `plan.py:444` from
  `goal`, `track`, `flags`, `budget_size`, `tier` and `governed_by`. The candidate's `scope`,
  the plan text the owner approved on the gate card (rendered as `Scope:` in `plan.md`,
  `plan.py:291`), stays in `proposal.json` only. `wuwei plan approve`
  (`cli/wuwei/commands/plan.py:24-28`) takes no note, so the owner's own words on the card
  have no record either.
- `plan.add` (`plan.py:471`) admits an owner-named item with `goal`, `title` and `ticket`
  (`plan.py:557-563`); the owner's words that named it have no argument and no field.
- `brief.write` (`cli/wuwei/brief.py:376`) builds the gate header from the verdict file,
  Assumptions, Docs and Live lines (`brief.py:513-526`) and appends the lead's free-text body
  (`brief.py:533`). Nothing in the header comes from the item's approval, so each brief carries
  the wording only if the lead copies it into that brief's body.
- `why <item>` (`cli/wuwei/commands/why.py:146`) shows `queued: goal ..., score ...` and no
  approval wording.

Reproduced read-only in the owner's workspace for day 2026-10-10: an owner-named item admitted
with `plan add` (event `plan.added`, `source: owner`, no wording in the payload or the item
record). Its `briefs/builder-<item>.md` body quotes the owner's decision in full (line 21,
"Owner decision (2026-10-10, in chat): ..."); its `briefs/arch-<item>.md` body says only
"(owner decision 2026-10-10)". No `_pipeline/notes/731-full.md` exists, so the issue, this
workspace and the code on main are the inputs.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is "the item's recorded approval"? A: One new item field, `items.<item>.approved_as`,
  a one-line string written only when the item is admitted: by `plan approve`, the candidate's
  `scope` from the approved proposal, then `; owner: "<note>"` when `--note` is given; by
  `plan add`, `owner: "<note>"` when `--note` is given, else no field. A discovery candidate
  admitted by the intraday policy without a note gets no field: the owner did not approve its
  scope, so it is never labelled approved.
- Q: Per-item or plan-wide note on `plan approve`? A: Plan-wide, one `--note`: the gate card
  answer is one text for the whole plan. It is recorded on every item the call approves, after
  that item's own scope, so each gate brief reads the scope the owner approved and the words
  the owner said when approving it. Imported carry-over items and adopted PR claims keep what
  they had (carry-over copies the earlier day's item record, field included).
- Q: Does copying the value into the brief break #667 (values the day changes are read live)?
  A: No. `approved_as` is written once, at admission, and no command changes it during the day,
  so the copy cannot go stale under a seat. Later scope words from the owner are a scope
  change: a decision record (one-way under `_common.md` decisions rule 2), which `why` already
  lists. `plan add --note` on an item already in the plan is refused (exit 1) naming that route,
  so the owner's words are never silently dropped.
- Q: Which briefs carry it? A: Every builder and gate brief of an item with the field, as one
  header line `Approved as: <value>` beside the `Live:` line. The builder is included because
  the builder brief carrying it today depends on the lead retyping it, the same root cause.
  Shepherd and steward briefs do not.
- Q: Where do the charters say it answers the scope question? A: One sentence in
  `charters/_common.md`, `## Evidence and gates` rule 7 (classify each finding against the
  item's promise), which every sentinel charter reads first and every sentinel agent file
  embeds. The charter one-home test (`tests/test_charters.py:67`) forbids repeating the
  sentence in each `sentinel-*.md`. `bin/wuwei agents build` regenerates `agents/`.
- Q: How does the planner know to record it? A: `charters/planner.md` rule 3 and
  `skills/wuwei-plan/SKILL.md` name `--note "<the owner's words>"` on `plan add` and
  `plan approve`; `docs/site/daily.md` says the same for the owner. The gate card's record
  command (`plan.gate_widget`) does not change.
- Q: Who may write the field? A: Only `plan approve` and `plan add` (dedicated producers,
  `reserved=False`). A generic `state set items.<item>.approved_as` is refused as reserved and
  names those two commands. It is not `items.<item>.note`, which any generic write may change
  (`state.py:358`).

## User Scenarios and Testing

### User Story 1 - Every gate brief quotes the approval (Priority: P1)

**Independent Test**: approve or add an item with a note, write its gate briefs, read the
`Approved as:` line.

**Acceptance Scenarios**:

1. **Given** an item approved with a note (`plan add OWN-1 --goal G-1 --note "<words>"`),
   **When** any gate brief for it is written (arch, quality, security, goal; initial and
   delta), **Then** its header contains `Approved as: owner: "<words>"`.
2. **Given** an item approved at the morning gate with `plan approve --items A --note
   "<words>"`, **When** a gate brief for A is written, **Then** its header contains
   `Approved as: <A's scope>; owner: "<words>"`.
3. **Given** an item approved at the morning gate without a note, **Then** its gate briefs
   contain `Approved as: <its scope>`.
4. **Given** the builder brief of such an item, **Then** it carries the same line; a steward or
   shepherd brief does not.
5. **Given** an item with no `approved_as` (a discovery candidate admitted without a note),
   **Then** no brief has an `Approved as:` line.

### User Story 2 - The record stays the source (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item with `approved_as`, **When** `wuwei why <item>` runs, **Then** it prints
   `approved as: <value>` right after the queued step, and `why <item> --json` lists the same
   line in `steps`; at `--full` the line names `.wuwei/days/<date>/state.json`.
2. **Given** an item without it, **Then** `why` prints exactly what it prints today.
3. **Given** `state set items.<item>.approved_as <x>`, **Then** it is refused as reserved,
   written by `wuwei plan approve or wuwei plan add`.
4. **Given** `plan add <item> --note "<x>"` for an item already in today's plan, **Then** it
   exits 1 naming the decision record route and the record is unchanged.

### User Story 3 - Seats and the planner are told (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the generated sentinel agent files, **Then** each says the brief's `Approved as:`
   line answers whether a change is in the item's scope.
2. **Given** the planner agent file and the plan skill, **Then** they name `--note` on
   `plan add` and `plan approve` for the owner's own words.

### Edge Cases

- A multi-line or padded note or scope is flattened to one line (`' '.join(text.split())`, as
  `plan set --reason` does), so the header line never contains a blank line and the brief header
  is never cut early.
- An empty or whitespace note records nothing extra.
- `--note` is recorded only on the items the approve call admits, never on imported carry-over
  items or adopted claims.

## Requirements

- **FR-001**: `plan.approve(..., note=None)` records `approved_as` on each newly approved item:
  its flattened `scope`, plus `; owner: "<note>"` when the flattened note is not empty.
- **FR-002**: `plan.add(..., note=None)` records `approved_as = 'owner: "<note>"'` on the admitted
  item when the flattened note is not empty, and refuses a note for an item already in the plan
  (exit 1, naming `bin/wuwei decision template`).
- **FR-003**: `wuwei plan approve` and `wuwei plan add` take `--note` and pass it through.
- **FR-004**: `brief.write` adds `Approved as: <approved_as>` to the header of every builder and
  gate brief whose item has the field.
- **FR-005**: `why <item>` lists `approved as: <approved_as>` as its own step after the queued
  step when the item has the field.
- **FR-006**: `items.<item>.approved_as` is reserved; the refusal names `wuwei plan approve or
  wuwei plan add`.
- **FR-007**: `charters/_common.md` rule 7 says the `Approved as:` line answers the scope
  question; `charters/planner.md` rule 3 and `skills/wuwei-plan/SKILL.md` name `--note`;
  `docs/site/daily.md` documents it; `agents/` is regenerated with `bin/wuwei agents build`.

## Success Criteria

- **SC-001**: For an item approved with a note, every gate brief written for it contains the note
  under `Approved as:` (the issue's acceptance).
- **SC-002**: Briefs and `why` output for items without the field are byte-for-byte as today.
- **SC-003**: The full suite passes.

## Assumptions

- No orchestrator notes file exists for #731; the issue text, the owner's 2026-10-10 workspace
  (read only) and the code on main are the inputs. The workflow's relayed owner request (item
  63, owner commands and the workspace folder) belongs to another issue; this run specs #731
  only.
- "The gate card answer text" is the owner's own words when answering the morning gate card;
  the chosen label (Approve, Approve at fast) is the pace and is already recorded (`pace`).
  The planner passes the words with `--note`; the card's record command is unchanged, so a
  planner that omits `--note` records the scope alone.
- "The owner's wording from the plan" is the candidate's `scope`, the `Scope:` line of
  `plan.md` the owner approved on the card. It is the lead's text approved by the owner, which
  is what the sentinel needs to judge scope.
- The plan-wide approve note is copied to every item it approves, not split per item: the
  card answer is one text and the planner should not paraphrase the owner. Overturn: owners
  writing item-specific notes at the gate often enough that the copy misleads a gate.
- A seat can run `plan add <new item> --note` like any `plan add` today; it cannot change the
  field on an existing item (FR-002, FR-006). Making `plan add` owner-only is out of scope.
- The `plan.approved` and `plan.added` event payloads stay as they are; the state record is the
  source and `why` reads it.

## Deferred

- None.

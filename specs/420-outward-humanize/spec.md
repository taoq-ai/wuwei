# Feature Specification: Every external write goes through the humanizer pass by default

**Feature Branch**: `420-outward-humanize`
**Created**: 2026-10-03
**Status**: Ready
**Input**: GitHub issue #420, "feat(outward): every external write goes through the humanizer
pass by default (configurable): tracker comments, docs pages, DM, PR comments and review
pings". Owner, 2026-10-03: "External writes stay under the outward policy. For this,
humanizer skill must always be used by default (configurable)."

## Problem (reproduced)

Reproduced read-only on `main` (9434cc0) with a throwaway workspace (owner set, `C1` a work
channel, `C2` an external voice source) and the real chat port with a fake sink:

- `chat.post('C2', 'This is not just a fix but a rewrite. We delve into it.', None)` returns
  exit 1 and stores a draft whose `style` is `['not-x-but-y', 'stock-word']`. Nothing warns the
  seat, the only event is `draft.created`, and no setting can refuse the text.
- `workspace.load_config(root)['outward']` has the keys `banned_characters`, `max_length`,
  `patterns` and `tool_patterns` only; there is no way to turn a humanizer pass on, off or to
  strict.

Root causes, with file and line on `main`:

1. `cli/wuwei/outward.py` `lint` (lines 57 to 104) checks owner references, internal patterns,
   banned characters, length and voice; it never calls `tells` (lines 41 to 44). The tells table
   `TELLS` (lines 27 to 38) is used only to annotate drafts (`cli/wuwei/drafts.py` line 59),
   decision lint (`cli/wuwei/decision.py` line 179) and the `ai_tells` metric
   (`cli/wuwei/metrics.py` lines 505 to 513). A send that clears the tier (`outward.check_call`,
   lines 357 to 367) and every MCP write through the hook (`cli/wuwei/guards/outward.py`
   `check_lint`, lines 23 and 24) is never checked for tells at all.
2. `cli/wuwei/workspace.py` `SCHEMA['outward']` (lines 147 to 161) has no `humanize`,
   `humanize_kinds` or `humanize_strict` key.
3. The `dash` row of `TELLS` (line 32) matches an en dash and ` -- ` but not an em dash; the em
   dash is refused by `banned_characters` only, so a workspace that clears that list loses it.
4. Two outward writes bypass the port wrapper `registry.outward_operation` (lines 165 to 195):
   the PR reply draft in `cli/wuwei/pr_actions.py` (classify at line 418, `drafts.create` at line
   434) and the PR title and body in `cli/wuwei/shepherd.py` `raise_pr` (`outward.lint` at line
   267, `host.create_pr` at line 290). Nothing asserts that every adapter write of free text goes
   through the port wrapper, so the tracker and docs adapters #417 and #419 add could skip it.
5. `cli/wuwei/drafts.py` `approve` (lint at line 138, confirmation prompt at line 146) shows the
   destination and text but not the style findings.
6. `charters/_common-authoring.md` line 17 and `skills/wuwei-plan/SKILL.md` line 10 name the
   humanizer for "text written for a person" but not for tracker comments, docs pages, DMs, PR
   comments or review pings, and say "only an em dash or an emoji is refused".

Already in place and reused: `outward.tells` and `TELLS` (one table, one function), the port
wrapper `registry.outward_operation` and `outward.check_call` (every adapter write of free text
today: `chat.post`, `chat.dm`, `tracker.create`, `code_host.comment`), the hook guard
`guards/outward.py`, the draft row's `style` field and the `ai_tells` metric (#303), the
`drafts` JSON listing, `profile_result`, `workspace.verbosity`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Outward text is checked for AI tells before it is drafted or sent (Priority: P1)

A seat or the CLI writes a tracker comment, a docs page, a DM, a PR comment or a review ping.
Before the text is drafted or sent, the CLI checks it against the humanizer tells table. By
default a finding warns and is recorded so the `ai_tells` metric counts it; with
`humanize_strict = true` the write is refused with the findings and a rewrite hint.

**Why this priority**: this is the owner's instruction; it is the deterministic backstop for
every external write.

**Independent Test**: call the real chat port with a fake sink, with default, strict and
disabled settings; check the result, the draft row and the events.

**Acceptance Scenarios**:

1. **Given** `[outward] humanize = true` (the default) and a chat post whose text has two tells
   (`not-x-but-y` and `stock-word`) to a destination the tier drafts, **When** the port is
   called, **Then** it returns exit 1 with the stored draft id, the draft row's `style` lists the
   two findings, and today's events contain one `outward.ai_tells` event whose payload is
   `{"kind": "review", "tells": ["not-x-but-y", "stock-word"], "draft": true}` and no message
   text.
2. **Given** the same text and `humanize_strict = true`, **When** the port is called, **Then** it
   returns exit 1 with a reason naming both findings and the rewrite hint (the humanizer skill in
   embedded mode, the checklist in `charters/_common-authoring.md`), no draft is stored, and no
   `draft.created` or `outward.ai_tells` event is written.
3. **Given** `humanize = false`, **When** the same port call runs, **Then** no humanize lint
   runs: no `outward.ai_tells` event, no humanize warning on stderr, and `humanize_strict = true`
   refuses nothing.
4. **Given** `humanize_kinds = ["dm"]`, **When** a chat post (kind `review`) with tells is
   drafted, **Then** no `outward.ai_tells` event is written; a chat DM with the same text writes
   one with `"kind": "dm"`.
5. **Given** a seat's MCP write (for example a Linear comment matched by `outward.tool_patterns`)
   with a tell, **When** the PreToolUse outward lint guard runs, **Then** it warns and records
   `outward.ai_tells` by default and returns exit 1 with the findings under
   `humanize_strict = true`; the `outward` posture area and the profile govern that result like
   every other outward lint finding.
6. **Given** `humanize_strict = true`, **When** `wuwei pr act <ref> --reply <text with a tell>`
   would draft the reply, or `shepherd.raise_pr` is given a title or body with a tell, **Then** it
   exits 1 with the findings before any draft or PR is created.

### User Story 2 - The owner sees the findings where drafts are decided (Priority: P2)

The owner sees each draft's findings in `wuwei drafts`, sees them again in the approval prompt,
and sees a count in the DM status reply at full verbosity only.

**Why this priority**: the owner decides drafts; the findings must be visible without adding
reading load at the default verbosity.

**Independent Test**: queue a draft with tells, list it, approve it with a recording
confirmation fake, and send `status` through `remote.handle` at `brief` and `full`.

**Acceptance Scenarios**:

1. **Given** a pending draft with two tells, **When** the owner runs `wuwei drafts`, **Then** the
   JSON row carries `style` with both names.
2. **Given** that draft, **When** the owner runs `wuwei drafts approve <id>`, **Then** the
   confirmation prompt contains the destination, the text and a line naming both findings, and
   the send goes ahead once confirmed (default, not strict).
3. **Given** `humanize_strict = true` and an owner edit that introduces a tell, **When** the owner
   runs `wuwei drafts approve <id> --edit`, **Then** it exits 1 with the findings and nothing is
   sent; approval bypasses nothing.
4. **Given** pending drafts carrying three tells in total, **When** the owner sends `status` in
   the DM, **Then** at `owner.verbosity.dm = "full"` the reply ends with `| ai tells 3`, and at
   `brief` or `standard` it does not mention tells.

### User Story 3 - No adapter can send free text around the port (Priority: P1)

Every adapter operation that sends free text is wrapped by `registry.outward_operation`, so the
tracker and docs adapters built in parallel (#417, #419) inherit the humanizer pass and the walk
test fails the day one is added without it.

**Why this priority**: the pass is only as good as its coverage; the owner asked for every
external write.

**Independent Test**: walk `registry.PARAMETERS`, load every installed adapter of each kind, and
check every operation whose parameters include a text field or a `draft`.

**Acceptance Scenarios**:

1. **Given** every installed adapter module, **When** the walk test inspects each operation in
   the port contract whose parameters include `text`, `message`, `body`, `title`, `description`
   or `draft`, **Then** each one is the `registry.outward_operation` wrapper, except the named
   exemptions: `tts.speak` and `redactor.redact` (local, nothing leaves the host) and
   `code_host.create_pr` (its only caller, `shepherd.raise_pr`, runs the outward lint and the
   humanize lint on the title and body first).
2. **Given** a new adapter operation with a `text` parameter and no wrapper, **When** the walk
   test runs, **Then** it fails naming the kind, module and operation.

### User Story 4 - Seats and the planner run the humanizer on outward text, said once (Priority: P2)

When the humanizer skill is installed, the planner's and the seats' briefs name it for outward
text in embedded mode, once, with the checklist from `charters/_common-authoring.md`.

**Why this priority**: the skill does the rewrite; the CLI lint only catches what is left.

**Independent Test**: read the charter section, the generated agents and the plan skill.

**Acceptance Scenarios**:

1. **Given** the humanizer skill installed, **When** a seat's agent file or the planner skill is
   read, **Then** it names the `humanizer` skill in embedded mode exactly once, and that sentence
   names tracker comments, docs pages, DMs, PR comments and review pings.
2. **Given** the charter section "Writing for a person", **When** it is read, **Then** it still
   carries the ten-line checklist, has no tell and no em dash, and no longer says that only an
   em dash or an emoji is refused.

### Edge Cases

- A text with tells only inside inline code: `tells` already strips inline code; no finding.
- A custom `outward.tool_patterns` channel (not `chat`, `slack`, `tracker`, `code_host`,
  `docs`): it maps to no humanize kind and is not checked.
- An unreadable policy or payload while humanizing: exit 2 with the existing reason
  `outward: cannot read or validate policy or payload`; never clean.
- The event cannot be appended: exit 2, fail closed, same as any state write.
- `humanize_kinds` with an unknown name: a config finding at load time (schema choices).
- Strict mode turned on after a draft with tells was queued: approval refuses it until the owner
  edits the text.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `[outward]` MUST accept `humanize` (bool, default `true`), `humanize_kinds` (list
  drawn from `dm`, `tracker`, `docs`, `pr`, `review`; default all five) and `humanize_strict`
  (bool, default `false`); an unknown kind is a config finding.
- **FR-002**: One function, `wuwei.outward.humanize_lint(inputs, root, config, channels, *,
  draft=False)`, MUST decide the humanize kind (`dm` for a DM, `review` for any other chat or
  Slack post, `tracker`, `pr` for the code host, `docs`), run `outward.tells` on the text fields,
  and return `(0, '')` when off, out of kind or clean; `(1, reason)` under strict; otherwise
  record one `outward.ai_tells` event `{kind, tells, draft}`, print a warning to stderr and
  return `(0, reason)`.
- **FR-003**: The reason MUST name every finding and the rewrite hint: rewrite with the humanizer
  skill in embedded mode, or the checklist in `charters/_common-authoring.md`.
- **FR-004**: The `TELLS` table MUST stay the one list; its `dash` row MUST also match an em dash.
  No second checker is added.
- **FR-005**: `outward.check_call` (the port wrapper's policy) MUST run `humanize_lint` before a
  draft is stored (with `draft=True`) and before a send (after the outward lint passes), with the
  profile applied as it is to the outward lint; its signature MUST NOT change.
- **FR-006**: The PreToolUse outward lint guard MUST run `humanize_lint` after the outward lint
  passes, inside the same guard so the `outward` posture area and the profile govern it.
- **FR-007**: `pr_actions` MUST run `humanize_lint` (kind `pr`, `draft=True`) before it stores a
  PR reply draft; `shepherd.raise_pr` MUST run it on the title and body before `create_pr`.
- **FR-008**: `drafts.approve` MUST run `humanize_lint` on the final text (`draft=True`): under
  strict it refuses with exit 1 and sends nothing; otherwise the confirmation prompt shows the
  findings line.
- **FR-009**: The `ai_tells` metric MUST count `outward.ai_tells` events with `draft = false`
  (sends) in addition to draft rows and decision records, so a draft is never counted twice.
- **FR-010**: `outward.ai_tells` MUST be a silent event kind (no nudge) and reserved: the
  `wuwei event` command refuses it and names its producer.
- **FR-011**: The DM `status` reply MUST append `| ai tells <n>` (total findings on pending
  drafts) only when `owner.verbosity.dm` resolves to `full` and `n > 0`.
- **FR-012**: A walk test MUST assert every free-text adapter operation is wrapped by
  `registry.outward_operation`, with the three named exemptions.
- **FR-013**: The authoring charter's "Writing for a person" sentence and the plan skill MUST name
  outward text (tracker comments, docs pages, DMs, PR comments, review pings) for the humanizer
  in embedded mode, once each; the generated agents MUST be rebuilt.
- **FR-014**: Docs MUST cover the three `[outward]` keys in `configuration.md`, one paragraph in
  `concepts.md` under writing for the owner, a `Humanizer` glossary entry, the template's
  commented keys and the `drafts approve` reference row.

### Key Entities

- **Humanize kind**: one of `dm`, `tracker`, `docs`, `pr`, `review`, derived from the port or
  tool channel and the DM flag.
- **`outward.ai_tells` event**: `{kind, tells: [names], draft: bool}`; never the text.

## Success Criteria *(mandatory)*

- **SC-001**: With default settings, every adapter write of free text and every matched MCP write
  that has a tell produces a warning and an `outward.ai_tells` event; with strict on and the
  default profile, none of them is drafted or sent through a port.
- **SC-002**: With `humanize = false`, no write produces an `outward.ai_tells` event or a
  humanize warning.
- **SC-003**: The walk test covers every free-text operation in `registry.PARAMETERS`; adding an
  unwrapped one fails the suite.
- **SC-004**: At the default DM verbosity the owner reads no new text.

## Assumptions

- "Review pings" is every non-DM chat or Slack post: WUWEI's own channel messages are review
  pings and work-channel replies, and the issue's five kinds have no other chat kind.
- Custom `outward.tool_patterns` channels map to no humanize kind and are not checked; a workspace
  that adds one can map it later.
- Forced triads need judgment (the skill keeps three real items), so the mechanical table does
  not try to detect them; the embedded pass and checklist item 4 cover them. Staged openers
  (`run-up`), one-line closers (`closer`), not-X-but-Y, stock words and bold labels are already
  rows; the em dash is added to `dash`.
- `humanize = false` turns off the humanize lint (warning, event, refusal). The draft row's
  `style` field and the `ai_tells` metric from #303 keep measuring, since they are measurement,
  not a pass; that field is how "the draft queue shows the lint result on each draft" today.
- On the hook path, humanize follows the outward posture area and the profile like the rest of
  the outward lint, so under the default `guarded` posture a strict finding on an MCP write is a
  `guard.would_refuse` warning; on the port path the profile alone applies (the default `strict`
  profile blocks).
- The hook guard runs independently of the tier guard, so an MCP write the tier refuses can still
  record its tells, and the seat's retry through the port records them again. Accepted ceiling,
  marked with a `ponytail:` comment.
- The control-plane DM (`remote.dm`) is not humanized: its fixed lines are pinned tell-free by
  `test_owner_facing_templates_are_plain`, and it goes to the owner's own DM. Chat port DMs (the
  watch digest, seat DMs) are humanized.
- "The DM shows the count only in the full verbosity" is the DM `status` reply: it is the only DM
  that summarises the day, and drafts have no DM of their own.
- The approval event (`draft=True`) is kept for the audit trail but not counted by the metric,
  which counts the draft row.
- #417 and #419 add tracker comment and docs operations through `registry.outward_operation` and
  their own `drafts.OPERATIONS` entries; this feature only maps the `docs` channel to its kind.

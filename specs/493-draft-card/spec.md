# Feature Specification: a held draft names its rule and id, the owner approves it on a card, and the approved draft goes out through the same MCP tool

**Feature Branch**: `493-draft-card`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #493, "fix(outward): a draft names the rule that forced it and its id,
the owner approves it on a card, and the approved draft goes out through the same MCP tool the
seat called; drafts approve keeps the adapter path for configured adapters". Owner,
2026-10-04, on 0.15.0: a review ping through a claude.ai Slack connector was held as a draft
"even after I say that it can be sent", and "the outward decision never says which rule
forced a draft".

## Root cause (read and reproduced on main, 6b82f7b, read-only)

Reproduction: the notes name no dry-run workspace, so a scratch workspace in a temp directory
(owner name, `outbound.work_channels = ["C1"]`, seeded integrity) ran
`wuwei.guards.outward.check_tier` in process for five Slack MCP calls (unknown channel `C9`,
an unknown `@dev` mention, a commitment, "Can you review my PR?", and the same send with
`WUWEI_SEAT_ROLE=shepherd`), then the full `wuwei hook PreToolUse` for the unknown channel.
All five returned the same line, `outward: channel slack needs owner approval; write it as a
draft for the owner to send`, with `posture: outward = block (owner-only action; no setting
lowers it)` as the second hook line, and `state.json` held no `drafts` row afterwards.

1. **The rule is thrown away.** `outward.classify` (`cli/wuwei/outward.py:297-406`) has
   fourteen `return FINDINGS, 'draft'` sites for different rules (headless shepherd seat at
   301, sensitive or commitment or disagreement text at 325, DM and external audience at 330,
   unknown recipient at 344, external org at 347, docs and tracker tiers at 349 and 353,
   chat thread at 359, code-host PR context at 363, unknown or missing destination at 367,
   review gate at 378, unclassified prose at 390, unresolved commit at 404) and returns only
   the word `draft`. `check_tier` (`outward.py:441-442`) maps every one to the constant
   `APPROVAL_REQUIRED`, and the guard (`cli/wuwei/guards/outward.py:133-135`) rewrites that
   to one channel line.
2. **An MCP draft is never stored, so it has no id.** Only the port wrapper
   (`cli/wuwei/registry.py:187-192`) calls `drafts.create`. The MCP guard path refuses and
   tells the session to "write it as a draft", but nothing records one, so neither the owner
   nor the planner can point at it.
3. **An approved draft cannot leave through a connector.** `drafts.approve`
   (`cli/wuwei/drafts.py:125-131`) requires `config['adapters'][row['channel']]` to equal the
   row's adapter and replays through `registry.load(channel)`. A connector has no WUWEI
   adapter, and a row stored with adapter `none` replays into `registry.record_none`
   (exit 2). The seat that holds the working tool is never allowed to repeat the call.
4. **The owner's word is not a record.** `drafts approve` is an owner action
   (`cli/wuwei/guards/protect_state.py:50-51`) that is not in the planner's gate edits
   (`_GATE_EDITS`, `protect_state.py:156`), and the question guard
   (`cli/wuwei/guards/decision.py:186-195`) accepts only questions citing a `D-n`, a `C-n` or
   the morning gate, so the planner can neither ask a draft card nor record its answer.
   `drafts.approve` always calls `integrity._host_confirm` (`drafts.py:151-158`), which needs
   `/dev/tty`, so even a recorded answer could not be acted on from the session.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The refusal names the rule and the draft (Priority: P1)

When the outward tier holds a message back, the guard stores it as a draft and the reason
names the draft id, the rule that forced it with its evidence, and the one command that shows
the card: `outward: draft <id>: <rule>: <evidence>; the owner decides: bin/wuwei drafts show
<id> --widget`. The second hook line names the posture as today. `wuwei why last refusal`
prints the same rule and fix.

**Why this priority**: the owner cannot fix or approve what they cannot see; every later
story needs the stored draft and its id.

**Independent Test**: call `guards.outward.check_tier` with five MCP payloads in a
`tmp_path` workspace and assert five distinct rules, a stored pending row per call, and the
widget command in each reason.

**Acceptance Scenarios**:

1. **Given** a Slack MCP send to channel `C9` that is not in `outbound.work_channels`,
   **When** the hook runs, **Then** the reason is `outward: draft <id>: unknown destination
   C9: not in outbound.work_channels; the owner decides: bin/wuwei drafts show <id> --widget`,
   the second line is the outward posture line, a pending draft `<id>` holds the call, and
   `wuwei why last refusal` prints `rule: outward: draft <id>: unknown destination C9: ...`
   and `fix: the owner decides: bin/wuwei drafts show <id> --widget`.
2. **Given** the five classify rules (unknown destination, unknown mention, approval tier,
   headless seat, review ping without a code-host link), **When** each drafts a call,
   **Then** five distinct reasons, each naming its rule in the issue's words.
3. **Given** the same held call made twice before any decision, **When** the guard runs the
   second time, **Then** it reuses the first pending draft's id instead of queueing a second.
4. **Given** a port draft (an adapter operation the tier holds), **When** it is stored,
   **Then** its reason has the same shape, and the docs, tracker and digest callers that
   read a stored draft id from the reason still find it.

---

### User Story 2 - The owner answers a card in the session (Priority: P1)

`bin/wuwei drafts show <id> --widget` prints one AskUserQuestion widget (#359) with the text,
destination, tool or adapter and rule, and the options `Send now`, `Send with an edit`, `Keep
as draft`, `Drop`. The planner asks it, and the answer becomes a record by the command the
card names: `bin/wuwei drafts approve <id>` (with `--file <path>` for an edited text) or
`bin/wuwei drafts drop <id>`. Outside strict the planner may run that command after asking the
card (the #357 records rule); under strict the guard refuses it from the session and prints it
for a host terminal.

**Why this priority**: it turns "send it" in chat into a record, which is the owner's actual
complaint.

**Independent Test**: store a draft, print its widget, replay the AskUserQuestion PreToolUse
and PostToolUse payloads for the planner session, then replay a Bash `drafts approve <id>`
through `protect_state` under guarded and strict.

**Acceptance Scenarios**:

1. **Given** a pending draft, **When** `drafts show <id> --widget` runs, **Then** it prints
   a JSON list with one widget whose header is `Draft`, whose question cites `<id>`, the
   destination, the rule and the text, whose options are the four labels with the
   recommended one first and marked `(Recommended)`, and whose `record` is `bin/wuwei drafts
   approve <id>`; the option descriptions name `--file` for an edit and `drafts drop <id>`.
2. **Given** a missing-record rule (unknown destination or unknown mention), headless seat or
   review ping, or any rule under observe or guarded, **Then** `Send now` is recommended;
   **Given** an approval tier rule under strict, **Then** `Keep as draft` is recommended.
3. **Given** the planner session asks that widget, **Then** the question guard accepts it,
   and after the answer the planner's `bin/wuwei drafts approve <id>` passes `protect_state`
   under guarded; a seat, another session, or an id the planner did not ask is refused.
4. **Given** `Send now` under strict, **When** the planner runs the record command,
   **Then** the guard refuses it with `Run it in a host terminal: bin/wuwei drafts approve
   <id>`, and the held tool call stays refused (as the same pending draft) until the owner
   runs it.
5. **Given** an unknown destination or unknown mention rule and `[outbound] learn` set to
   anything but `off` (#492), **Then** the `Send now` description adds that `bin/wuwei
   outbound learn` records the channel or person for later sends.

---

### User Story 3 - The approved draft goes out through the tool that drafted it (Priority: P1)

For a draft that came from an MCP tool or from a port whose adapter is `none`, `drafts
approve` lints the text as today, records the owner's answer, the time and the text hash, and
allows one tool call: the same tool (any tool for an adapter `none` draft), the same
destination and the same text hash, within `[outward] draft_ttl` seconds (default 3600). The
seat repeats the call; the guard lets it through once and records `draft.sent` with the id and
the tool. For a configured adapter, `drafts approve` sends through the adapter as today. The
host terminal confirmation stays under strict; under observe and guarded the recorded card
answer is the confirmation.

**Why this priority**: without it the owner's answer still changes nothing for a connector.

**Independent Test**: approve an MCP draft in process under guarded, then replay the same
`check_tier` payload twice.

**Acceptance Scenarios**:

1. **Given** the owner's `Send now` on the card for an MCP-tool draft under guarded,
   **When** `drafts approve <id>` runs, **Then** the row is `approved` with the answer, time,
   text hash and expiry and a `draft.approved` event; the same tool call then passes once
   with a `draft.sent` event naming the id and the tool, and a second identical call is
   drafted again with a new id.
2. **Given** an approved allowance, **When** the call differs in tool, destination or text,
   or comes after the expiry, **Then** it is drafted and the allowance is untouched.
3. **Given** a draft from a configured adapter channel, **When** `drafts approve <id>` runs,
   **Then** it sends through the adapter as today, with no y/N prompt under guarded and with
   the host confirmation under strict.
4. **Given** `Send with an edit`, **When** `drafts approve <id> --file <path>` runs, **Then**
   the file's text replaces the draft text, is linted, and is the text the allowance (or the
   adapter send) uses, with `edit_size` and `sent_unedited` recorded as for `--edit`.
5. **Given** a call carrying a canary or honeytoken, **Then** the allowance never lets it
   through (the security check runs before the tier and the allowance).

---

### User Story 4 - Docs say a draft is one card away (Priority: P3)

`docs/site/concepts.md` defines draft, rule, card and allowance; `docs/site/daily.md` gets one
paragraph that a draft is one card away from being sent; `docs/site/security.md` says the
floor is "the owner decides" and the card is how; `docs/site/configuration.md` and the
template document `outward.draft_ttl`.

**Independent Test**: the docs tests that already pin the site pages and the schema rows.

**Acceptance Scenarios**:

1. **Given** the site docs, **Then** each named page carries its sentence, the security page
   no longer says a held write "asks for a draft you send yourself", and no page has an
   em-dash or an emoji.

### Edge Cases

- A held call whose inputs `outward._text` rejects stays exit 2 as today; no draft is stored.
- The state write that stores the draft fails: the guard returns exit 2 with the existing
  "cannot read or validate policy" reason; nothing passes.
- Two identical calls race on one allowance: the consuming state write re-reads the row and
  requires `approved`, so one call passes and the other is refused with exit 2 (fail
  closed); a retry is drafted.
- An expired `approved` row is left as is; it never passes and never shows as pending.
- The allowance passes the tier guard, and the lint guard still runs on the same call; it
  sees the text `drafts approve` already linted, so its result is the same.
- `drafts show` for an unknown or no longer pending id exits 1 with the existing `_pending`
  message.
- `drafts approve` on an adapter `none` row after the owner configured a real adapter refuses
  as today ("adapter configuration changed").

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `outward.classify` MUST, when given a list in a new keyword `why`, append one
  `<rule>: <evidence>` string for every draft it returns, with `<rule>` one of `unknown
  destination <channel>`, `unknown mention @<name>`, `approval tier <tier> for <audience>`,
  `headless seat`, `review ping without a code-host link`. Its return value is unchanged.
- **FR-002**: `outward.check_tier` MUST return `(1, f'{APPROVAL_REQUIRED}: <rule>:
  <evidence>')` for a draft; every caller that compared the reason with `APPROVAL_REQUIRED`
  MUST compare by prefix.
- **FR-003**: The MCP outward guard and the port wrapper MUST store the held call as a
  pending draft (an MCP row records its tool) and refuse with `outward: draft <id>: <rule>:
  <evidence>; the owner decides: bin/wuwei drafts show <id> --widget`. An MCP call identical
  to a pending MCP draft reuses its id.
- **FR-004**: `bin/wuwei drafts show <id> [--widget]` MUST print the pending row, or with
  `--widget` the card of User Story 2; it is read-only.
- **FR-005**: The question guard MUST accept a question citing a draft id pending today, and
  the gate recorder MUST record that id for the planner session when the header is `Draft`.
- **FR-006**: `protect_state` MUST let today's planner session run `drafts approve <id>` and
  `drafts drop <id>` for ids it asked on a card, outside strict, and refuse every other
  caller as today; under strict it prints the command for a host terminal.
- **FR-007**: `drafts approve` MUST, for an MCP row or an adapter `none` row, record status
  `approved` with the answer, time, `text_sha256` and `expires`, and send nothing; for any
  other row it sends through the adapter as today.
- **FR-008**: `drafts approve` MUST call the host confirmation only under the strict
  posture.
- **FR-009**: `drafts approve --file <path>` MUST replace the draft's text fields from the
  file with the same validation as `--edit`.
- **FR-010**: The MCP outward guard MUST, for a call the tier holds, pass it once when an
  `approved` row matches its tool (or has none), destination and text hash before `expires`,
  marking the row `sent` with a `draft.sent` event `{id, tool}`.
- **FR-011**: `[outward] draft_ttl` MUST be an integer of seconds, default 3600, minimum 60.
- **FR-012**: No new module is imported on a hook path that does not hold a draft (#346).
- **FR-013**: Docs per User Story 4.

### Key Entities

- **Draft row** (`state.json` `drafts`, producer `wuwei drafts` and the outward guard and
  ports): gains `tool` (MCP rows), status `approved`, `answer`, `text_sha256`, `expires`.
- **Allowance**: an `approved` row; consumed by exactly one matching tool call.
- **Card**: the widget `drafts show <id> --widget` prints.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Five held calls with the five rules give five distinct reasons, each with a
  draft id and the widget command.
- **SC-002**: An MCP draft goes from held to sent with one card answer and one repeated tool
  call under guarded, and with one host terminal command under strict.
- **SC-003**: No hook path that holds no draft imports a module it did not import before.

## Assumptions

- The reason names the first rule classify meets, in classify's existing order (sensitive
  text, audience flags, recipients, external org, docs, tracker, thread, PR context,
  destination, review ping, safe forms); one rule per reason is enough to act on.
- `<evidence>` names the config key or fact that fired, never the matched message words, and
  never contains `; ` so `wuwei why` splits rule and fix at the first `; `.
- Tier words: `sensitive`, `commitment`, `disagreement`, `direct message`, `external`,
  `thread`, `docs`, `tracker`, `review ping`, `review gate`, `unclassified`, `unresolved
  commit`. `<audience>` is `voice.audience` of the destination, or the channel kind when the
  call names no destination.
- `review ping without a code-host link` fires at the unclassified fallback when the text
  mentions review; a text in the full review-request shape whose mentions differ from the
  PR's requested reviewers is `approval tier review ping`, and a failed review gate is
  `approval tier review gate` with the gate's first clause as evidence.
- `Send now` is recommended for every rule except an approval tier rule under strict (the
  issue says "never for a tier rule under strict"; it does not forbid it elsewhere).
- The card's `record` field is the `Send now` command; the other options name their command
  in their description, because a widget carries one record command (#359).
- One confirmation rule for both approve paths: the host confirmation runs under strict
  only. Under observe and guarded only the owner at a host terminal or the planner after a
  card answer can reach `drafts approve` (`protect_state`, records floor), so the card answer
  is the confirmation. Existing tests that relied on the prompt under the default posture
  set strict.
- An adapter `none` draft has no tool to repeat, so its allowance matches any tool with the
  same destination and text hash; the owner approved that text to that destination.
- The allowance check runs after the security check and after classify, at the point the
  tier would refuse, so a call classify sends is untouched and the clean path imports
  nothing new. "Before the tier check" in the notes is read as before the tier refusal.
- Duplicate pending drafts are folded only for MCP rows; port drafts keep today's one row per
  call, because the tracker and docs callers count them.
- `draft_ttl` is in seconds, like `sessions.stale_seconds`.
- `drafts show` without `--widget` prints the pending row as JSON, like `wuwei drafts` does
  for the queue.
- The security page says the floor as "You decide", since the site pages address the reader
  (#362); the refusal text keeps "the owner decides".
- A held tool row accepts any tool name `outward.tool_patterns` can match (letters, digits,
  `_`, `.`, `-`), not only `mcp__` names, so a configured custom tool is stored too.

## Deferred

- Writing `outbound.work_channels` or `outbound.people` from the card answer belongs to #492
  (`outbound learn`); this item only names that command on the card when #492's
  `[outbound] learn` key is present and not `off`.
- `pr act` drafts (`cli/wuwei/pr_actions.py`) keep `APPROVAL_REQUIRED` as their stored reason
  with no rule; passing `why` there is a follow-up if the owner asks.

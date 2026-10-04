# Feature Specification: a message to the owner's own DM or user id is never a draft: the owner's identity per channel is learned on the first card and the send passes under every posture

**Feature Branch**: `495-owner-dm`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #495, "fix(outward): a message to the owner's own DM or user id is
never a draft: the owner's identity per channel is learned on the first card and the send
passes under every posture". Owner, 2026-10-04, on 0.15.0 and 0.16.0: "I also have problems
with sending myself DMs in Slack."

## Root cause (read and reproduced on main, edc10e7, read-only)

Reproduction: the notes name no dry-run workspace, so a scratch workspace in a temp directory
(owner name, `outbound.work_channels = ["C1"]`) ran `wuwei.outward.classify` and
`wuwei.outward.check_tier` in process for a Slack send of "Your build is green" to `D01`, to
`U01`, and to `D01` with `is_dm`. Every call returned `(1, 'draft')` with the rule
`approval tier direct message for D01: every direct message drafts` (or `U01`), and
`check_tier` returned `outward: deliver as a draft for the owner to send: approval tier direct
message for D01: every direct message drafts`. `workspace.SCHEMA['outbound']` has no `owner`
key, and the fixture connector name
`mcp__00000000-0000-4000-8000-000000000001__slack_send_message` matches no built-in
`outward.tool_patterns` rule on main (that half is #492).

1. **Every D or U destination drafts.** `cli/wuwei/outward.py:338-344` (`classify`): any
   destination starting with `D` or `U`, `is_dm`, or `channel_type` `im`/`mpim` returns
   `tier('direct message', 'every direct message drafts')`. Nothing before that rule asks
   whether the destination is the owner, so a message the owner sends to their own DM through
   a Slack connector is always a draft the owner then approves to send to themselves.
2. **The MCP path knows nothing about the owner.** The owner's DM is known only to the adapter
   path, through the `SLACK_OWNER_DM_CHANNEL` environment variable (`remote.dm` at
   `cli/wuwei/remote.py:182-198`, `drafts.destination` and `drafts.approve` at
   `cli/wuwei/drafts.py:66` and `:235`). That variable is the DM between the owner and the
   WUWEI app, which the listener reads; it is not the owner's own DM as seen by a connector
   that acts as the owner, and the hook does not load it. `outbound` config has no owner
   identity at all.
3. **The rule is not named in the #493 shape.** The DM draft reason says `approval tier direct
   message for <id>: every direct message drafts`, not which recipient was unknown.
4. **The outward lint treats the owner's own DM as third-party text.** The guard's lint
   (`cli/wuwei/guards/outward.py:52-56` to `outward.check_lint`, `cli/wuwei/outward.py:484-497`)
   never passes `to_owner`, so a message to the owner that names the owner trips the
   third-person rule; `remote.dm` already passes `to_owner=True` for the same reason.

## User Scenarios and Testing

### User Story 1 - A message to the owner goes out (Priority: P1)

The planner (or the owner's session) sends the owner a Slack message through a connector,
addressed to the owner's own DM channel or the owner's user id. It goes out at once, under
observe, guarded and strict, after the security check and the outward lint, with one
`outward.to_owner` event. It is never a draft and never reaches the drafts queue.

**Why this priority**: it is the owner's report; every message WUWEI sends the owner through
a connector is held today.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k to_owner`.

**Acceptance Scenarios**:

1. **Given** `outbound.owner.slack = {user = "U01", dm = "D01"}` and a
   `mcp__<uuid>__slack_send_message` call with `channel = "D01"` through a fixture UUID
   connector, **Then** the guard passes it with one `outward.to_owner` event and no draft row,
   under observe, guarded and strict.
2. **Given** the same config and the same call with `channel = "U01"`, **Then** the same.
3. **Given** the same config and a call with `recipient = "U01"` and no channel, **Then** the
   same; with `recipients = ["U01", "U02"]` it is a draft.
4. **Given** the same send whose text names the owner (`Pat, your build is green`), **Then**
   the lint does not refuse it as a third-person reference; a text with an emoji is still
   refused by the lint.
5. **Given** a message to the owner whose text holds a sensitive keyword or a commitment,
   **Then** it still goes out: those tiers protect other people, not the owner.

### User Story 2 - The owner's identity is learned on the card (Priority: P1)

With no `outbound.owner.slack`, a DM to the owner is held back as today, the reason names the
rule and the learn command, and the planner's `bin/wuwei outbound learn` (#492) adds the
owner's identity, read from the connector's own identity call, to the one card the owner
answers. After `Approve`, the same send goes out.

**Why this priority**: the owner's principle from #492: nothing is typed by hand.

**Independent Test**: `python -m pytest -q tests/test_outbound_learn.py -k owner`.

**Acceptance Scenarios**:

1. **Given** no `outbound.owner` and the send of Story 1, **Then** it is a draft whose reason
   holds `unknown DM recipient D01` and names `bin/wuwei outbound learn --tool <tool>`.
2. **Given** that reason, **When** the planner runs `bin/wuwei outbound learn --tool <tool>`
   with no files, **Then** the printed listing step names the identity tool (`auth_test`,
   `users_me`, `whoami` or the tool whose name says identity or profile) and `--owner <file>`.
3. **Given** `--owner` with `{"user": "U01", "dm": "D01"}`, **Then** one decision record and
   one card whose question names the identity (`your identity U01, DM D01`), whatever
   `outbound.learn` and the posture are (an owner identity is never learned without the card).
4. **Given** `Approve` is recorded, **Then** `outbound.owner.slack.user = "U01"` and
   `outbound.owner.slack.dm = "D01"` are written, the `outbound.learned` event says the owner
   was learned, and the send of Story 1 passes with the `outward.to_owner` event.
5. **Given** `Defer: keep as drafts`, **Then** nothing is written and the send stays a draft.

### User Story 3 - Every other DM keeps today's rule, with the rule named (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_outward.py -k dm_recipient`.

**Acceptance Scenarios**:

1. **Given** `outbound.owner.slack` recorded and a DM to another user id `U02`, **Then** a
   draft as today, and the reason is `unknown DM recipient U02: not the owner's DM or user id
   in outbound.owner.slack` with no `outbound learn` way out.
2. **Given** an `is_dm` call to `C1`, **Then** a draft with `unknown DM recipient C1: ...`.
3. **Given** the adapter `chat.dm` port (no destination in its inputs), **Then** a draft with
   today's reason (`approval tier direct message ...`), unchanged.

### User Story 4 - The owner reads WUWEI where they said (Priority: P2)

With `[outbound] owner_channel = "dm"`, the planner posts the digest, the day report and the
nudges to the owner's DM through the connector, addressed to `outbound.owner.slack.dm` (else
`outbound.owner.slack.user`), so they pass as messages to the owner.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k owner_channel`.

**Acceptance Scenarios**:

1. **Given** the plan and report skills, **Then** they say what to post to the owner's DM when
   `outbound.owner_channel` is `dm`, and to run `outbound learn` first when
   `outbound.owner.slack` is not set.
2. **Given** a workspace with no `owner_channel`, **Then** the loaded value is `session`.

### User Story 5 - Setup records the identity when no connector is present (Priority: P3)

`wuwei setup` proposes `outbound.owner.code_host` from the measured code-host login and
`outbound.owner.mail` from the repositories' commit email, and `wuwei setup slack` proposes
`outbound.owner.slack.user` from the pinned owner, each only when unset, in the digest the
owner already confirms.

**Independent Test**: `python -m pytest -q tests/test_setup.py -k owner_identity`.

**Acceptance Scenarios**:

1. **Given** a measured login `pat-example`, a repository identity email
   `pat@example.test` and no `outbound.owner`, **Then** `setup.identity` returns the two
   settings; with both already set it returns neither.
2. **Given** `setup slack` pins `T01/U01`, **Then** its settings include
   `outbound.owner.slack.user = "U01"`; it never writes `SLACK_OWNER_DM_CHANNEL` into
   `outbound.owner.slack.dm`.

### Edge Cases

- A Slack send with a nested `draft` wrapper is never treated as a message to the owner.
- A send to the owner's DM plus another destination or recipient is not a message to the
  owner and follows today's rules.
- An identity file whose `user` is not `U...`/`W...`, whose `dm` is not `D...` or empty, or
  whose `dm` equals `SLACK_OWNER_DM_CHANNEL` (the app DM the listener reads as owner input) is
  refused by `outbound learn` with exit 1 naming the shape.
- The learn card proposes only identity fields that are empty in config; it never replaces a
  recorded identity.
- A connector whose owner mode (#492 `outward.modes`) is `draft` drafts every write,
  messages to the owner included; `refuse` refuses them.
- The headless shepherd seat rule (`WUWEI_SEAT_ROLE=shepherd`) stays first in `classify`.
- `outbound.owner.code_host` is identity only: a code-host write is public (a pull request or
  issue), so it never passes as a message to the owner.

## Requirements

### Functional Requirements

- **FR-001**: `outbound.owner` holds the owner's identity per channel class:
  `slack = {user = "", dm = ""}`, `mail = ""`, `code_host = ""`, all empty by default.
- **FR-002**: `outward.owner_only(context, config, kind)` is true when the call has at least
  one destination or recipient, no nested `draft` wrapper, and every destination
  (`channel`, `channel_id`), every `recipients` item and `recipient` is one of the owner's
  identities for the kind (`chat` and `slack`: `outbound.owner.slack` user and dm; `mail`:
  `outbound.owner.mail`), compared casefolded. Other kinds are never to the owner.
- **FR-003**: `outward.classify` returns `(0, 'send')` for an owner-only call, after the
  headless shepherd rule and the input checks and before the sensitive, commitment and
  disagreement tiers and the DM rule.
- **FR-004**: The DM rule names `unknown DM recipient <id>: not the owner's DM or user id in
  outbound.owner.slack` (the first destination, else `recipient`); with no destination and no
  recipient it keeps today's `approval tier direct message` reason.
- **FR-005**: `outward.check_tier` appends one `outward.to_owner` event
  (`{"channel": <kind>}`) when it lets an owner-only call through. The kind is reserved (only
  the outward hook and port write it) and silent in the attention tiers.
- **FR-006**: `outward.check_lint` lints an owner-only call with `to_owner=True`, as
  `remote.dm` does; every other lint rule still applies.
- **FR-007**: In the guard's draft reason, a `D`/`U` destination counts as not known yet (so
  the reason names `bin/wuwei outbound learn --tool <tool>`) only while
  `outbound.owner.slack.user` or `.dm` is empty and `outbound.learn` is not `off`.
- **FR-008**: `bin/wuwei outbound learn` takes `--owner <file>` for a Slack connector: a JSON
  object with exactly `user` and `dm`; the proposal carries the fields that are empty in
  config; an owner identity always goes through the card; `Approve` and the `Approve, mode
  <mode>` options write `outbound.owner.slack.<field>`, `Approve channels only` and
  `Defer: keep as drafts` do not. The listing step names the identity tool and `--owner`
  while the identity is incomplete.
- **FR-009**: `outbound.owner_channel` is `"session"` (default) or `"dm"`. The plan and report
  skills post the digest, the nudges and the day report to the owner's DM when it is `dm`.
- **FR-010**: `wuwei setup` proposes `outbound.owner.code_host` and `outbound.owner.mail`;
  `wuwei setup slack` proposes `outbound.owner.slack.user`; each only when empty.
- **FR-011**: No new import on the hook path (#346); `CONFIG_CACHE_VERSION` is bumped.
- **FR-012**: `docs/site/configuration.md`, `docs/site/security.md`, the workspace template
  and the two skills document the above.

### Key Entities

- `outbound.owner`: `{slack: {user, dm}, mail, code_host}`, strings, empty when unknown.
- `outbound.owner_channel`: `"session"` or `"dm"`.
- `outward.to_owner` event: `{"channel": "slack" | "chat" | "mail"}`; no ids, no text.
- #492 learn proposal: gains `owner: {user?, dm?}` (only the fields to write).

## Success Criteria

- **SC-001**: The owner's scenario, a Slack DM to themselves through a UUID connector, goes
  from a held draft to sent, with one card answer the first time and nothing after.
- **SC-002**: A DM to anyone else stays a draft and its reason names `unknown DM recipient`.
- **SC-003**: The full suite passes, including the #346 import tests and the #362 and #493
  reason tests.

## Assumptions

- A1 This item builds on #492 (`outbound learn`, `guards.outward.resolve`,
  `outward.unknown_audience`, `outward.modes`), which is not on main at edc10e7. Stories 1, 3,
  4 and 5 do not need it except for the UUID connector name in the guard-level acceptance
  tests; Story 2, FR-007 and FR-008 extend #492's code. The worktree is brought up to a main
  that holds #492 before those tasks (tasks.md, checkpoint).
- A2 The owner pass sits before the sensitive, commitment and disagreement tiers, not only
  before the D/U rule: "never a draft" for a message to the owner, and those tiers exist to
  protect other people. The security check (`security.outbound`, before `classify`) and the
  outward lint still run, so it is not a bypass of the lint.
- A3 The headless shepherd rule stays first: it is about the seat, not the audience.
- A4 The card learns only the Slack identity: the owner's report is Slack, and the mail and
  code-host identities come from setup's measured login and commit email. A mail connector
  card can take `--owner` later if a mail send to the owner is reported.
- A5 `code_host` identity has no pass rule: every code-host write is public.
- A6 The adapter `chat.dm` port keeps today's behaviour: its inputs carry no destination, and
  `remote.dm` already sends to the owner without a draft. Only the MCP path changes.
- A7 `SLACK_OWNER_DM_CHANNEL` is the app DM the listener reads as owner input; a post there by
  a connector acting as the owner would read back as an owner command, so it is never
  recorded as `outbound.owner.slack.dm`.
- A8 "Never counted against the approval tier" means no draft row, no `draft.*` event and no
  hold: the call passes before the drafts queue, and `outward.to_owner` is a separate silent
  kind that no draft metric reads.
- A9 An owner mode (#492 `outward.modes`) of `draft` or `refuse` is the owner's explicit
  choice for the connector and wins over the owner pass; "every posture" is about postures.
- A10 The `outward.to_owner` event is recorded where `check_tier` decides, so a connector in
  owner mode `send` (which skips `check_tier`, #492) sends without it.
- A11 Slack user ids are `U...` or `W...` (Enterprise Grid), DM ids `D...`, as in
  `remote.PIN`.

## Deferred

- Mail identity on the learn card (A4).

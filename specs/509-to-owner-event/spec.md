# Feature Specification: a message to the owner records outward.to_owner under every connector mode

**Feature Branch**: `509-to-owner-event`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #509: fix(outward): a message to the owner sent under connector mode
send writes the outward.to_owner event like every other owner message. Left open by #495
(spec A10): with a connector in mode `send`, a self-DM went out without the
`outward.to_owner` event that the draft and refuse paths write. Deliver: the owner-identity
check writes the event on every path, including mode `send`; one test per mode.

## Root cause

The gap A10 describes was real when #495 landed (commit e6c65d6). The MCP guard,
`cli/wuwei/guards/outward.py` `_check`, then switched on the connector's mode before the
tier policy ran: `found == 'send'` called `outward.check_send` (lines 189-190 at e6c65d6),
and only `outward.check_tier` called `owner_only` and appended `outward.to_owner`. A
self-DM through a connector in mode `send` therefore skipped the event; modes `draft` and
`refuse` reached `check_tier`, where the owner pass ran first and recorded it.

#496 (commit 7347b4d, PR #512) removed that switch. On the worktree base (327dd57):

- `cli/wuwei/guards/outward.py:175-176`: every resolved MCP write calls
  `outward.check_tier(inputs, root, config, channels, tool=tool)`, whatever the mode.
- `cli/wuwei/outward.py:401-402` (`table`): `outward.modes` is the first row of the tier
  table, read inside `classify`.
- `cli/wuwei/outward.py:600-601` (`classify`): `owner_only` returns `send` before the table
  is walked, so no mode row can hold or refuse a message only the owner reads.
- `cli/wuwei/outward.py:760-763` (`check_tier`): the shared owner-identity check appends
  `outward.to_owner` with `{'channel': kind}` on every pass that reaches it.

A reproduction on the base (guard `check_tier` and `check_lint`, connector in each mode, a
send to the owner's DM `D01`) records exactly one event per mode. No production code is
wrong today. What is missing is the guarantee: `tests/test_outward.py`
`test_guard_to_owner_floor` (line 1641) covers modes `draft` and `refuse` only, and no test
runs a self-DM through a connector in mode `send`. A later change that brings back a fast
path for `send` (the shape #492 had) would drop the event silently.

## User Scenarios and Testing

### User Story 1: every message to the owner is counted, whatever the connector mode (Priority: P1)

A self-DM sent by a seat through a connector must leave the same silent `outward.to_owner`
event whether the owner set that connector to `send`, `draft` or `refuse`, so the day's
count of messages to the owner is complete.

**Why this priority**: it is the whole item.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k to_owner_every_mode`.

**Acceptance Scenarios**:

1. **Given** a workspace with the owner's Slack identity (`outbound.owner.slack.dm = "D01"`)
   and a claude.ai connector in `outward.modes` with mode `send`, **When** the seat sends
   `Your build is green` to `D01` through that connector, **Then** the guard's `check_tier`
   and `check_lint` both return `(0, '')`, `events.jsonl` holds exactly one
   `outward.to_owner` row with payload `{'channel': 'slack'}`, and no draft is stored.
2. **Given** the same workspace with the connector in mode `draft`, **When** the same call
   runs, **Then** the same result: exit 0 on both guards, one event, no draft.
3. **Given** the same workspace with the connector in mode `refuse`, **When** the same call
   runs, **Then** the same result: exit 0 on both guards, one event, no draft.

### Edge Cases

- A message to anyone else records no `outward.to_owner` event (already covered by
  `test_to_owner_event_and_lint`, where a send to `C1` adds none).
- Under the send umbrella (`outbound.default_tier = "send"`) a mode `draft` row drops out
  of the table (#533); the owner pass sits before the table, so the event is unchanged.
  Not a separate test: the three-mode test already pins the path.

## Requirements

### Functional Requirements

- **FR-001**: A message only the owner receives, sent through an MCP connector, records
  exactly one `outward.to_owner` event per call under each connector mode `send`, `draft`
  and `refuse`, from the one shared owner-identity check in `outward.check_tier`.
- **FR-002**: The connector mode never turns such a message into a draft or a refusal
  (unchanged from #495 A9).
- **FR-003**: One test per mode proves FR-001 and FR-002 through the PreToolUse guard.

### Key Entities

- `outward.to_owner` event: silent, reserved to `wuwei.outward.check_tier`
  (`cli/wuwei/commands/event.py`), payload `{'channel': <kind>}`. Unchanged.

## Success Criteria

- **SC-001**: the three-mode test passes on the base and fails if any mode's path stops
  reaching the owner check in `check_tier`.
- **SC-002**: the full suite passes with no production code change.

## Assumptions

- A1 The issue's premise (a mode switch before the owner check) no longer holds on main:
  #496 replaced it with the tier table, and `owner_only` runs before the table. The item
  therefore delivers the per-mode regression test and no code change. The orchestrator note
  "one event call moved above the mode switch" has no switch left to move above.
- A2 The test runs at the guard level (`wuwei.guards.outward.check_tier` and `check_lint`),
  the path a seat's connector call takes. Modes match only `mcp__<server>__` tool names, so
  the adapter port path (`outward.check_call`, no tool) is not affected by modes.
- A3 `remote.dm` (WUWEI's control-plane reply to the app DM) does not write the event; it is
  not a connector write and the event's producer is the outward hook and port. Out of scope.
- A4 The existing ponytail note in `check_tier` stays: the event is appended before
  `check_lint`, so a self-DM the lint refuses still counts. Not part of this item.
- A5 No docs change: `docs/site/security.md` and `docs/site/configuration.md` already say a
  message only the owner receives records `outward.to_owner` and goes under every posture;
  neither names a mode exception.
- A6 `tests/test_invariants.py` is absent on the base, so no invariant row is added.
- A7 No new refusal, rule or event kind (#530 and #551 are not touched).

# Feature Specification: read-only MCP tools are recognised by any word of their name, unknown tools warn under observe and guarded with the exact config line, and the built-in Slack write pattern covers add_message and friends

**Feature Branch**: `469-mcp-reads`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #469, "fix(outward): read-only MCP tools are recognised by any word of
their name, unknown tools warn under observe and guarded with the exact config line, and the
built-in Slack write pattern covers add_message and friends". Owner report from a Slack
triage session on v0.12.0, confirmed unchanged on the v0.15.0 asset.

## Root cause (read and reproduced on main, 963a839, v0.15.0)

Both outward guards (`check_tier` and `check_lint`) route through `_check` in
`cli/wuwei/guards/outward.py`. For a tool that no `outward.tool_patterns` rule matches:

- `cli/wuwei/guards/outward.py:85-95`: an `mcp__` tool counts as a read only when the first
  word of its name (split on `_` only), or the second word when the first is part of the
  server name, is one of `get list search read find fetch query describe view lookup`.
  Anything else falls through as a write.
- `cli/wuwei/guards/outward.py:106-107`: inside a workspace every such tool is refused with
  the bare `outward: configure outward.tool_patterns for this write tool`. Both guards
  return it, and `check_tier` is an owner-only check (`guards.OWNER_ONLY`), so it blocks in
  every posture.
- `cli/wuwei/workspace.py:187`: the built-in Slack rule is
  `mcp__.*slack.*__.*(send|post|reply|schedule|update).*`, so `conversations_add_message`
  matches no rule and gets the bare hint instead of the draft path.

Servers that name tools noun-first (`conversations_history`, `channels_list`,
`conversations_replies`) are therefore refused as writes. Reproduced read-only with a scratch
probe outside the repository that calls both guards in a fresh test workspace under each
posture (same outcome in observe, guarded and strict):

| tool | check_tier | check_lint |
|---|---|---|
| `mcp__slack__conversations_search_messages` | 2, bare configure hint | 2, same |
| `mcp__slack__conversations_history` | 2, bare configure hint | 2, same |
| `mcp__slack__channels_list` | 2, bare configure hint | 2, same |
| `mcp__slack__slack_search_messages` | 0 | 0 |
| `mcp__slack__slack_get_channel_history` | 0 | 0 |
| `mcp__slack__conversations_add_message` | 2, bare configure hint | 2, same |
| `mcp__slack__slack_post_message` | 1, `outward: deliver as a draft for the owner to send` | 0 |
| `mcp__acme__frobnicate` (unknown) | 2, bare configure hint | 2, same |

The draft refusal does not name the channel today, so `wuwei why last refusal` cannot show
it: the recorded target of an MCP call is the tool name and the rule is the bare draft text.

## User Scenarios & Testing

### User Story 1 - Read-only MCP tools pass whatever their word order (Priority: P1)

A seat in a workspace calls a read-only MCP tool named noun-first (`conversations_history`,
`channels_list`, `conversations_search_messages`). The outward guards let it through in
every posture.

**Why this priority**: it is the owner's outage: a read-only Slack triage could not run.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k "probe or recorded"`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace, **When** the PreToolUse hook runs for
   `mcp__slack__conversations_search_messages`, `mcp__slack__conversations_history`,
   `mcp__slack__channels_list`, `mcp__slack__slack_search_messages` and
   `mcp__slack__slack_get_channel_history`, **Then** each exits 0.
2. **Given** observe and strict, **Then** the same five exit 0.
3. **Given** the recorded tool-name lists of the common Slack, Linear and GitHub MCP servers,
   **Then** every read in them passes both guards, and every write either matches a built-in
   rule (draft path) or is refused with the filled-in config line; none is "unknown".
4. **Given** a name with a leading read verb and a write word (`mcp__gmail__get_message`),
   **Then** it still passes, as it does today.

### User Story 2 - Writes take the draft path and name the channel (Priority: P1)

A seat calls a Slack write tool, in either naming style. It is refused with the draft
reason and the channel, and the owner can see both in `wuwei why last refusal`.

**Why this priority**: a real write that falls to a config hint instead of the draft path
loses the approval tier's reason, and a noun-first server's writes are the common case.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k "probe or why"`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace, **When** the hook runs for
   `mcp__slack__conversations_add_message` and for `mcp__slack__slack_post_message` with a
   non-mechanical text, **Then** each exits 2 and the reason names the draft path and the
   channel `slack` (in observe and strict too: the approval tier is owner-only).
2. **Given** a refused write, **When** the owner runs `bin/wuwei why last refusal`, **Then**
   the output shows the channel and the draft path.
3. **Given** a write tool no rule matches (`mcp__acme__send_email`), **Then** it is refused
   in every posture with the filled-in config line, never the bare "configure
   outward.tool_patterns".

### User Story 3 - Unknown MCP tools follow the posture (Priority: P2)

A seat calls an MCP tool whose name has neither a read word nor a write verb
(`mcp__acme__frobnicate`).

**Why this priority**: today it blocks work in every posture with a hint that names no
command; the posture areas (#331, #347) say a warn-level finding passes and is recorded.

**Independent Test**: `python -m pytest -q tests/test_outward.py -k unknown`.

**Acceptance Scenarios**:

1. **Given** observe or guarded, **When** the hook runs for an unknown tool, **Then** it exits
   0, one `outward.unknown_tool` event is recorded for that tool today, and the event's
   reason (shown as a nudge by `bin/wuwei status` and `bin/wuwei nudges`) names the exact line
   `bin/wuwei config set outward.tool_patterns '[{pattern = "<tool>", channel = "<server>"}]'`
   with the tool and its server filled in.
2. **Given** the same unknown tool called again the same day, **Then** no second event is
   recorded.
3. **Given** strict, **Then** the hook exits 2 with the filled-in config line.
4. **Given** guarded with `security.areas.outward = "block"`, **Then** it refuses as under
   strict; with `"off"` it passes and records nothing.
5. **Given** a directory outside any workspace, **Then** an unknown tool exits 0 and nothing
   is recorded.

### Edge Cases

- camelCase and hyphenated names split into words: `chat_postMessage` is `chat post
  message`, `getConfluencePage` is a read, `sendEmail` is a write, `resolve-library-id` is
  unknown.
- Plural nouns are not write words: `conversations_search_messages` has `messages`, not
  `message`.
- An MCP tool name with a character outside `[A-Za-z0-9_-]` cannot come from Claude Code;
  where a config line would be built from it, the guard refuses with exit 2 and the payload
  family instead of printing it into a shell line.
- A built-in rule still wins over the name heuristic: the rules are matched first, as today.
- Non-MCP tool names keep today's behaviour (pass unless a rule matches).

## Requirements

### Functional Requirements

- **FR-001**: An unmatched `mcp__` tool is a read when today's leading-read test holds, or
  when none of its words is a write verb and at least one is a read word. It is a write when
  it is not a read and any word is a write verb. Otherwise it is unknown.
- **FR-002**: Words come from the part of the name after the last `__`, split on any
  non-alphanumeric character and on lower-to-upper case boundaries, lowercased.
- **FR-003**: The write verbs are the issue's list plus `save notify draft respond push fork
  request dismiss mark manage run`; the read words are the issue's list. Both are module
  constants with a table test.
- **FR-004**: An unmatched write is refused by both guards in every posture with the filled-in
  config line in the #362 shape. The bare "configure outward.tool_patterns" text is gone.
- **FR-005**: An unknown tool passes `check_tier`. `check_lint` reads the outward area level
  from `workspace.posture(config)`: `block` refuses with the filled-in config line; `warn`
  passes and records one `outward.unknown_tool` event per tool per day; `off` passes.
- **FR-006**: The built-in Slack rule becomes
  `mcp__.*slack.*__.*(send|post|reply|schedule|update|add_message|add_reaction|react|chat_post|delete|edit|upload|invite|kick|archive|pin|star).*`.
  The Linear and GitHub rules are reviewed against their recorded lists and stay unchanged.
- **FR-007**: The MCP guard's draft refusal names the channel and the draft path, so `wuwei
  why last refusal` shows both. The adapter ports keep `outward.APPROVAL_REQUIRED` unchanged.
- **FR-008**: No new import on the hook path for reads, writes or matched tools; the unknown
  branch may import `wuwei.watch` lazily, as `hook.newer_template` does.

### Key Entities

- `outward.unknown_tool` event: payload `{tool, posture, reason}`, at most one per tool per
  day; not in `commands/event.py` `FREE_KINDS`, so seats cannot forge it with `wuwei event`.

## Success Criteria

- **SC-001**: The seven probe tools give the issue's expected exits under observe, guarded and
  strict in hook tests.
- **SC-002**: The recorded Slack, Linear and GitHub tool lists classify with no read refused
  and no write unknown.
- **SC-003**: The full suite passes, including the #346 import tests and the #362 reasons test.

## Assumptions

- A1 The leading-read test from main is kept ahead of the any-word rule (a deviation from the
  issue's literal rule). Without it `get_message` (Gmail and similar) would contain the write
  word `message` and be refused, which is a regression against main.
- A2 The write verb list adds `save notify draft respond` (existing rows of
  `test_real_mcp_write_names` that must stay refused) and `push fork request dismiss mark
  manage run`, the verbs the recorded GitHub writes need (`push_files`, `fork_repository`,
  `request_copilot_review`, `dismiss_notification`, `mark_all_notifications_read`,
  `manage_notification_subscription`, `run_workflow`). Without them those writes would be
  "unknown" and pass under guarded, where main refuses them.
- A3 The unknown decision lives in `check_lint` (area `outward`, not owner-only), so the
  strict refusal carries the accurate posture line `posture: outward = block (set
  security.areas.outward)`. `check_tier` is owner-only and would claim no setting lowers it.
- A4 The channel in the filled-in line is the tool's server segment, lowercased (`slack` for
  `mcp__slack__...`, as in the issue). An unknown channel name always drafts in
  `outward.classify`, so the line is safe for any server.
- A5 `bin/wuwei config set outward.tool_patterns '[...]'` replaces the built-in rules, as
  `docs/site/configuration.md` says; the owner sees the diff and answers y/N. The issue names
  this exact line; making it append is out of scope.
- A6 There is no way to declare a misnamed read as a read; an unknown read under strict stays
  refused. Deferred.
- A7 Recorded tool-name lists are public API names of the servers as of 2026-10 (the
  korotovsky Slack server, the archived reference Slack server, the claude.ai Slack connector
  names already in the tests, the Linear MCP server and the GitHub MCP server). They are test
  data, not owner data.
- A8 "Exit 2 with the draft reason" in the issue is the hook's exit; the guard returns 1 and
  the hook turns every PreToolUse refusal into 2, as today.
- A9 The nudge is the `outward.unknown_tool` event itself: `signal.classify` already tiers an
  unlisted kind as `nudge` and `bin/wuwei status` shows its `reason`. No status or signal code
  changes. `hook.run` prints nothing for a passing PreToolUse call today, and this keeps that.
- A10 The dedupe is a read of today's events; two concurrent first calls may record twice.
- A11 The Bash `cd` refusal in the same owner report is bug #323, not this issue.

# Feature Specification: Slack inbound by polling mentions and DMs

**Feature Branch**: `050-slack-inbound`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #50, feat(adapters). Design section 15.2. Wave G (M5-lite): remote control
over one channel, Slack DMs polled with urllib. Notes (binding): poll
`conversations.history` for the owner DM channel and mentions, urllib only, cursor by
`ts`, dedup by event id, text through the redactor before storage, credentials from
`.wuwei/env` (#170), `config check` names them. Depends on #48 (merged, ce6c7cf) and #49
(merged, 493716a).

## Root cause (read on main, 493716a)

This is a new adapter, not a regression. What exists today and why it does not cover the
issue:

- `adapters/inbound/` holds only `none.py`, so `registry.known('inbound') == ['none']`.
  Probed read-only in a scratch workspace with `[adapters] inbound = "slack"`:
  `bin/wuwei config check` exits 1 and `bin/wuwei listen --once` exits 2, both with
  `adapters.inbound: unknown adapter 'slack'; known names: none`
  (`cli/wuwei/registry.py:69-74`, `validate`, reached from `workspace.load_config`).
- Everything downstream of the port already exists: `listen.tick`
  (`cli/wuwei/listen.py:32-63`) polls `inbound.poll(since)` with the per-source cursor,
  stores through `inbox.store` (`cli/wuwei/inbox.py:31-68`, which validates the
  normalised shape, dedups by `(source, id)` and redacts before writing) and sets the
  next cursor to the last returned event's `ts` (`listen.py:52`). That cursor moved only
  on polls that returned events, so a quiet owner pinned it and each poll re-read a
  growing backlog; review finding F1 changes `listen.tick` to move it on every
  successful poll to the newer of the last event's `ts` and the poll start epoch.
- The only Slack read today is `sent` in `adapters/chat/slack.py:45-71`: a bounded
  `conversations.history` page loop (100 per page, ten pages, 4 MB per body, error body
  refused) written inline for owner-voice learning. It has no `oldest` bound, no
  handling for HTTP 429 (a rate limit surfaces as `slack.sent: could not run:
  HTTPError`, with the `Retry-After` value lost), and it cannot be reused without
  copying.
- `wuwei config check` (`cli/wuwei/commands/config.py:27-32`) lists credential
  requirements for `chat.slack` only; an `inbound.slack` selection would print
  `no credential variables required`.

The notes for this issue name no dry-run failure; the probe above is the reproduction.

## User Scenarios & Testing

### User Story 1 - Mentions and DMs reach the inbox once (Priority: P1)

The owner selects `adapters.inbound = "slack"` and runs `wuwei listen`. Each poll reads
the owner DM channel and the workspace's work and external channels, and every message in
the DM channel plus every message mentioning the owner elsewhere lands in the inbox,
redacted, exactly once.

**Independent Test**: `python -m pytest -q tests/test_reference_adapters.py -k inbound`.

**Acceptance Scenarios**:

1. Given a recorded Slack `conversations.history` response with two mentions of the
   owner, when the listener polls, then two events are stored, and a second poll that
   receives the same response stores none (issue acceptance).
2. Given a message in the owner DM channel from the owner, then it is stored as an event
   with `source = "slack"`, the DM channel id, the sender's user id and the message `ts`.
3. Given a work or external channel message that does not mention the owner, or a
   mention written by the owner, then nothing is stored for it.
4. Given a bot message, an app message or a message with a subtype (join, bot post), in
   any polled channel, then nothing is stored for it.
5. Given a message holding a phone number, then the stored text has it replaced (the
   redactor from #48 runs in `inbox.store`, unchanged).

### User Story 2 - The poll resumes from its cursor and respects rate limits (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_reference_adapters.py -k inbound`.

**Acceptance Scenarios**:

1. Given a cursor `ts`, then every request carries `oldest` equal to the cursor's whole
   seconds minus 300; given no cursor (first poll), `oldest` is now minus 300.
2. Given messages from several channels, then the poll returns them oldest first by
   `ts`, so the listener's cursor becomes the newest.
3. Given Slack answers HTTP 429 with `Retry-After: 30`, then the poll exits 2 with a
   reason naming `rate limited` and `30`, nothing is stored and the cursor does not move;
   the next listener tick retries the same range.
4. Given an error body (`ok: false`), a malformed message row, a malformed cursor, or
   more than ten pages, then the poll exits 2 with the reason and nothing is stored.

### User Story 3 - Credentials come from `.wuwei/env` and `config check` names them (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k missing_and_set`.

**Acceptance Scenarios**:

1. Given `adapters.inbound = "slack"` and no Slack credentials, then `wuwei config check`
   names `SLACK_BOT_TOKEN`, `SLACK_USER_TOKEN` (one required) and
   `SLACK_OWNER_DM_CHANNEL`, reports them missing and exits 1; with them in `.wuwei/env`
   it reports `set` and exits 0, never printing a value.
2. Given a token or the DM channel is missing, then the poll exits 2 naming the variable
   and makes no HTTP request.

### Edge Cases

- A cursor that is not a Slack `ts` (digits, optionally `.` digits) is exit 2.
- The same message seen twice (lookback overlap, or a channel listed both as DM and work
  channel) is stored once: dedup is `inbox.store`'s, not the adapter's.
- Work or external channels are configured but `owner.handles` has no Slack user id:
  exit 2 naming `owner.handles`, before any request.
- No work or external channels: only the DM channel is polled; `owner.handles` is not
  needed.
- A mention written as `<@U123|name>` counts like `<@U123>`.
- A `thread_ts` on a message (thread parent or broadcast reply) becomes the event's
  `thread`; otherwise `thread` is empty.

## Requirements

### Functional Requirements

- **FR-001**: `adapters/inbound/slack.py` MUST implement `poll(since, *, root=None)`:
  read `conversations.history` for the channel in `SLACK_OWNER_DM_CHANNEL` and for each
  channel in `outbound.work_channels` and `outbound.external_channels`, with
  `oldest` = cursor (or now) minus 300 seconds, and return `Result(0, events)` oldest
  first.
- **FR-002**: An event MUST be the normalised shape `{id, source, channel, thread,
  sender, text, ts}` with `id = "<channel>/<ts>"`, `source = "slack"`, `sender` the
  Slack `user`, `thread` the `thread_ts` or empty, and the text unredacted (redaction is
  `inbox.store`'s).
- **FR-003**: Rows with `bot_id`, `app_id` or `subtype` MUST be skipped in every
  channel. In the DM channel every other row is an event; in the other channels only
  rows mentioning a Slack user id from `owner.handles` and not sent by one are events.
- **FR-004**: The page loop MUST be one shared function in `adapters/chat/slack.py`,
  used by both `chat.slack.sent` and `inbound.slack.poll`; `sent`'s results MUST not
  change.
- **FR-005**: HTTP 429 MUST fail the call with exit 2 and a reason carrying the
  `Retry-After` seconds (digits only, no provider text); no sleep and no retry inside
  the call.
- **FR-006**: Missing credentials MUST fail before any request; the token is
  `SLACK_USER_TOKEN`, else `SLACK_BOT_TOKEN`, as for `sent` and `dm`.
- **FR-007**: `wuwei config check` MUST name the `inbound.slack` credentials exactly like
  `chat.slack`'s connector requirements.
- **FR-008**: `listen.py`, `inbox.py`, the redactor, the chat port's `post` and `dm`,
  and the registry MUST not change.

### Key Entities

- **Slack inbound event**: `{id: "<channel>/<ts>", source: "slack", channel, thread,
  sender, text, ts}`.
- **Cursor**: the listener's per-source string (#49), here a Slack `ts`; the adapter
  reads it, the listener writes it.

## Success Criteria

- **SC-001**: The issue's acceptance scenario is one test that fails on main (unknown
  adapter) and passes after the change, through `listen.tick` and the real adapter with
  recorded HTTP.
- **SC-002**: No second copy of the Slack page loop exists; `sent` and `poll` share it.
- **SC-003**: The full suite passes with no existing test changed except the added
  config check row.

## Assumptions

- **Mentions are read with `conversations.history`, not `search.messages`.** The notes
  name `conversations.history`. `search.messages` would need a user token with
  `search:read` and has index lag that a `ts` cursor cannot survive.
- **Mention channels are `outbound.work_channels` plus `outbound.external_channels`.**
  They are already the workspace's chat channels, marked internal or external for 15.4;
  no new config key. Channel and sender allowlists are #52.
- **The owner's Slack user id comes from `owner.handles`** (bare chat ids matching
  `[UW][A-Z0-9]+`, the rule `obligations._owner_login` already uses to tell chat ids
  from code-host logins).
- **The DM channel is `SLACK_OWNER_DM_CHANNEL`,** the channel `chat.slack.dm` and the
  drafts queue already post to. Every human message there is inbound: it is the channel
  the owner answers drafts and decisions in (#57, #65).
- **WUWEI's own posts are not read back** because they carry `bot_id` or `app_id`
  (bot token, or an app posting with a user token). If a provider posts without either,
  the owner's DM drafts would be ingested as owner messages; they still only reach the
  inbox, nothing sends. Revisit if that is observed.
- **Top-level messages only.** `conversations.history` returns thread parents and
  broadcast replies, not replies inside a thread. A mention or a DM reply inside a
  thread is not seen; the owner answers in the DM as a new message. Thread replies
  (`conversations.replies`) are deferred.
- **One cursor for all channels, with a 300 s lookback.** The listener keeps one cursor
  per source (#49). Reading channels one after another can see a newer message in a later
  channel than a message that arrives meanwhile in an earlier one; re-reading 300 s
  behind the cursor covers that gap and `inbox.store`'s dedup makes the overlap free. The
  same lookback bounds the first poll: the listener does not replay history from before
  it started. A message older than the lookback that was missed during an outage before
  the first event is not recovered.
- **Rate limits.** WUWEI uses the workspace's own Slack app (connector or custom app), an
  internal app, for which `conversations.history` is Tier 3. Slack's 2025 limit of one
  request per minute applies to commercially distributed non-Marketplace apps and is not
  designed for here. A poll makes one request per channel per page; the listener polls
  every `listen.poll_seconds` (60 s default). A 429 fails that poll; the next tick is the
  retry. No backoff state is kept (`ponytail:` comment, upgrade path: persist a
  not-before time if 429s repeat).
- **Ten pages of 100 per channel per poll.** Beyond that the poll exits 2 (as `sent`
  does) and the cursor does not move, so it does not recover by itself. Because every
  successful poll moves the cursor to the poll start (F1), only more than 1000 messages
  in one channel between two successful polls (a long outage of the listener) reaches
  it. Marked `ponytail:` in `chat.slack.history`; upgrade path: return the oldest pages
  and let the cursor advance.
- **Credentials:** the same variables as the chat adapter, already in
  `env.CREDENTIALS`, so they load from `.wuwei/env` and stay out of seat environments
  with no change to `env.py`.
- **Required scopes** (documentation only): `channels:history`, `groups:history`,
  `im:history` for the token that reads; the app must be a member of the polled channels.

## Deferred

- Thread replies (`conversations.replies`): not in wave G.
- Sender and channel allowlists, per-sender rate limits: #52.
- Replies over Slack and the command vocabulary: #65; reply parsing: #57.
- Persistent 429 backoff and partial pages: only if observed.

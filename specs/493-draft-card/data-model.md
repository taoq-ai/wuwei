# Data model: held drafts, cards and allowances

All records live in the existing producer-owned `drafts` key of the day's `state.json`
(`state.STATE_PRODUCERS['drafts']`); `wuwei state set` and `wuwei event` already refuse it and
every `draft.*` kind.

## Draft row

Fields today: `id`, `channel`, `operation`, `adapter`, `destination`, `inputs`, `text`,
`created`, `tier_reason`, `audience`, `status`, `item`, `style`, and after a decision
`final_inputs`, `final_text`, `edit_size`, `sent_unedited`, `decided`, `closed`.

| Field | Change | Values |
|---|---|---|
| `operation` | new value | `tool` for a call held by the MCP guard |
| `adapter` | new value | `mcp` for a tool row; `none` rows already exist from ports |
| `tool` | new, tool rows only | the MCP tool name, full-matching `mcp__[A-Za-z0-9_-]+` |
| `channel` | wider for tool rows | the tool's outward channel from `outward.tool_patterns` (`slack`, `tracker`, `code_host`, `docs`, or an owner channel) |
| `tier_reason` | richer | `outward: deliver as a draft for the owner to send: <rule>: <evidence>` |
| `status` | new value | `approved`: an allowance waiting for its one tool call |
| `answer` | new, set by `drafts approve` | `Send now` or `Send with an edit` |
| `text_sha256` | new, set by `drafts approve` | sha256 hex of `final_text` |
| `expires` | new, `approved` rows | ISO time: `decided` plus `outward.draft_ttl` seconds |

Status transitions:

```
pending --drafts approve (adapter row)--> sending --> sent | failed
pending --drafts approve (mcp or none row)--> approved --matching tool call, before expires--> sent
pending --drafts drop--> dropped
approved --expires passes--> (unchanged; never matches again)
```

`read()` validation for `approved`: the send-record checks (`final_inputs`, `final_text`,
`edit_size`, `sent_unedited`) plus `answer in ANSWERS`, `text_sha256` of 64 lowercase hex and
`expires` readable by `datetime.fromisoformat`.

## Allowance match (the guard, one call)

An `approved` row matches a held MCP call when all hold:

- `row.get('tool')` equals the call's tool, or is absent (an adapter `none` row);
- `row['destination']` equals `drafts.destination(call inputs without is_dm, channel, 'tool')`;
- `row['text_sha256']` equals the sha256 of the call's joined text fields;
- `workspace.now()` is before `row['expires']`.

The consuming write re-reads the row and requires `approved`, so a row is spent once.

## Session gate record

`state.json` `sessions.<planner session>.gate_asked` (from #357) may now hold draft ids, added
by `record_gate` for an answered `Draft` card. `protect_state` lets that planner session run
`drafts approve <id>` or `drafts drop <id>` for those ids outside strict.

## Events

| Kind | Producer | Payload |
|---|---|---|
| `draft.created` | `drafts.create` (guard or port) | `{id, channel}` (unchanged) |
| `draft.approved` | `drafts approve`, allowance rows | `{id, tool}` (`tool` null for a `none` row) |
| `draft.sent` | the outward guard spending an allowance | `{id, tool}` |
| `draft.sent` | `drafts approve`, adapter rows | `{id, exit}` (unchanged) |

## Config

| Key | Type | Default | Minimum |
|---|---|---|---|
| `outward.draft_ttl` | int, seconds | 3600 | 60 |

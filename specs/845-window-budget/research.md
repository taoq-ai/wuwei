# Research: what each runtime exposes about its usage windows (#845)

Date: 2026-10-12. Versions checked: Claude Code 2.1.284, codex-cli 0.156.1, codex Claude Code
plugin (codex-companion) 1.0.6. Every check was read-only; no model run was spent.

## Verdict

| Runtime | Window usage and reset exposed? | Where | What WUWEI does |
|---|---|---|---|
| Claude Code | Yes, percent used and reset time for the 5-hour and 7-day windows | the status line command's stdin JSON, `rate_limits` | `wuwei status --line` (already the configured status line) saves the reading |
| Claude Code | No | hook inputs, CLI subcommands | not used |
| Codex | No in `codex exec --json` events | exec JSONL `turn.completed` carries tokens only | not used |
| Codex | Yes, percent used, window length and reset time | the session rollout file's `token_count` event, `rate_limits` | the codex runtime adapter reads it for the seat's thread |
| Both | Fallback when no reading exists | `seat.usage` token counts against a per-window token budget in config | estimate |

## Claude Code

### Status line input: exposed

The status line command receives a JSON object on stdin at each refresh. Since Claude Code
added plan windows to it, the object carries:

```json
"rate_limits": {
  "five_hour": {"used_percentage": 42, "resets_at": 1738425600},
  "seven_day": {"used_percentage": 18, "resets_at": 1738857600}
}
```

Sources:

- Claude Code docs, "Customize your status line" (code.claude.com/docs/en/statusline),
  available-data table: `rate_limits.five_hour.used_percentage` and
  `rate_limits.seven_day.used_percentage` are 0 to 100; `resets_at` is Unix epoch seconds.
  The page says `rate_limits` appears only for claude.ai Pro and Max subscribers (or behind a
  Claude apps gateway with a spend limit) and only after the first API response of the
  session, that each window may be absent on its own, and that Claude Code drops a window once
  its `resets_at` passes. It also says the status line refreshes when a window in the last
  data reaches its `resets_at`.
- The installed binary (2.1.284) builds that object in the status line input:
  `five_hour:{used_percentage:...,resets_at:...}`, `seven_day:{...}`, and `spend_limit` behind
  a gateway; `rate_limits` is set only when one of them exists.

WUWEI already installs `wuwei status --line` as the project's `statusLine` command
(`cli/wuwei/commands/init.py`, `_status_command`), but `cli/wuwei/commands/status.py` does not
read stdin today. Reading it there is the one place a Claude reading can come from.

Limits of this source: it is only as fresh as the planner session's last status line refresh;
API-key sessions (no plan) never get it; a reading is the account's whole use (the owner's
own sessions included), not WUWEI's share.

### Hooks: not exposed

No hook input carries plan usage. The closest is the `StopFailure` hook, which fires when an
API error such as `rate_limit` ended a turn (its `error` matcher values include `rate_limit`);
it says a limit was hit, not how much is left or when it resets. Not used.

### CLI: not exposed

`claude --help` (2.1.284) lists no usage subcommand. `/usage` is an interactive slash
command; there is no documented non-interactive form, and running a headless prompt to read
it would spend a turn. The SDK has a usage read (`rate_limits.limits` rows with meter kinds
such as `session` and `weekly_all`), reachable only from an SDK host, not from a plugin's
shell command. Not used.

### How WUWEI counts Claude tokens today

- `seat.usage` rows: builder rows from `commands/build.py` `record_result` (fed by the
  SubagentStop payload in `stopped`: `usage`, else `total_input_tokens`,
  `total_output_tokens`, `duration_ms`); second-opinion rows from `dispatch.opinion`. Claude
  gate sentinels get duration only (`dispatch._seat_usage`), so their tokens are unmeasured.
- `metrics.seat_tokens(events)` sums input plus output tokens per measured row.
- `dispatch.host` bounds CAP with `budget.tokens_per_day`: today's used tokens and the
  median per-seat tokens of the newest day with rows. No row names its runtime.
- The status line shows `seats <running>/<cap> by <bound>`; it shows no tokens.

## Codex

### `codex exec --json`: not exposed

The exec JSONL event set in the installed binary (0.156.1) is `thread.started`,
`turn.started`, `turn.completed`, `turn.failed`, `item.started`, `item.updated`,
`item.completed` and `error`. `turn.completed` carries `usage` with `input_tokens`,
`cached_input_tokens`, `output_tokens` (and reasoning tokens); no rate limit fields. The
issue's premise that Codex reports windows "in its JSON events" holds only for the session
rollout file below, not for exec's stdout.

WUWEI does not call `codex exec` anyway: `adapters/runtime/codex.py` runs the configured
`codex.command` (the codex plugin's `codex-companion.mjs`) with `task`, `status`, `result`,
`--json`. The companion talks to the Codex app-server and stores `rawOutput`, `threadId`,
`touchedFiles` and a summary; it stores neither token usage nor rate limits (no `usage` or
rate limit field anywhere in the companion scripts). The adapter's `if 'usage' in
result_data` branch therefore never fires today: Codex seat tokens are unmeasured.

### Session rollout file: exposed

Codex writes each thread to `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<time>-<threadId>.jsonl`
(`CODEX_HOME` defaults to `.codex` in the home directory). Every turn appends a `token_count` event whose payload
has `info` (`total_token_usage`, `last_token_usage`, `model_context_window`) and
`rate_limits`:

```json
"rate_limits": {
  "limit_id": "codex",
  "primary":   {"used_percent": 88.0, "window_minutes": 10080, "resets_at": 1791179367},
  "secondary": null,
  "plan_type": "pro",
  "rate_limit_reached_type": null
}
```

Sources: the binary's `TokenCountEvent { info, rate_limits }` and
`RateLimitWindow { used_percent, window_minutes, resets_at }` types, and the shape of the
newest local rollout file (keys only were read). On that account the primary window is the
7-day one (10080 minutes) and `secondary` is null, so window lengths vary by plan: a reading
is matched to a window by `window_minutes` (300 is the 5-hour window, 10080 the 7-day one),
never by `primary` or `secondary`. The app-server also offers `account/rateLimits/read` and an
`account/rateLimits/updated` notification, reachable only through a JSON-RPC client; not used.

The companion's stored result names the `threadId`, so the adapter can find the seat's own
rollout file and read its last `token_count` event after the seat finishes. The format is not
a documented contract: a missing file, an unknown shape or a parse error yields no reading,
never an error.

## Fallback: estimate

Where no reading exists (an API-key Claude session, no status line, a Codex rollout not
found), a window is estimated: the input plus output tokens of `seat.usage` rows of that
runtime inside the window, against a token budget for that runtime and window set once in
config. The estimated window starts at now minus its length and is taken to reset one window
length after its earliest counted row.

## Decisions taken from this research

1. Window names are the two the runtimes share: `five_hour` (300 minutes) and `seven_day`
   (10080 minutes). A Codex window of any other length is ignored.
2. One cache file, `.wuwei/windows.json`, holds the last reading per runtime and window
   (`used_percent`, `resets_at` as an ISO time). Two writers: `wuwei status --line` (Claude)
   and the CLI code that records a Codex seat's result (Codex). A reading whose reset has
   passed is ignored.
3. A reading tightens the estimate, never loosens it: used tokens are the larger of the
   counted `seat.usage` tokens and `used_percent` of the configured budget, and a reading at
   100 percent or more holds every launch on that runtime until its reset even when no budget
   is set.

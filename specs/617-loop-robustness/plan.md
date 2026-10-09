# Implementation Plan: loop robustness

**Branch**: `617-loop-robustness` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Five small changes on existing code: one brace in the `created` query, a reason helper in
`adapters/tracker/github.py`, a per-ticket catch in `metrics._lead_time`, a local fix-round
count that `steward.review` reads instead of `metrics.collect`, and the steward rows of
`next.step`.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new config
key, no new event kind, no new port operation.

## Constitution Check

- I stdlib: no new import beyond `wuwei.redact`, already used by adapters' callers.
- II exits: a failing lookup is still exit 2 with a reason; an errors body is never read as
  data (only its first message); a missing lead-time reading is `unmeasured`, never zero.
- III one behaviour one function: `metrics.fix_rounds` serves `collect` and `review`; the
  reason text lives in one `_error` helper for both transports.
- IV test first: each change starts with a failing test.
- V simplicity: no retry, no cache; `review` reads the day's events once.
- VII security: gh stderr never echoed (#602); the GraphQL message is redacted, one line and
  capped at 160 characters.

## Design

### adapters/tracker/github.py

- `created()`: the plain string closes three braces (`'createdAt}}}'`).
- `_error(value, variables)`: returns `Failure('GitHub error response' + ' for
  owner/name#number' (when the variables carry all three) + ': ' + first message)`. The
  message is the first `errors[i].message` string, `' '.join(text.split())`, through
  `redact.redact`, cut at 160 characters. Non-list errors or a non-string message give the
  bare text.
- `_query`: `raise _error(value, variables)` instead of the bare failure.
- `_gh`: on a nonzero exit whose stdout starts with `{`, parse it (a parse error gives `{}`)
  and use `str(_error(body, payload['variables']))` as the hint; the order of the status and
  scope hints is unchanged.

### adapters/_http.py

- `Failure` docstring: no provider body or stderr text; a GraphQL error's first message may be
  named (#617).

### cli/wuwei/metrics.py

- `_Unavailable(ValueError)`: raised by `_port` for a nonzero exit or an error-shaped body,
  with the same message as today and the adapter's reason on `.reason`.
- `_lead_time`: per ticket, `history` and `created` lookups in one `try`; `_Unavailable`
  records `unmeasured[ticket] = reason` and continues. The values are appended only once both
  lookups returned. Malformed data still raises. The result gains `unmeasured` only when it is
  non-empty; no leads stays `UNMEASURED`.
- `fix_rounds(events)`: `dict(Counter(...))` of fix phase changes; `collect` uses it.

### cli/wuwei/steward.py

- `review`: `events = metrics._events(workspace.day_dir(root))`; `None` returns `[]` as the
  `UNMEASURED` branch did; else `rounds = metrics.fix_rounds(events)`.

### cli/wuwei/commands/next.py

- `steward_running = any(seat['role'] == 'steward' and seat['status'] == 'running' ...)`.
- When not running: the due row as today; then the newest run only: `runs[-1]` launches when
  its brief stem has no seat.

### Docs

- configuration.md, `steward.every_tool_calls`: next launches the newest steward brief only,
  never while a steward seat runs.
- reference.md: the `steward.due` nudge waits while a steward seat runs; `bin/wuwei metrics`
  `lead_time.unmeasured`.
- adapters.md: a GraphQL error names the ticket and GitHub's first message.

## Tests

- `tests/test_tracker_adapters.py`: balanced queries in both port contracts (and Linear's);
  the errors reason on the token path (ticket, first message, one line, cap); the gh errors
  reason (stdout errors, no stderr text).
- `tests/test_outcome_metrics.py`: one of two tickets failing `created` measures the other
  with `unmeasured`; both failing is `unmeasured`; a malformed timestamp still fails collect.
- `tests/test_steward.py`: `review` records the third-fix-round note with `metrics.collect`
  and `registry.load` raising.
- `tests/test_next.py`: two unlaunched runs offer the newest; a running steward hides both
  rows; after it stops the due row returns.
- `tests/test_docs.py`: configuration.md names the newest-brief rule.

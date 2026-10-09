# Feature Specification: next and dispatch next survive a failing tracker lookup, and one fresh steward at a time

**Feature Branch**: `617-loop-robustness`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #617 (owner, 2026-10-09): wuwei v0.23.0 ran a full autonomous day under
Claude Code desktop and hit two loop bugs. (A) `wuwei next` and `wuwei dispatch next <item>`
failed with `github.created: could not run: GitHub error response` while `wuwei discover` and
doctor's tracker row read the same backlog and every recorded ticket was a valid
`owner/repo#N` issue. (B) Several steward seats ran at once, and stale steward briefs were
launched beside fresh ones. Keep both bugs in this one feature.

## Root causes

- **A**: in `adapters/tracker/github.py` `created()` the query is built from an f-string and
  a plain string. The f-string halves its doubled braces; the plain string `'createdAt}}}}'`
  keeps four closing braces. The query opens three and closes four, GitHub answers with a
  GraphQL parse error, and `_query` raises `Failure('GitHub error response')`. The replay
  tests never parse the query text. The loop reaches it through `dispatch.next_step` ->
  `steward.review` -> `metrics.collect` -> `metrics._lead_time` -> `_port(tracker.created,
  ...)`, which turns the failure into a `ValueError` for the whole collect, so one metric's
  network read blocked every gate step. `steward.review` uses only `fix_rounds_per_item`,
  a count over the day's local events.
- **B**: `steward.maybe_run_for_tool_calls` appends `steward.due` every
  `steward.every_tool_calls` trace lines counted across all seats. `next.step()` returned the
  steward-run row whenever `due` was set, even while a steward seat ran, and returned the
  first `steward.run` whose brief had no seat, oldest first. Each due run wrote a new brief,
  so next launched old briefs beside fresh ones and several stewards ran at once.

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which reason does a GraphQL error carry? A: `GitHub error response`, then `for
  owner/name#number` when the request's variables name a ticket, then `: ` and GitHub's first
  error message, whitespace collapsed to one line, passed through `redact.redact` and cut at
  160 characters. The gh path reads the same from stdout when gh exits nonzero and stdout
  holds a JSON object with `errors`: only the messages are read, never `data`. gh's stderr
  text and any credential still never appear (#602).
- Q: Is GitHub's error message allowed in a reason? A: Yes, the first GraphQL error message
  only. It names the failing lookup (`Could not resolve to an Issue with the number of 9.`),
  which is what the owner needs and what the bare `GitHub error response` hid. GitHub does not
  echo the token in it; the redactor and the length cap bound the rest. HTTP error bodies and
  gh stderr stay out.
- Q: Which lead-time failures leave one ticket unmeasured instead of failing the metric? A: A
  lookup that could not run: `tracker.history` or `tracker.created` returning a nonzero exit
  or an error-shaped body for that ticket. That ticket goes into `lead_time['unmeasured']`
  as `{ticket: reason}` and the others still measure; when none measures, `lead_time` stays
  `unmeasured`. A lookup that ran and returned malformed or inconsistent data (an unparseable
  timestamp, a merge before In Progress or before creation) keeps its `ADAPTER_DATA` error:
  a wrong answer is a defect to surface, not a missing reading. It no longer blocks the loop,
  because `steward.review` stops calling `metrics.collect`.
- Q: Can `steward.review` skip `metrics.collect`? A: Yes. `fix_rounds_per_item` is a count of
  `fix` phase changes in the day's `events.jsonl`. One function, `metrics.fix_rounds(events)`,
  computes it for both `collect` and `review`. With no events file, `review` returns no notes
  and skips the negotiation check, as it did when the metric was `unmeasured`. `steward run`
  still collects every metric for the brief.
- Q: Which steward brief does next launch when several are unlaunched? A: Only the newest
  `steward.run` brief. Older unlaunched briefs carry stale metrics and are never launched;
  their files stay on disk as a record.
- Q: What does next do while a steward seat runs? A: A seat record with role `steward` and
  status `running` is a running steward. Next then returns neither the steward-run row nor a
  steward launch and falls through to the other rows. The due flag is not cleared: it stays
  until the next `steward.run`, so the due row returns once the seat stops.

## User Scenarios and Testing

### User Story 1 - A gate step runs while one ticket's tracker read fails (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the GitHub tracker, **When** the port contract runs on the token path and on the
   gh path, **Then** every GraphQL query it sends has balanced braces and parentheses.
2. **Given** a GraphQL response with errors for `github.created('acme/app#9')`, **Then** the
   reason reads `github.created: could not run: GitHub error response for acme/app#9: <first
   message>`, on one line, at most 160 characters of message. **Given** gh exits 1 with that
   errors object on stdout, **Then** the reason reads `gh api graphql exited 1: GitHub error
   response for acme/app#9: <first message>` and holds no stderr text.
3. **Given** two tickets with merged PRs and the tracker's `created` failing for one, **When**
   `metrics.collect` runs, **Then** `lead_time` measures the other and carries
   `unmeasured: {<ticket>: <reason>}`. **Given** both fail, **Then** `lead_time` is
   `unmeasured`.
4. **Given** an item with three fix rounds today and `metrics.collect` failing, **When**
   `steward.review` runs (as `dispatch next` and `next` call it), **Then** it records the
   third-fix-round note and reads no adapter.

### User Story 2 - One fresh steward at a time (Priority: P1)

**Acceptance Scenarios**:

1. **Given** two `steward.run` events whose briefs have no seat, **Then** next offers a launch
   of the newest brief only.
2. **Given** a steward seat running, **Then** next returns no steward row for a due flag nor for
   an unlaunched brief.
3. **Given** the steward seat stopped and a `steward.due` after the last `steward.run`, **Then**
   the due row returns.

## Requirements

- **FR-001**: Every query `adapters/tracker/github.py` sends is balanced; a test checks every
  query of the port contract on both transports (and the Linear adapter's GraphQL).
- **FR-002**: `_query` turns an errors response into a reason naming the ticket from the
  variables and GitHub's first error message (redacted, one line, at most 160 characters);
  `_gh` does the same for a nonzero exit whose stdout is an errors JSON object.
- **FR-003**: `metrics._lead_time` records a ticket whose `history` or `created` lookup could
  not run under `unmeasured` with the adapter's reason and measures the rest.
- **FR-004**: `metrics.fix_rounds(events)` is the one count of fix rounds; `steward.review`
  reads it from the day's events and calls no adapter.
- **FR-005**: `next.step` launches only the newest `steward.run` brief and returns no steward
  row while a steward seat runs.
- **FR-006**: docs: configuration.md (`steward.every_tool_calls`), reference.md (the
  `steward.due` nudge, `bin/wuwei metrics` lead time) and adapters.md (the GraphQL error
  reason).

## Success Criteria

- **SC-001**: A gate step (`dispatch next`, `next`) never fails on a tracker or code host read.
- **SC-002**: A day's tool-call steward triggers yield at most one running steward, on the
  newest brief.

## Assumptions

- A seat record with `role = "steward"` and `status = "running"` is the running steward; a
  launched seat not yet recorded is outside this fix (next's three-returns rule covers it).
- A ticket with no In Progress entry still leaves `lead_time` unmeasured as today; only a
  lookup that could not run is per ticket.
- No guard or decision rule changes, so no design 9.2 invariant row.

## Deferred

- None.

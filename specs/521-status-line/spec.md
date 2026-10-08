# Feature Specification: status --line is one readable line, the detail moves to status

**Feature Branch**: `521-status-line`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #521: `status --line` is one readable line (counts, posture, running
seats by role, and the one thing to do now), the detail moves to `status`, and a stale hook
version says restart Claude Code in plain words. Builds on #477 (running seats in next and
status), #358 and #551 (next), #353 (restart detection), #227 (no plan yet).

## Root cause

The owner reads the line in a status bar, and the line carries every part any feature ever
added, in the order the features landed:

- `cli/wuwei/commands/status.py:325-362` (`line`) appends pages, nudges, posture, the restart
  sentence, loops, PRs changed, solo, watch, listen, health, trace gaps, every phase, seats with
  the cap bound and the goal split, every running seat with its item and start time
  (`:353-354`, `state.in_flight_text`), sessions, phone answers, reply and meeting. There is no
  width and no order by importance, so the terminal truncates the end of the line, and the one
  thing the owner should do (restart, answer the gate, answer a decision) sits in the middle or
  is not on it at all.
- `cli/wuwei/commands/status.py:46` makes `--line` or `--json` required: there is no plain
  `status` for the owner to read the detail the line should drop.
- `cli/wuwei/integrity.py:78` (`restart`) says what it measured, `plugin <old> running against
  template <new>: restart Claude Code`, with the action last.
- `cli/wuwei/commands/status.py:350-352` counts only builder seats and labels them by goal, so
  a lead or sentinel seat that is running shows only in the long `running` part.

## User Scenarios and Testing

### User Story 1: One line, the thing to do first (Priority: P1)

The owner glances at the status bar and reads, left to right, the one thing to do now (when
there is one), the work counts, then the attention counts. Nothing else, and it fits.

**Independent Test**: neutral day state in `tmp_path` (items `ITEM-1`.., seats by role), run
`wuwei status --line` and `status.line(data)` in process.

**Acceptance Scenarios**:

1. **Given** four running seats (`lead`, `arch`, `quality`, `security`) and hooks `0.12.0` and
   `0.15.0` still running against a newer installed plugin, **When** `status --line` runs,
   **Then** the output is at most 100 characters, starts with `WUWEI restart Claude Code:
   hooks 0.12.0 and 0.15.0 still running`, never ends in a partial word, and carries no item
   id and no start time.
2. **Given** an approved gate, no pending decision, no stale hook, **When** `status --line`
   runs, **Then** it starts with `WUWEI ` followed by the counts (phases, seats), for example
   `WUWEI planned 3/1 · gate 1/1 · seats 4/1 (lead, arch, quality, security) | pages 0 ·
   nudges 6 · observe`.
3. **Given** a proposed plan (`plan.md` written) and no gate approval, **Then** the line starts
   `WUWEI gate waiting`; **Given** no `plan.md` and no gate approval, **Then** it starts `WUWEI
   no plan yet` (the #227 contract).
4. **Given** an approved gate and a routed decision `D-7` with no owner outcome, **Then** the
   line starts `WUWEI decision D-7 waiting`.

### User Story 2: The detail is in status (Priority: P1)

The owner runs `wuwei status` and reads the same groups one per line, with what the line
dropped.

**Independent Test**: the same fixtures, `wuwei status` with no flag.

**Acceptance Scenarios**:

1. **Given** the four running seats and the stale hook of US1.1, **When** `wuwei status` runs,
   **Then** it exits 0, its first line is `WUWEI restart Claude Code: hooks 0.12.0 and 0.15.0
   still running (plugin <new> installed)`, and it has one `running <role> <item> <HH:MM>` line
   per running seat (four lines).
2. **Given** any day, **Then** `status` also shows the watch, listen and heartbeat health,
   sessions, phone answers, loops, PRs changed, solo, trace gaps, the next reply, the next
   meeting, the cap bound and goal split, and the plugin and template versions.
3. **Given** an unreadable day state, **Then** `status` prints `WUWEI ? unmeasured` and exits 2,
   as `status --line` does.

### User Story 3: The restart says what to do (Priority: P2)

**Acceptance Scenarios**:

1. **Given** another cached plugin version with a process marker, or a `template_version`
   newer than this plugin, **Then** `integrity.restart` returns `restart Claude Code: hooks
   <old> still running (plugin <new> installed)`, the versions joined as `a`, `a and b`, `a, b
   and c`; doctor's `.in_use` row carries the same text.

### User Story 4: A narrow status bar (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `status --line --width 60` and a line longer than 60, **Then** the seat roles are
   cut from the right into `+N more` (`seats 4/1 (lead, arch, +2 more)`, down to `seats 4/1
   (+4 more)`) before anything else is dropped.
2. **Given** a line still too long after the seat list is cut, **Then** whole parts are dropped
   from the right (work tokens first, then attention tokens, never now), never the first token, never
   inside a token.

### Edge Cases

- No seat running and the gate approved: `seats 0/<cap>` with no parentheses.
- A fast check in flight is not a seat: it is not counted in `seats`, and `status` lists it as
  `running checks <item> <HH:MM>` (unchanged `state.in_flight` rows).
- A first part longer than the width (an extreme version list with a tiny `--width`) is kept
  whole: the line never comes back empty.
- The fast path `status --line` (no `--width`) keeps skipping the parser (#346 budget).

## Requirements

### Functional Requirements

- **FR-001**: `status.line(data, width=100)` MUST print `WUWEI ` followed by up to three
  groups joined by ` | `, tokens within a group joined by ` · `: (1) the one thing to do now,
  when there is one; (2) work: each nonzero phase as `<phase> <count>/<cap>`, then `seats
  <running>/<cap> (<role>, ...)` when the gate is approved or a seat runs; (3) attention:
  `pages N`, `nudges N`, and the posture name when it is not `guarded`. Nothing else.
- **FR-002**: The one thing to do now MUST be, first match wins: the restart text without its
  parenthesis (`restart Claude Code: hooks <old> still running`); `gate waiting` (plan proposed,
  gate not approved); `no plan yet` (no plan, gate not approved); `decision <id> waiting` for
  the first routed decision with no outcome.
- **FR-003**: `seats` MUST count running seats of every role (from `data['running']`, rows whose
  role is not `checks`) and list their roles oldest first; items and start times MUST NOT be on
  the line.
- **FR-004**: When the line is longer than `width`, `line` MUST first cut the role list from the
  right into `+N more`, then drop whole tokens from the right until it fits, keeping the first
  token. No token is cut inside.
- **FR-005**: `status --line` MUST accept `--width <n>` (integer, default 100). The fast path for
  exactly `status --line` stays.
- **FR-006**: `wuwei status` with no flag MUST print the full status: the line's groups one per
  line (first line prefixed `WUWEI `, the now line with the full restart text), with the detail:
  one `running <role> <item> <HH:MM>` line per `state.in_flight` row, the cap bound and goal
  split, watch, listen, health, sessions, phone answers, loops, PRs changed, solo, trace gaps,
  reply, meeting, and `plugin <version> · template <version>`. Exit 0; `WUWEI ? unmeasured`
  and exit 2 on an unreadable day, like the line.
- **FR-007**: `integrity.restart` MUST return `restart Claude Code: hooks <old> still running
  (plugin <new> installed)` or `''`; doctor's `.in_use` row uses it unchanged.
- **FR-008**: `status --json` keeps every existing key and adds `plan` (plan proposed),
  `decisions` (routed ids without an outcome, route order), `plugin` and `template`.
- **FR-009**: Docs and the design spec say where each moved part now shows (`status`), and the
  line's new shape.

### Key Entities

- Status snapshot (`status.snapshot`): the one dict `line`, `full` and `--json` read.

## Success Criteria

- **SC-001**: The US1.1 fixture line is at most 100 characters and starts with the restart.
- **SC-002**: `status --line` stays within the status-line budget (`tests/test_hooks.py`
  latency test unchanged) and one pass over `events.jsonl`.
- **SC-003**: No new refusal, no new event kind, no new state key.

## Assumptions

- The `WUWEI ` prefix stays on the line and on the first `status` line: the remote `status`
  verb strips it and `WUWEI ? unmeasured` stays the failure line. "Starts with the restart
  line" means right after the prefix.
- Separators are the issue's: ` · ` inside a group, ` | ` between groups. Width counts
  characters (`len`); the middle dot is one column. The Python 3.11 runtime writes UTF-8 to the
  status bar (PEP 538/540 locale coercion).
- "Under 100 columns" is implemented as at most `width` characters, default 100.
- `seats N/CAP` counts running seats of every role against the builder CAP, as the issue's
  example `seats 4/1 (lead, arch, quality, security)` does. The builder split by goal and the
  cap bound move to `status`; design 5.3's "the status line names what bound it" becomes
  "`status` names what bound it".
- Watch, listen and heartbeat health leave the line: a dead watch or listener and a degraded
  heartbeat are already pages, so `pages N` carries them and `wuwei nudges` and `status` name
  them. Loops, phone answers, PRs changed, solo, trace gaps, sessions, reply and meeting move to
  `status`; their nudges still count on the line.
- Only one decision is named on the line (the first routed); the rest count as nudges.
- `gate waiting` needs `plan.md` in the day directory, the same fact `wuwei next` uses for its
  gate row.
- Truncation drops from the right because the issue orders the line by importance left to
  right.
- The remote `status` verb and the board keep calling `status.line` and get the new line.
- No `tests/test_invariants.py` exists on this base, so no invariant row is added.
- The design spec states the old line contents (5.2 availability, 5.3 cap bound, 5.8.2 loops,
  5.9 status line). This issue is the owner's own change to them, so the feature amends those
  sentences in the same change and cites #521, as earlier features did; the conflict is raised
  here, not resolved silently.
- Printing the middle dot to a stream that cannot encode it raises inside `status.run`; the
  CLI's `_call` turns that into exit 2 with the reason, so it still fails closed.

## Deferred

- None.

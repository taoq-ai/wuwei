# Feature Specification: delete nudges; warnings stay in the event log

**Feature Branch**: `801-nudges-out`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #801, part 4 of the #789 deletion pass: "Delete nudges: the `nudges` command, the nudge list and every writer of it, the status counts, the `[nudges]` config table and its template entry, and their tests. A would-be refusal or a warning stays in the event log, where `why` and the retro read it."

## Context

A nudge is a derived view, not a record. `status.scan` reads the day's `events.jsonl`, asks
`signal.classify` for a tier (`page`, `nudge`, `silent`) and keeps one row per open cause. On
top of that view sit: the `wuwei nudges` command; `nudges.mode` with `status.surfaced`, which
also invents `round.ready` and `close.ready` rows; the ageing and cap in `status._tidy`
(`nudges.ttl_hours`, `nudges.max_open`, the `nudges.dropped` row); the `nudges N` token on the
status line and in `status --json`; the doctor `nudges` row; the board's Attention table; the
`owner.verbosity.nudges` surface; and four rows that `scan` writes only for the list
(`decision.pending`, `decision.cruise`, `session.planner_stale`, `guards.shadow`). Each is a
list the model or the owner reads to decide what to do next. `wuwei next` already derives the
next action, so the list is process machinery and goes.

The events stay. Every producer keeps appending the same kinds to `events.jsonl`. The
classifier's `nudge` tier becomes `warn`: still apart from `silent` for the few counts that
read it (trace gaps, untraced subagents, phone answers, changed PRs), never a list, never on
the status line.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No nudge list anywhere (Priority: P1)

The owner and the planner no longer see or manage a nudge list. The status line counts pages
only; `wuwei nudges` does not exist; doctor has no `nudges` row; config has no `[nudges]`
table.

**Why this priority**: it is the issue.

**Independent Test**: `wuwei status --line` before the gate prints
`WUWEI no plan yet | pages 0`; `wuwei --help --all` lists no `nudges`; `workspace.SCHEMA` has
no `nudges`; the doctor day rows have no `nudges` name.

**Acceptance Scenarios**:

1. **Given** a day with a failed `tracker.call` and a `security.finding`, **When** the owner
   runs `wuwei status --line`, **Then** the line shows `pages 1` and no `nudges` token, and
   `status --json` has `pages` and neither `nudges` nor `nudges_mode`.
2. **Given** any workspace, **When** `wuwei nudges` runs, **Then** the parser refuses it as an
   unknown command.
3. **Given** a day with a page, **When** `wuwei doctor` runs, **Then** the page is a `fail` row
   whose fix is `wuwei next`, and there is no `nudges` row.

---

### User Story 2 - Warnings stay in the event log (Priority: P1)

Every event that produced a nudge is still appended, unchanged, to `events.jsonl`; the
classifier calls it `warn`. The counts that read warnings keep working: doctor `traces` and
`untraced subagents`, the `status` phone answers, changed PRs and trace gaps, and the
SessionStart phone-answer lines.

**Why this priority**: the issue keeps warnings where `why` and the retro read them.

**Independent Test**: three `traces.gap` and three `subagent.untraced` events give doctor
`3 gaps today` and `3 stopped with no seat today`, and `status.snapshot` `trace_gaps == 3`.

**Acceptance Scenarios**:

1. **Given** a `guard.would_refuse` event under `guarded`, **When** classified, **Then** the tier
   is `warn`; under `observe` it stays `silent`.
2. **Given** an overdue PR action, **When** the watch polls past the deadline, **Then** the
   `pr.action` event carries `tier: warn`, and `page` at twice the deadline.
3. **Given** today's state written before the upgrade with an action episode `tier: nudge`,
   **When** the watch polls, **Then** the episode is read, not refused.

---

### User Story 3 - Docs, charters and skills say nothing about nudges (Priority: P2)

**Why this priority**: issue acceptance; lower than behaviour.

**Independent Test**: `grep -rli nudge charters skills docs/site README.md templates hooks`
finds nothing.

---

### Edge Cases

- A `config.toml` that still has `[nudges]` or `owner.verbosity.nudges`: part 2 (#799) makes
  unknown keys warn under every posture and `init --upgrade` remove them. No migration here.
- An event whose payload says `tier: "nudge"` (a `pr.action` written today before the
  upgrade): `classify` maps an unknown payload tier to `warn`.
- `status --line` keeps its latency budget: `scan` loses the config read it did for
  `guards.shadow`, and nothing is added.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cli/wuwei/commands/nudges.py` is deleted; no module imports it.
- **FR-002**: `status.surfaced`, `status._tidy`, `workspace.nudge_mode`, `SCHEMA['nudges']`
  and the `nudges` entry of `workspace.SURFACES` are deleted.
- **FR-003**: `status.scan` writes no `decision.pending`, `decision.cruise`,
  `session.planner_stale` or `guards.shadow` row, and takes no `config` argument. It keeps the
  `decision.answered` row (read by the SessionStart lines and `status`).
- **FR-004**: `signal.classify` returns `page`, `warn` or `silent`; every former `nudge`
  return is `warn`. `status.scan` labels its own non-page rows `warn`.
- **FR-005**: `status.snapshot` drops `nudges` and `nudges_mode`; the status line attention
  group starts with `pages N` and has no `nudges` token.
- **FR-006**: doctor drops the `nudges` row; a page row's fix is `wuwei next`; the `traces` fix
  names the day's event log, not `wuwei nudges`.
- **FR-007**: `pr_actions` writes `warn` for an overdue action; its episode check accepts
  `silent`, `warn`, `page`, and a legacy `nudge` written before this change.
- **FR-008**: `integrity.workspace_check` labels a non-page change `warn:`.
- **FR-009**: the listener's PR-change DM reads `owner.verbosity.dm`.
- **FR-010**: every CLI message that named `bin/wuwei nudges` names a command that exists or
  the plain step to take.
- **FR-011**: `wuwei init --upgrade` no longer prints the `nudges.mode unset` notice; the
  template has no `[nudges]` table and no nudge wording.
- **FR-012**: charters, skills, `docs/site/*`, README and templates do not mention nudges.
- **FR-013**: the board's Attention table lists pages only; the dashboard and the SwiftBar
  menu show pages only. Part 5 deletes all three; until then they keep working.

### Key Entities

- **Attention row** (`status.scan`): `{tier: page|warn, source, lane, reason, count?, ts?}`,
  derived from the event log on every read and never stored.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rn nudge cli/wuwei` matches only the legacy tier read in `pr_actions.py`.
- **SC-002**: every touched test file passes with `python -m pytest -q <files>`.
- **SC-003**: no test is loosened: each removed assertion covered deleted code, and each kept
  behaviour keeps its test (scan folding, silent clearing, unreadable lines, count sums).

## Assumptions

Clarify pass, each answered with the recommendation:

- **Rename, not collapse.** Collapsing `nudge` into `silent` would zero the doctor `traces`
  and `untraced subagents` counts and the `status` phone-answer and changed-PR counts, which
  read non-page rows. Renaming the tier to `warn` keeps them with no new code. The issue's own
  word ("a warning stays in the event log") names it.
- **`round.ready` and `close.ready` go.** `wuwei next` already offers the fix round (an item
  in phase `fix` gets its build action) and the close (the `close` rows in `next.py`).
- **Stale planner.** The heartbeat `planner` probe fails on a stale planner and pages through
  `heartbeat: clock`; doctor has a `planner` row. The `session.planner_stale` row duplicated
  both.
- **Pending decisions.** `wuwei next` returns the first pending decision; `status --json`
  lists all of them under `decisions`. The messages that named `nudges --all` for open
  decisions name `bin/wuwei status --json`.
- **Obligation and thread refusals.** `nudges --all` never listed comment ids, so the two
  reply refusals in `obligations.py` say to reread the PR on the code host and retry.
- **Shadow.** The `guards.shadow` row goes; the doctor `posture` warn row keeps the same text,
  and the constant moves from `status.py` to `doctor.py`, its only reader.
- **Doctor page fix.** A page reason names its own fix; the fix column says `wuwei next`, the
  command the loop runs after any finding.
- **Docs.** The issue acceptance (docs do not mention nudges) wins over the pass rule "edit
  docs/site only where a test forces it". Mentions are removed or reworded at sentence level;
  part 24 rewrites the site.
- **Design spec.** Design 5.9 defines the `nudge` tier and other sections say "a nudge". #789
  is the owner's instruction for this pass, so this feature amends the design spec to match:
  5.9 renames the tier `warn` and records the deleted list, and every other passage that used
  the tier says `warn` or names the event, each marked "(owner, 2026-10-10, #789)".
- **Order.** Parts 1 to 3 merge first. If part 3 has not yet removed them,
  `commands/__init__.py` READ_ONLY/WRITES, `__main__.GROUPS`, `guide.py` and the
  `docs/site/agent.md` guide block lose their `nudges` entries here. Part 2 (#799) removes
  `[nudges]` from existing configs.
- **Parallel parts.** Parts 5 and 7 delete the board, dashboard, SwiftBar, listener and
  control plane. This feature edits them minimally so they work if it merges first; on a
  rebase after their deletion, the deletion wins.
- **Constitution 9.2 rule.** No guard or decision rule changes here (classification feeds no
  guard), so no invariant row is added.

## Deferred

- `warn` rows that nothing reads (for example the `watch: sweep` reply counts) stay in `scan`;
  part 22 replaces `scan` with derived state.

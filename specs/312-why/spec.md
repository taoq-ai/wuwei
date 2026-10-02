# Feature Specification: wuwei why: reconstruct from events why an item, decision or refusal happened

**Feature Branch**: `312-why`
**Created**: 2026-10-02
**Status**: Draft
**Input**: Issue #312, feat(cli). Design spec 3.3 (workspace and events), 5.8 (decision
framework, 5.8.1 cruise mode), 5.9 (cockpit, signals and briefings); builds on
`cli/wuwei/report.py`, `cli/wuwei/commands/report.py` and `status.py`, #281 (board tool),
#303 (owner verbosity), #308 (shadow mode and refusal targets), #114 (producer-only
events). Evidence: owner agreement 2026-10-02.

## Root cause (read on main, 6e55d81)

The orchestrator notes name no dry-run workspace; this is missing behaviour, read from code
and reproduced read-only in a scratch workspace:

- No command assembles the chain. `cli/wuwei/report.py:55-124` `build` lists merged, open
  and parked items without causes; `cli/wuwei/commands/status.py:31` `scan` classifies
  attention, not causes; `cli/wuwei/commands/board.py:116-140` `read` shows phase and gate
  verdicts only.
- Events carry no id. `cli/wuwei/state.py:154-158` `_append_event` writes
  `{kind, payload, ts}` and nothing else, so "traceable to an event id" needs a defined id
  (Assumption A1).
- A refusal does not record its guard or command. `cli/wuwei/commands/hook.py:177` writes
  `state.append_event('hook.refusal', {'reason': reason}, root)`. Reproduced: calling
  `hook.refuse('PreToolUse', 'force-push is refused', cwd=<scratch workspace>)` leaves the
  single line `{"kind": "hook.refusal", "payload": {"reason": "force-push is refused"}, ...}`.
  The guard module is known at `hook.py:77` (`refusals` holds `(module, message)` since
  #308) and the normalised, redacted command is computed for shadow events at
  `hook.py:111-114`, but `shadow` returns bare reasons (`hook.py:98-121`) and `refuse`
  (`hook.py:91`, `163-177`) receives only the joined text. Without them
  `why "last refusal"` cannot name the guard (issue acceptance 2).
- An owner answer does not record who decided. `cli/wuwei/commands/decision.py:130-133`
  writes `decision.decided` / `decision.reversed` with `{id, option, reversibility}`; the
  seat route (`decision.py:64-65`) carries `decided_by: seat` from `seat_outcome`. The
  owner event has no `decided_by`, so the chain would have to guess the decider.
- Every other step is already recorded by its producer: `plan.approved` / `state.import`
  (`plan.py:197-198`) and `plan.added` (`plan.py:259`), with the score in the day's
  `proposal.json` or in `discovery_candidates`; `gate.tiered` with tier and reasons
  (`dispatch.py:157`); `gate.received` with role, round and verdict, and the verdict file
  in `gate_verdicts` (`dispatch.py:315-328`); `decision.routed` and `decision.waited`
  (`decision.py:247`, `293`); `merge.auto` with the policy evidence (`merge.py:359`); and
  every state write's `phase_changes` (`state.py:223-227`), whose event kind names the
  producer (`commands/event.py` `EVENT_PRODUCERS`).

## User Scenarios & Testing

### User Story 1 - Why is this item where it is (Priority: P1)

The owner runs `wuwei why <item>` (or a PR ref linked to an item) and reads, one line per
step, how the item entered the queue, its gate tier and the rules that set it, each gate
verdict with its blocking findings, each decision with its decider, its phase transitions
with their producers, the merge with the policy check that cleared it, and what it waits on
now. Every line comes from a record; a missing record prints `not recorded`.

**Independent Test**: build a workspace day with recorded events, state, a decision record
and verdict files for one merged item; run `wuwei why <item>` and `--full`.

**Acceptance Scenarios**:

1. Given a merged item with `plan.approved`, `gate.tiered`, three `gate.received` events,
   a seat `decision.decided`, an owner `decision.decided`, phase transitions and a
   `merge.auto` event, when the owner runs `wuwei why <item>`, then the output lists the
   goal and score, the tier with its reasons, three verdict lines (arch, quality,
   security), each decision with its decider (`seat`, `owner`), the phase transitions with
   their producers, and the merge line naming the merge policy with the head, checks and
   approvals from the `merge.auto` evidence; exit 0 (issue acceptance 1).
2. Given the same item, when the owner runs `wuwei why <item> --full`, then every line
   built from an event ends with `event <YYYY-MM-DD>:<line>` naming the exact line of that
   day's `events.jsonl`, and lines with evidence files name their workspace-relative paths
   (`proposal.json`, verdict files, decision records, `state.json`).
3. Given a FIX verdict whose verdict file holds a `blocks: yes` finding, then that verdict
   line names the blocking finding's first line; a PASS verdict names none.
4. Given an item whose `gate.tiered` event is absent, then the output has the line
   `tier: not recorded`; the same holds for the queue entry, the gate verdicts, and the
   merge policy check of a merged item with no `merge.auto` event (issue acceptance 3).
5. Given `wuwei why owner/repo#7` where an item links that PR, then the output equals
   `wuwei why <that item>`.
6. Given an item recorded on an earlier day and carried into today, then the chain reads
   both days, oldest first.
7. Given an unknown item or PR ref, then the command exits 1 with the reason on stderr;
   given a corrupt `events.jsonl` line on a day it reads, then it exits 2 with the reason.

### User Story 2 - Why was that refused (Priority: P1)

After a refusal, the owner runs `wuwei why "last refusal"` (or a refusal's event id) and
reads the guard, the rule, the normalised command and the fix the message named.

**Independent Test**: refuse a PreToolUse Bash call through the hook in a workspace, then
run `wuwei why "last refusal"`.

**Acceptance Scenarios**:

1. Given a PreToolUse refusal recorded through the hook, then the `hook.refusal` payload
   holds the unchanged `reason`, `refusals` (one `{guard, reason}` per enforced guard, the
   guard being its module name) and `target` (the normalised command, redacted the same
   way as shadow events).
2. Given that event is the newest refusal, when the owner runs `wuwei why "last refusal"`,
   then the output names the guard, the rule (the message before its first `; `), the
   command and the fix (the message after its first `; `); exit 0 (issue acceptance 2).
3. Given a refusal message with no `; `, then the fix line says `not recorded`; given an
   older `hook.refusal` with only `reason`, then guard and command say `not recorded`.
4. Given an event id `<day>:<line>` that names a `hook.refusal`, then `wuwei why <id>`
   prints the same refusal; an id naming another kind, or no line, exits 1.
5. Given no recorded refusal, then `wuwei why "last refusal"` exits 1 with
   `no recorded refusal`.
6. Given the target cannot be computed or redacted, then the refusal is still recorded
   (without `target`) and still enforced.

### User Story 3 - Why was this decided (Priority: P2)

The owner runs `wuwei why D-<n>` and reads the question, the options with their weighted
scores, the weights, the margin, the class and level at the time, and who decided it.

**Acceptance Scenarios**:

1. Given today's valid `D-3` routed to the owner and answered with
   `wuwei decision outcome D-3 B`, then the `decision.decided` (or `decision.reversed`)
   payload carries `decided_by: owner`, and `wuwei why D-3` prints the options with
   scores, the recommendation, the weights, the margin, `class: not recorded` (no
   `Class:` line), `level: not recorded` and `decided: B by owner`.
2. Given a seat-routed `D-n`, then the decided line names `seat`; given a pending record,
   it says `decided: not recorded`.
3. Given `D-n` with no record today, then the command exits 1.

### User Story 4 - The board shows the same chain (Priority: P3)

**Acceptance Scenarios**:

1. Given a day with items, then the `wuwei_board` result's `structuredContent` holds
   `./why.json`, mapping each item to the lines `wuwei why <item>` prints at the owner's
   level.
2. Given a chain that cannot be read, then the board still answers and `./why.json` holds
   `{"unmeasured": <reason>}`; every existing board test passes unchanged.

### Edge Cases

- Outside a workspace: exit 2 with the reason (as `wuwei shadow` does).
- `wuwei why` never writes: no event, no state, no file.
- A `D-n` record named by an item that does not lint: its question is read from the
  `Question:` line or prints `not recorded`; the item chain does not fail on it.
- A refusal from two guards: one guard, rule and fix block per guard, in recorded order.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei why <target...>` (the words joined by one space) resolves the target
  in this order: `last refusal`; an event id `YYYY-MM-DD:<n>`; `D-<n>`; a PR ref
  `owner/repo#n`; otherwise an item name.
- **FR-002**: The item chain reads only recorded data: the day directories (oldest first,
  up to today) whose `state.json` holds the item, their `events.jsonl`, `proposal.json`,
  `decisions/D-*.md` and the verdict files `gate_verdicts` names. It prints fixed steps in
  this order: queued, tier, gate verdicts, decisions, phases, merge, now. Records inside a
  step keep event order.
- **FR-003**: A step with no record prints `<step>: not recorded`. Required steps:
  queued, tier, gate verdicts; merge when the item's phase is `merged`. Nothing is
  guessed: a decider, guard, command, fix, class or level that was not recorded prints
  `not recorded`.
- **FR-004**: Every line built from an event carries its event id `<YYYY-MM-DD>:<line>`
  (1-based line of that day's `events.jsonl`). At level `full` each line ends with
  `(event <id>; <paths>)`, or `(event not recorded; ...)` when no event; other levels print
  the line alone.
- **FR-005**: The level is `full` with `--full`, else `workspace.verbosity(config,
  'report')`; `brief` and `standard` render the same.
- **FR-006**: The hook records each enforced PreToolUse refusal with `refusals`
  (`[{guard, reason}]`) and `target` in the `hook.refusal` payload, `reason` unchanged.
  `target` uses the same redaction as `guard.would_refuse`; failing to compute it never
  drops the refusal record. No new event kind, no new state key.
- **FR-007**: The owner outcome writes `decided_by: owner` into its `decision.decided` /
  `decision.reversed` payload. No other producer changes.
- **FR-008**: The refusal view prints guard, rule, command and fix; the decision view
  prints the question, the options with scores and the recommendation (reusing
  `decision.present` at `brief`), the weights, the margin (5.8.1: the recommendation's
  score minus the best other option's score, over 10 times the sum of the weights, two
  decimals), class, level and decided.
- **FR-009**: Exit 0 when the view prints, 1 when the target has no record, 2 when a record
  cannot be read (through the CLI's exception handler).
- **FR-010**: The board tool adds `./why.json` to `structuredContent`; a failure there
  becomes `{"unmeasured": reason}` and never fails the board.
- **FR-011**: `docs/site/reference.md` lists `bin/wuwei why` in the commands table and
  documents the output, the event id and the new `hook.refusal` fields.

### Key Entities

- **Event id**: `<YYYY-MM-DD>:<line>`, the day directory name and the 1-based line number
  in its append-only `events.jsonl`.
- **Step**: text, event id or none, workspace-relative evidence paths.

## Success Criteria

- **SC-001**: For a merged item the owner names, from one command, the goal, tier, three
  verdicts, deciders and merge policy evidence, each with an event id under `--full`.
- **SC-002**: The last refusal names its guard and fix in one command.
- **SC-003**: No output line states a cause that is not in a record; every missing record
  reads `not recorded`.
- **SC-004**: The full suite passes and every `WUWEI_BENCH=1` hook budget holds (the hook
  change runs only on the refusal path).

## Assumptions

- **A1**: Events have no id field; the event id is `<day>:<line>`. `events.jsonl` is
  append-only (constitution III), so the id is stable. No id is added to events.
- **A2**: A refusal id is the event id of a `hook.refusal` or `guard.would_refuse`
  event. `last refusal` is the newest of either across day directories up to today. A
  shadowed refusal is explained the same way, from its `guard`, `reason` and `target`,
  under the header `would have refused (shadow) at <ts>`.
- **A3**: Guard messages carry no structured rule or fix. The rule is the message before
  its first `; ` and the fix is the text after it; with no `; ` the fix is
  `not recorded`. This splits the recorded text and adds nothing to it.
- **A4**: The guard name is its module name, as `guard.would_refuse` records it.
- **A5**: `D-n` ids are per day; `why D-n` reads today's record only (as
  `wuwei decision show` does). Older decisions appear in their item's chain.
- **A6**: Cruise mode (5.8.1) has no writer on main. Class comes from a `Class:` line when
  the record has one; level comes from a recorded `decided_by` of the form
  `cruise <class>@L<n>`; otherwise both print `not recorded`. Margin is arithmetic on the
  record's own scores as 5.8.1 defines it.
- **A7**: The verbosity surface is `report`; no new surface or config key. `--full`
  overrides it.
- **A8**: Traces are not read: they hold tool spans, and no step the issue lists needs
  them.
- **A9**: Clarification records (`C-n`) are not decisions and are not listed.
- **A10**: An item's decisions are the `D-n` records of each of its days whose
  `Question:` or `Context:` names it (`decision.naming`), its `decision` field, and its
  external `assumption`; decision events also match on `payload.item`.
- **A11**: "What it waits on now" comes from the newest day state: phase and status; for a
  parked or escalated item its `decision` or `not recorded`; otherwise a waiting external
  assumption or the PR's recorded watch action when present, else nothing more.
- **A12**: Records written before this change stay readable and print `not recorded` for
  the new fields.

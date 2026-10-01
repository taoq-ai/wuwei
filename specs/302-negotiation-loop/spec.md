# Feature Specification: Mandate block in briefs, assume-and-record, time-boxed external waits, ask metrics, and a negotiation-loop nudge per work item

**Feature Branch**: `302-negotiation-loop`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Issue #302, feat(team). Implements the #301 amendment: design spec 5.2 (Briefs),
5.3 (Assume and record, Negotiation budget), 5.8 (Enforcement, ask metrics), 5.8.1 (class
table), 5.8.2 (External waits and negotiation loops), 5.9 (tiers, status line). Builds on
#279 (interview), #282 (cruise classes and levels, designed, auto-answering not built:
#283), #288 (steward metrics), #297 (listener DM nudges). Evidence: owner request
2026-10-01 for an observability ping when agent-to-agent negotiation ping-pong happens on a
work item.

## Root cause (read on main, deff8c0)

The orchestrator notes name no dry-run workspace; this is missing behaviour, so the cause is
read from the code the amendment governs:

- `cli/wuwei/brief.py:14-18` `launch_prompt` returns only the brief reference and the
  "Read instructions" line. No seat prompt says what the seat may decide, so a cautious seat
  asks. `adapters/runtime/codex.py:47-48` builds its own prompt with the same gap.
- `charters/_common.md:27-28` sends every decision through a record and never mentions
  `Assumptions:`; `charters/_common.md:21` still states the cycle budget ending in "an owner
  decision", not the 5.3 design reconsideration.
- `cli/wuwei/guards/decision.py:99-150` `check_question` guards only `AskUserQuestion`
  (`cli/wuwei/guards/__init__.py:23-24`). A Claude subagent, a Codex job or a headless
  shepherd that ends its turn with a question to the owner is not flagged.
- `cli/wuwei/verdict.py:57-85` `finding_blocks` does not start a finding at an
  `Assumption:` line, so a verdict whose only finding is an assumption is refused with "no
  finding with severity".
- `cli/wuwei/commands/decision.py:19-21` `route` has no way to mark an external
  confirmation on an item; `cli/wuwei/watch.py:201-263` `sweep` has no time box; there is no
  `decisions.wait_hours` key (`cli/wuwei/workspace.py:39-148`, no `decisions` table).
- `cli/wuwei/steward.py:20-37` `review` sees only a third fix round. Nothing counts records,
  verdicts, re-dispatches and fix-round continuations per item in a window; no
  `negotiation.loop` event, tier (`cli/wuwei/signal.py:26-89`), DM (`cli/wuwei/listen.py:40-61`)
  or status-line part (`cli/wuwei/commands/status.py:251-271`) exists.
- `cli/wuwei/metrics.py:498-576` `collect` has no owner asks per item and no unnecessary asks.

## User Scenarios & Testing

### User Story 1 - Every seat prompt carries its mandate (Priority: P1)

A builder, sentinel, lead, shepherd or steward launched by WUWEI reads in its prompt what it
decides alone, what it decides and records, and what goes to the owner, generated from the
5.8.1 class levels and the owner's interview answers, closing with "Nothing else is a
question."

**Independent Test**: `brief.launch_prompt` on a workspace with default config, then with
`decisions.cruise.levels.approach = 1`, then with `decisions.cruise.enabled = false`.

**Acceptance Scenarios**:

1. Given a builder brief for an item with class levels, when its launch action is built,
   then its prompt contains the mandate block with the three lists ("Decide alone:",
   "Decide and record:", "Go to the owner:") and the closing rule "Nothing else is a
   question."; the first line is still `WUWEI brief: <path>`.
2. Given the default levels, then `approach` is assume-and-record, `retry`, `park`,
   `accept-residual` and `merge` are under "Decide and record", and `defer`, `scope-cut`,
   `re-plan`, `dependency-bump`, `message` and `other` are under "Go to the owner".
3. Given `decisions.cruise.levels.approach = 1`, then the assumption sentence is gone and
   `approach` is listed under "Go to the owner"; given `decisions.cruise.enabled = false`,
   every class is under "Go to the owner".
4. Given a promoted interview `risk` line in `.wuwei/charters/lead.md` and a non-empty
   `deploy.deny`, then "Go to the owner" names the trust-surface areas and the commands.
5. Given a config `decisions.cruise.levels.merge = 4`, `levels.message = 2` (above its
   ceiling L1) or `levels.unknown = 1`, then `wuwei config check` refuses it.

### User Story 2 - A seat question without a record is flagged in every runtime (Priority: P1)

**Independent Test**: SubagentStop payloads through the guard and the hook shim; the Codex
`result` and the headless shepherd with recorded outputs.

**Acceptance Scenarios**:

1. Given a WUWEI seat stopping with a last message that asks the owner a question and cites
   no decision id, then SubagentStop flags it (guard exit 1, hook `decision: block` with the
   citation hint), and the planner's next action names the missing record: `wuwei dispatch
   next <item>` refuses with a steward note whose text names the missing decision record.
2. Given the same message citing `D-1` whose record passes the lint, then the stop is clean;
   citing a `D-9` that does not exist, it is flagged (exit 2: the shared citation check fails
   closed on an unreadable record).
3. Given `stop_hook_active` true, a non-WUWEI agent type, or a cwd outside any workspace,
   then the guard returns 0 and writes nothing.
4. Given a Codex job result or a headless shepherd turn whose text asks the owner a question
   without a decision id, then the Codex `result` returns exit 1 with the hint and the
   shepherd turn finishes with exit 1.

### User Story 3 - Assume and record is reviewable (Priority: P1)

**Acceptance Scenarios**:

1. Given a gate verdict `Verdict: FIX` whose only finding is an `Assumption:` line with
   severity, `file:line`, `blocks: no|yes` and a failure scenario, then the verdict lint
   accepts it; an `Assumption:` finding without a failure scenario is refused as
   `finding 1: missing failure scenario`.
2. Given any gate brief written by `wuwei brief`, then its header tells the sentinel to
   review the item's `Assumptions:` (spec and PR body) as findings of kind `Assumption:`.

### User Story 4 - External confirmation never holds reversible work (Priority: P1)

**Acceptance Scenarios**:

1. Given a valid decision record `D-n` asking for a confirmation from a person outside the
   loop, when a seat runs `wuwei decision route D-n --external <item>`, then the record is
   routed to the owner (whatever its reversibility and blast radius), the item carries
   `assumption: {kind: external, decision, day, since, status: waiting}`, and
   `wuwei dispatch next` and `wuwei build next` for that item are not refused because of it.
2. Given that external-confirmation decision past `decisions.wait_hours` weekday hours in
   `owner.timezone` without an owner answer, on a two-way door (record `Reversibility:
   two-way`, item goal not `unplanned`, item flag `trust_surface` false), when the watch
   sweep runs, then the item's assumption becomes `confirmed` per the recommendation and a
   `decision.waited` event records it; the record stays pending with the owner.
3. Given the same on a one-way door (or `unsure`, an `unplanned` item, or a
   `trust_surface` item), then the sweep parks the item (`phase: parked`, `status: blocked`,
   `decision: D-n`) and a `decision.waited` event records it; the owner's answer resumes it.
4. Given an answered record, or fewer weekday hours than `wait_hours` (a weekend does not
   count), then the sweep changes nothing.

### User Story 5 - The owner hears about negotiation loops once (Priority: P1)

**Acceptance Scenarios**:

1. Given an item with two fix rounds opened today (two `build.fix_opened` events), or seven
   exchanges (records naming it, gate verdicts, re-dispatches, fix-round continuations) in
   the last four hours with `steward.loop_threshold = 6`, when `steward.review` runs (on the
   sweep or on `dispatch next`), then one `negotiation.loop` event is written naming the
   counts and the last two exchanges, `wuwei nudges` lists it as a nudge, the listener DMs
   the summary once (`negotiation.notified`), and `status --line` shows `loops 1`.
2. Given a second trigger for the same item the same day, then no second event, nudge or DM.
3. Given the item's goal date (`memory/goals.md`) is before today, then the event is a page.
4. Given the defaults (window 4, threshold 9), then nine exchanges raise nothing and ten
   raise one event.
5. Given `control_plane.content = "none"`, then the DM says only that an update is waiting.

### User Story 6 - Ask metrics (Priority: P2)

**Acceptance Scenarios**:

1. Given owner-routed decisions D-1 (its `Question:` names item `alpha`), D-2 (`Context:`
   names `alpha` and `beta`) and D-3 (names no item), then `metrics.collect` gives
   `asks_per_item == {'alpha': 2, 'beta': 1, 'day': 1}`.
2. Given D-1 answered by the owner with its routed recommendation and D-2 answered with
   another option, then `unnecessary_asks == 1`; with no day state both are `unmeasured`.
3. Given the report and the retro, then both carry `asks_per_item` and `unnecessary_asks`.

### User Story 7 - Producer-only state, docs and charters (Priority: P1)

**Acceptance Scenarios**:

1. Given `wuwei state set` on `negotiation_loops` or `items.A.assumption`, or `wuwei event`
   with `negotiation.loop`, `negotiation.notified` or `decision.waited`, then each is
   refused naming its producer (the #114 meta-test rows).
2. Given the docs, then `concepts.md` (decisions and negotiation), `daily.md` (what the owner
   sees), `reference.md` (`decision route --external`, the events) and `configuration.md`
   (the `[decisions]` section and the two steward keys) describe the shipped behaviour, and
   every paragraph that names cruise mode still says it is not built.
3. Given the charters and the planner skill, then the mandate, assume-and-record and the
   negotiation budget are each stated once; `wuwei agents check` reports no drift.
4. Given the full suite, then guard, mutation and hook-level tests pass.

### Edge Cases

- A question inside a fenced code block or a quote is not a question (verdict
  `active_text`). A seat that is told once (SubagentStop block) and stops again is not
  flagged twice (`stop_hook_active`).
- A Codex job or headless turn has no seat reservation to resolve an item, so no steward
  note is written; the flag is the command's exit 1 with the hint.
- A seat stop that cannot be bound to a seat (no brief reference) is still flagged; the note
  is skipped because no item is known.
- Re-dispatch counts a `brief written` for an (item, role) that already had a brief earlier
  today; the first brief of each role is not a re-dispatch. The steward's own `day` briefs
  are not items.
- Build-loop fast-check continuations (`build.checked`) are not counted (5.3 bounds them).
- An item imported from yesterday keeps its `assumption`; the wait keeps counting from
  `since`. An answer recorded on a later day than the record is not seen by the sweep
  (records and outcomes are per day); see Assumptions.
- An unreadable `memory/goals.md` makes a loop a nudge, never silent and never a page.
- The listener sends nothing without `SLACK_OWNER_DM_CHANNEL`; a DM refused by the outward
  lint falls back to a fixed line that names only the item.

## Requirements

### Functional Requirements

- **FR-001**: `brief.mandate(root)` builds the mandate block; `brief.launch_prompt` appends
  it after the "Read instructions" line; the Codex dispatch prompt appends the same block.
- **FR-002**: Class levels: one table of the 5.8.1 classes with default and ceiling; the
  effective level is 0 when `decisions.cruise.enabled` is false, else the lower of the
  default and `decisions.cruise.levels.<class>`. The config check refuses an unknown class
  or a level above the ceiling.
- **FR-003**: A SubagentStop guard in `cli/wuwei/guards/decision.py` flags a WUWEI seat's
  last message with an uncited question through the existing `check_question`; on exit 1
  with a known item it adds a steward note through the steward's note writer. The Codex
  `result` and the headless shepherd use the same check.
- **FR-004**: `dispatch.next_step`'s steward-note refusal includes the note text.
- **FR-005**: The verdict lint starts a finding at an `Assumption:` line; gate brief headers
  carry one line telling sentinels to review `Assumptions:` as findings.
- **FR-006**: `wuwei decision route D-n --external <item>` routes to the owner and sets
  `items.<item>.assumption`; the watch sweep applies `decisions.wait_hours` (default 24,
  weekday hours in `owner.timezone`) and writes `decision.waited`.
- **FR-007**: `steward.review` counts per item in `steward.loop_window_hours` (default 4)
  and raises at a sum above `steward.loop_threshold` (default 9) or a second fix round today;
  one `negotiation.loop` event per item per day through state key `negotiation_loops`.
- **FR-008**: `signal.classify`: `negotiation.loop` is a page when its payload's
  `past_goal` is true, else a nudge; `negotiation.notified` is silent; `decision.waited`
  is a nudge.
- **FR-009**: `listen.notify` DMs each `negotiation.loop` summary once.
- **FR-010**: `status.scan` counts the day's `negotiation.loop` events in its single pass;
  `status.line` shows `loops N` when N > 0.
- **FR-011**: `metrics.collect` returns `asks_per_item` and `unnecessary_asks`; the report
  and retro show them through their existing metrics dump.
- **FR-012**: New state keys and event kinds are producer-only; `charters/_common.md`,
  `skills/wuwei-plan/SKILL.md`, the generated agents, the config template and the four docs
  pages change as in plan.md.

### Key Entities

- **Mandate block**: text, three labelled lists and a closing line; no state.
- **Item assumption**: `items.<item>.assumption = {kind: 'external', decision: 'D-n', day:
  'YYYY-MM-DD', since: ISO time, status: 'waiting'|'confirmed'|'parked'}`.
- **Negotiation loop**: `negotiation_loops.<item>` and the `negotiation.loop` event payload
  `{item, counts: {records, verdicts, redispatches, continuations}, fix_rounds,
  window_hours, last: [two strings], past_goal, reason}`.

## Success Criteria

- **SC-001**: Every issue Acceptance bullet maps to a passing test named in tasks.md.
- **SC-002**: `python -m pytest -q` passes; `wuwei agents check` exits 0.
- **SC-003**: `status.scan` still reads `events.jsonl` once.
- **SC-004**: No new module; no new dependency; the core never imports `subprocess`.

## Assumptions

- Design spec wins over the issue text (constitution): `steward.loop_threshold` defaults to
  9 as merged in #301 (its review raised it from the issue's 6). The issue's "seven exchanges
  in four hours" acceptance is tested with `steward.loop_threshold = 6` in config; the
  default is tested with nine (no event) and ten (one event).
- The issue's fifth loop signal, owner asks, is counted as the decision and clarification
  records naming the item (5.8.2, #301 assumption), so it is not counted twice.
- Records naming an item are today's `decisions/D-*.md` and `decisions/C-*.md` whose
  `Question:` or `Context:` line contains the item id as a whole word (option tables are
  skipped, so an option id never reads as an item); their time is the file mtime. Records are
  seat-writable, which is acceptable because the loop signal only reports and the
  negotiation budget, not this signal, stops rounds. `asks_per_item` uses the
  producer-only `decision_routes` for which records are asks and the record text only to
  attribute them; records naming no item count under `day`.
- Cruise auto-answering (#283) is not built. The mandate reads levels from
  `decisions.cruise.enabled` and `decisions.cruise.levels.<class>` with the 5.8.1 defaults;
  the running level (`memory/cruise.json`) does not exist yet, so the default stands in for
  it. `margin`, `max_per_day` and `undo_minutes` stay with #283. "Decide and record"
  records are routed by today's `wuwei decision route`, unchanged.
- The interview inputs are the durable, promoted ones: the `- risk:` line in the
  `## Owner preferences (interview)` block of `.wuwei/charters/lead.md` and `deploy.deny`
  (where the `manual` answer lands). Today's unpromoted `interview.json` is not read.
- A question is a line of the message's active text (fences and quotes removed) ending in
  `?`. False positives cost one SubagentStop continuation and are marked with a `ponytail:`
  comment.
- The planner's next action is `wuwei dispatch next`, which already refuses on a pending
  steward note; `wuwei build next` is unchanged (the SubagentStop block already sends the
  builder back to write the record).
- External confirmation is marked by the seat with `route --external`; there is no `Class:`
  field yet (#283), so the external flag is what makes it a `message`-class decision, which
  always goes to the owner (ceiling L1).
- "No other 5.8.1 ceiling applies" is measured by the item: goal not `unplanned` (outside
  the goals) and flag `trust_surface` false (trust boundary). "Scope agreed with other
  people" has no recorded signal; a seat that sees it should not mark the record two-way.
- Confirming the reading writes the assumption status and an event only; the record stays
  pending with the owner and no draft is sent (4.9). Parking reuses the external record as
  the item's decision, so `wuwei decision outcome` resumes it on the record's day. A later
  day's answer to a prior day's record is not visible to that day's state (existing per-day
  ledger); the item then stays parked until the owner resumes it.
- "Past its deadline" is the item's goal `date` in `memory/goals.md` before today.
- The DM goes out through the listener, the only DM sender (`listen.py`), with the PR
  pattern: one marker event per item, a fixed fallback line when the outward lint refuses
  the summary. Without a listener, the nudge and the status line are the surfaces.
- `asks_per_item` and `unnecessary_asks` reach "the cruise promotion rule" by being in
  `metrics.collect`; the rule itself is #283.

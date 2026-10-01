# Feature Specification: Assume and record on two-way doors, the mandate block, external confirmation is never a seat precondition, time-boxed waits

**Feature Branch**: `301-negotiation-spec`
**Created**: 2026-10-01
**Status**: Ready for verification (the amendment text is already in the working tree)
**Input**: Issue #301, spec(decisions). Design sections 5.2, 5.3, 5.8 and 5.8.1, with
pointers in 4.1, 4.6, 5.4 and 5.9. Related: #282 (cruise mode, classes and levels), #279
(calibration interview), #302 (the implementation of this amendment, same chain).
Evidence: owner observation 2026-10-01 ("endless negotiation loop between agents, wanting
written confirmation for everything, including from external clients") and owner request
the same day for an observability ping when agent-to-agent negotiation ping-pong happens
on a work item.

## Root cause (read on main, 56e9107)

This is a spec gap, not a runtime failure; the orchestrator notes name no dry-run
workspace to reproduce against. The rules that drive asking and re-asking are:

- `docs/specs/2026-09-24-wuwei-design.md:553` (5.8): "Every decision, whoever takes it, is a
  record". Every small in-item choice becomes a full MADR record, and with cruise mode not
  yet built (#283) the shipped routing sends any record that is not two-way with blast
  radius `own branch` or `own PR` to the owner (`cli/wuwei/decision.py:178-180`). There is
  no lighter place to record a choice and move on.
- `charters/_common.md:27-28` repeats it for every seat ("Every decision goes through the
  decision record") and says nothing about `Assumptions:`. AGENTS.md has the rule ("record
  assumptions in the spec under Assumptions and move on") for coding agents in this
  repository, but no runtime seat inherits it.
- Nothing tells a seat what it may decide. Briefs carry the task; the design (5.2) has no
  mandate, so a cautious seat asks.
- `docs/specs/2026-09-24-wuwei-design.md:586-588` (5.8.1): at L0 and L1 "the item waits",
  and the `message` class (`:606`) defaults to L0. A seat that wants a client's written
  confirmation turns it into a message decision, and the whole item waits on a person
  outside the loop with no time box.
- The negotiation budget is stated three times (5.3 `:412`, 4.6 `:283`,
  `charters/_common.md:21`) and the charter ends it with "Blocking residue after the delta
  is an owner decision", not the constitution's design reconsideration.
- The steward sees only fix rounds, and only at three (`cli/wuwei/steward.py:20-37`,
  `review`). It does not count decision records, verdicts, re-dispatches or fix-round
  continuations per item in a window, and nothing tells the owner an item is looping.
- `docs/specs/2026-09-24-wuwei-design.md:576` (5.8): only `AskUserQuestion` and
  control-plane escalations are guarded. A Codex or headless seat that ends its turn with a
  question to the owner is not caught.

## User Scenarios & Testing

### User Story 1 - Seats decide what they may decide (Priority: P1)

The owner, the #302 builder or a reviewer reads 5.2, 5.3 and 5.8 and finds, once each:
assume and record for two-way doors inside the item, the mandate block every brief
carries, and the rule that a seat question which is not a decision record is refused in
every runtime.

**Independent Test**: the phrase check in plan.md "Verification commands" passes on the
worktree and fails on a `git archive main` export.

**Acceptance Scenarios**:

1. Given the amended 5.3, then an open question on a two-way door inside the item is not
   asked: the seat takes its recommendation, records it under `Assumptions:` in the item's
   spec or PR body (what was assumed, why, what would overturn it) and continues; gates
   review assumptions as findings; only a one-way door or a question outside the item
   becomes a decision record. "When unsure, it is one-way" still decides reversibility.
2. Given the amended 5.2, then every brief carries a mandate block generated from the
   item's class levels (5.8.1) and the calibration interview answers, with three lists
   (decides alone, decides and records, goes to the owner) and the closing line "nothing
   else is a question".
3. Given the amended 5.8, then a seat question that is not a decision record is refused in
   every runtime: the PreToolUse guard on `AskUserQuestion` and control-plane escalations,
   and SubagentStop for a last message that asks the owner a question without a decision
   id; 4.1 lists the SubagentStop behaviour.

### User Story 2 - External waits are time-boxed and never hold reversible work (Priority: P1)

**Acceptance Scenarios**:

1. Given 5.8.2, then a confirmation from a person outside the loop is never a precondition
   a seat may impose: it becomes a `message` record (a draft the owner sends, ceiling L1),
   the item carries `assumption: external` with the recommended reading, and reversible
   work continues.
2. Given 5.8.2, then `decisions.wait_hours` (default 24 weekday hours in `owner.timezone`,
   one working day) is the time box: at the watch sweep past it the CLI confirms the
   item's `assumption: external` reading (the draft stays unsent with the owner) only when
   that reading is two-way and no other 5.8.1 ceiling applies; otherwise it parks the item
   with a decision record; either way it writes an event.
3. Given the 5.8.1 class table, then the `message` row points to 5.8.2, so cruise mode and
   the external rule agree.

### User Story 3 - One negotiation budget and a ping-pong signal to the owner (Priority: P1)

**Acceptance Scenarios**:

1. Given 5.3, then the negotiation budget is stated once: one fix round plus one delta per
   gate; residual non-blocking findings are review notes; the verdict lint refuses a
   finding without a failure scenario and a verdict without a probe or mutation row;
   exceeding the budget is a design reconsideration agreed with the owner, never another
   round. 4.6 points to it instead of restating it.
2. Given 5.8.2, then at each steward run the CLI counts per item over
   `steward.loop_window_hours` (default 4) the decision and clarification records naming
   it, gate verdicts, re-dispatches of a role and fix-round continuations; a sum above
   `steward.loop_threshold` (default 9), or a second fix round at any gate, raises one
   `negotiation.loop` event per item per day naming the counts and the last two exchanges.
3. Given 5.8.2 and 5.9, then a loop is a `nudge`, and a `page` when the item is past the
   date of the goal it serves; the control plane sends the DM the same summary within
   `control_plane.content`; the status line shows `loops N`.
4. Given 5.8, then owner asks per item and unnecessary asks (owner answer equal to the
   recommendation) are steward metrics, named as the agreements 5.8.1 promotes from.

### User Story 4 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the diff, then only `docs/specs/2026-09-24-wuwei-design.md` and
   `specs/301-negotiation-spec/` changed, and `python -m pytest -q` passes, including
   `tests/test_docs.py`.

### Edge Cases

- `approach` is the 5.8.1 class for in-item implementation choices. While it runs at L2 or
  L3 an open approach question is an assumption, not a record; if the class is demoted to
  L0 or L1, the mandate moves it to "goes to the owner" and it becomes an `approach`
  record. Demotion keeps its meaning without a second mechanism.
- L2 classes other than `approach` (`retry`, `park`, `accept-residual`) still write a
  record; cruise mode answers it. They are in "decides and records".
- A design reconsideration parks the item with a record. `park` runs at L2, so the CLI may
  take the park itself; resuming with a replacement approach is what needs the owner.
- The steward seat never changes item state (5.5), so the time box is applied by the watch
  sweep (4.2), and the loop signal only reports; the negotiation budget stops the rounds.
- Build-loop iterations driven by fast-check failures are not negotiation; 5.3 already
  bounds them (`build.max_iterations`, `build.stuck_after`). Only fix-round continuations
  (gate or PR feedback) count.
- A second fix round is already over budget, so it raises the signal on its own, whatever
  the window count.
- `control_plane.content = "none"` sends only that a loop exists, as for decisions (15.4).

## Requirements

- **FR-001**: 5.3 gains "Assume and record" and replaces "Cycle budget" with "Negotiation
  budget"; 4.6 points to 5.3 instead of restating the budget.
- **FR-002**: 5.2 gains a "Briefs" paragraph defining the mandate block and its closing
  rule; 5.4 adds that the owner is never asked what a mandate lets a seat decide.
- **FR-003**: 5.8 narrows "every decision is a record" to decisions the owner or cruise
  mode answers; Enforcement states the every-runtime question rule and adds owner asks per
  item and unnecessary asks to the steward metrics; the 4.1 SubagentStop row names the
  flag.
- **FR-004**: 5.8.1 class table: the `approach` and `message` rows point to 5.3 and 5.8.2.
- **FR-005**: New subsection 5.8.2 with external confirmation, the `decisions.wait_hours`
  time box, and negotiation-loop detection with `steward.loop_window_hours`,
  `steward.loop_threshold`, the `negotiation.loop` event, tiers, DM and status line.
- **FR-006**: 5.9 lists the loop nudge, the past-goal-date page and the status-line count.
- **FR-007**: No runtime file, charter, agent, skill, template, docs site page, test or
  constitution changes.

## Success Criteria

- SC-001: The plan's phrase check fails on main and passes on this branch.
- SC-002: Each new key, the `negotiation.loop` event, the mandate block definition and the
  budget's "one fix round plus one delta" appear exactly once in the design spec.
- SC-003: `git diff --stat main` lists only the design spec and this feature directory.
- SC-004: The amendment stays short: one new subsection, net growth under 60 lines.

## Assumptions

- The spec author writes the amendment (orchestrator notes, as for #237 and #282); the
  builder checks consistency and runs the docs tests. No docs test is added: the issue's
  acceptance says only the spec changes. #302 adds the runtime tests.
- The constitution already agrees (Cycle budget: one fix round plus one delta review,
  then a design reconsideration agreed with the owner before more code); it stays
  unchanged. 5.3 cites it.
- "One working day" is 24 hours counted on weekdays in `owner.timezone`. There is no
  working-hours config key; the interview's hours answer is charter text, not a value the
  CLI can read.
- "The item's deadline" is the target date of the goal the item serves (5.7, the `date`
  field in `memory/goals.md`), the only item-linked date the spec defines.
- "A person outside the loop" is anyone but the owner and the seats, so internal
  stakeholders count, not only the 4.9 external parties.
- The issue's four loop signals are kept; #302's "owner asks" are counted as the
  clarification records (`C-n`) and decision records that every owner question must cite,
  so they are not counted twice.
- Defaults come from #302 so the two issues agree: a 4 hour window, a threshold of 6
  combined (seven exchanges trigger), or any second fix round.
- "A finding without a failure scenario and a probe is refused by the lint" restates the
  shipped verdict lint: a finding needs a failure scenario, and a verdict needs a probe or
  mutation row, where `not run` stays accepted. Tightening that is a separate change.
- The interview inputs to the mandate are the trust-surface areas (`risk`) and the
  owner-run commands (`manual`); merge autonomy already reaches the mandate through the
  `merge` class and `merge.auto`.
- The charters (`charters/_common.md:21`, `:27-28`), the planner skill,
  `brief.launch_prompt`, the steward, the SubagentStop lint, the config template and the
  docs site change in #302.

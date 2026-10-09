# Feature Specification: a round cap for every item kind

**Feature Branch**: `623-round-cap`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #623 (owner, 2026-10-09): "The pre-registration went through five
review rounds of three reviewers each. Later rounds found real issues, but with diminishing
returns: the last two were mostly masking edge cases that belong in the annotation tool
anyway." Ask: "A round cap. After two fix rounds, any remaining non-blocking notes go into
the PR and the item ships." Deliver: `gates.max_rounds` (default 2) counts every fix round of
an item whatever its kind; after the cap non-blocking findings go into the PR body and the
item ships; a blocking finding after the cap parks the item with a decision record naming
the finding and what would unpark it, never another round; a reviewer cannot widen the scope
after round one; the report counts rounds per item and names the items that hit the cap; the
cap is configurable per tier.

## Root cause

Reproduced in-process on `main` (a temporary workspace built with the `tests/test_dispatch.py`
fixtures, item `A`, neutral verdict texts):

| Step | Today |
|---|---|
| Round one: quality writes FIX whose only finding is `blocks: no` | `dispatch next` returns `fix`: a full fix round opens for a note |
| Round one FIX, fix round, round two (delta) still blocking | `dispatch next` returns `escalate`, reason `blocking finding remains after delta`; the finding is not named |
| A second `build.open_fix` | `ValueError: fix round budget exhausted`, whatever the owner configures |

In the code:

- The budget is a literal one in two places and cannot be configured or set per tier:
  `cli/wuwei/commands/build.py:190` (`if record.get('fix_rounds', 0) >= 1`), with line 217
  setting `fix_rounds` to `1` rather than counting; and `cli/wuwei/dispatch.py:304-305` and
  `:344-345`, where the verdict record holds only an `initial` and one `delta` round, so a
  second delta cannot be recorded (`receive` refuses `gate already received`, lines 584-586).
- After the budget, `next_step` returns `escalate` with a fixed reason (dispatch.py:345), and
  `commands/next.py:376-378` turns it into `wuwei plan park A --reason 'blocking finding
  remains after delta'`: the park record names neither the finding nor what would unpark it.
- The budget is written in the charters as "one fix round plus one delta check per gate" on
  the pre-PR code gates (`charters/_common.md:20-21`). A spec or document reviewed outside
  that path (the FULL track's spec-done gate has no CLI path at all; a grep of `cli/wuwei`
  finds none) has no count, and a reviewer re-running a document with new non-blocking notes
  is not a fix round anywhere. That is how the pre-registration reached five rounds.
- Nothing stops a reviewer from widening the scope: the delta brief
  (`dispatch._delta_feedback`, dispatch.py:546-552) asks the seat to "re-check your findings
  at the current HEAD", so a new finding on lines the fix never touched can block again.
- The report has no round count: `report.seat_lines` (report.py:79-92) lists seats only.

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is a round? A: A fix round: the builder is resumed with gate or PR feedback
  (`build.open_fix`). It is counted where it opens, so code, spec and document items count
  the same. Round one is the first verdict; round n+1 is the verdict after fix round n.
- Q: What does `gates.max_rounds = 2` allow? A: Two fix rounds, so up to three verdict
  rounds. `1` is today's budget. The minimum is 1: a FIX verdict at round one always gets
  one round.
- Q: Per tier? A: `gates.tier_max_rounds.light`, `.standard` and `.full` override
  `gates.max_rounds` for items recorded at that tier; `0` (the default) means "use
  `gates.max_rounds`". An item with no recorded tier uses `gates.max_rounds`.
- Q: When does another round open below the cap? A: As today: a FIX verdict at round one
  opens the first round; after a delta, a blocking finding opens the next round while rounds
  remain. A delta with no blocking finding raises with its notes, as today.
- Q: After the cap? A: A verdict with no blocking finding raises the PR with its non-blocking
  findings as review notes in the PR body (the shepherd brief's `Review note:` lines, as
  today). A blocking finding returns `escalate` with a reason that names the cap, the gate,
  the finding's first line and what would unpark the item; the existing card parks it with
  `wuwei plan park`, whose decision record carries that reason.
- Q: How is the next delta recorded? A: When a fix round opens from a delta, each gate's
  delta verdict becomes the verdict that round answers (its `initial` record), and the record
  it replaces is kept under `round<n>`. Every existing reader (receive, the delta seats, the
  launch guard's `delta_due`, the second opinion, the PR guard, merge) keeps working on
  `initial` and `delta` unchanged.
- Q: How is "cannot widen the scope" enforced? A: The delta brief, from round two on, says a
  new finding on lines the fix round did not change is `blocks: no` unless it is a
  trust-boundary security finding, and `charters/_common.md` says the same for every seat.
  No line-level diff check.
- Q: Do PR review rounds count? A: They go through the same `open_fix` and its cap, but the
  existing reset of the count at every move from delta to raised (`state.py:474-475`)
  stays, so a reviewer's request on the PR is never refused because the gates used their
  rounds. The cap this feature adds is the pre-PR gate cap.
- Q: What does the report show? A: A `## Rounds` section, one line per item that opened a fix
  round today: its count and, when a round reached the cap, `round cap <n> reached`.

## User Scenarios and Testing

### User Story 1 - The cap ends the rounds and the item ships with its notes (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a document item (gate set `['goal']`, tier light) with FIX verdicts carrying a
   blocking finding in rounds one and two and a third verdict whose findings are all `blocks: no`, at the default cap,
   **When** `dispatch next` runs after the third verdict, **Then** it returns `raise` with
   those findings as notes, and the shepherd brief command carries them as `Review note:`
   lines.
2. **Given** the same item after round two, **When** `dispatch next` runs, **Then** it opens
   the second fix round (`fix` for `goal`), the round-two verdict becomes the record the
   third round answers, and the round-one record is kept as `round1`.
3. **Given** the third round, **Then** the delta seat continues the same goal seat with the
   re-read feedback, and `receive --round delta` records it.

### User Story 2 - A blocking finding after the cap parks with its record (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a code item whose security gate still has a blocking trust-surface finding at
   round three (two fix rounds used, default cap), **When** `dispatch next` runs, **Then** it
   returns `escalate` with a reason naming `round cap 2`, `security`, the finding's first line
   and the unpark step, and `next` turns it into the `wuwei plan park` card whose record
   carries that reason.
2. **Given** that item, **Then** `build.open_fix` refuses a third round with a reason naming
   the cap.

### User Story 3 - The cap is configurable (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `gates.max_rounds = 1`, a FIX at round one and a blocking finding at round two,
   **Then** `dispatch next` returns `escalate` (one fix round), and `open_fix` refuses a
   second.
2. **Given** `gates.max_rounds = 1` and `gates.tier_max_rounds.light = 2`, **Then** a light
   item gets two fix rounds and a standard item one.

### User Story 4 - A reviewer cannot widen the scope (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a delta seat at standard or full depth, **Then** its continue feedback says a new
   finding on lines the fix round did not change is `blocks: no` unless it is a
   trust-boundary security finding.

### User Story 5 - The report counts rounds (Priority: P2)

**Acceptance Scenarios**:

1. **Given** item `A` with two fix rounds at cap 2 and item `B` with one, **Then** the report's
   `## Rounds` lists `- A: 2 fix rounds, round cap 2 reached` and `- B: 1 fix round`.
2. **Given** no fix round today, **Then** the report has no `## Rounds` section.

### Edge Cases

- A gate that passed at round one keeps its round-one record; only gates with a delta verdict
  move when the next round opens.
- A gate whose round-two verdict passed is not asked again at round three.
- Every gate rotated (no round-one record left): the PR guard's same-HEAD check over round-one
  records has nothing to compare and passes.
- A second opinion (`quality@codex`) rotates like any gate; the retro still pairs it with its
  base gate's round-one record.
- An item moved to delta by hand with no build record counts as one fix round used.

## Requirements

- **FR-001**: `gates.max_rounds` (integer, default 2, minimum 1) and
  `gates.tier_max_rounds.{light,standard,full}` (integer, default 0, minimum 0; 0 uses
  `gates.max_rounds`) set an item's round cap, read by one helper
  `dispatch.max_rounds(config, row)`.
- **FR-002**: `build.open_fix` counts each fix round (`fix_rounds` plus one), refuses a round
  at the cap with a reason naming the cap and the config key, opens a round from `gate`,
  `raised` or `delta`, and writes `round` and `cap` into the `build.fix_opened` event.
- **FR-003**: When `open_fix` opens a round from `delta`, in the same state write, each gate
  with a `delta` record has its `initial` record kept as `<item>:<gate>:round<n>` (n = the
  rounds used before this one) and its `delta` record moved to `initial`.
- **FR-004**: `dispatch.next_step` at delta with a blocking finding opens the next fix round
  for the blocking gates while rounds remain, else returns `escalate` with the reason of
  FR-005. Without a blocking finding it returns `raise` with the notes, as today.
- **FR-005**: The cap reason reads `round cap <n> reached: <gate> still blocks: <finding
  first line>; unpark after a design change that closes it is recorded in the spec`.
- **FR-006**: The standard delta feedback adds the scope rule of User Story 4; the light
  re-read feedback is unchanged (it only rewrites `Verdict:` and `Head:`).
- **FR-007**: The PR guard's same-HEAD check compares only records still from round one, and
  passes when none is left; the retro's second-opinion table pairs round-one records by
  their recorded round, not by key.
- **FR-008**: The report gains `## Rounds` from the day's `build.fix_opened` events.
- **FR-009**: Invariant I35 in design 9.2 and `tests/test_invariants.py`: no item opens a fix
  round past its cap, for each cap and tier override.
- **FR-010**: Docs and charters say the rule: `charters/_common.md` rule 5 (round cap for
  every item kind and the spec-done gate, notes to the PR after the cap, park with a record,
  no scope widening after round one), agents regenerated; `docs/site/configuration.md`,
  `templates/workspace/config.toml`, `docs/site/concepts.md` (negotiation loops paragraph),
  the hero alt text in `README.md`, `docs/site/index.md` and both hero SVG descriptions.

## Success Criteria

- **SC-001**: At the shipped defaults no item, code, spec or document, gets a third fix round
  before the PR.
- **SC-002**: Every park at the cap has a decision record naming the blocking finding and the
  unpark step.
- **SC-003**: The owner reads each item's fix rounds and the cap hits in the day report.

## Assumptions

- A FIX verdict at round one still opens a round even when all its findings are
  `blocks: no` (today's rule). The cap counts that round. Changing what opens a round would
  touch every verdict reader (receive, `delta_due`, the second opinion, the PR guard, merge)
  and the issue does not ask for it.
- The scope rule is carried by the delta brief and the common charter, not by a line-level
  diff check: the VCS port has no hunk operation and adding one is out of proportion. If
  sentinels ignore the rule, the report's cap hits show it and a hunk check is the upgrade.
- The park keeps the existing card path (`escalate`, then `wuwei plan park --reason`, whose
  record already carries the reason) instead of the CLI parking on its own, so a park has one
  writer.
- The PR stage keeps today's count, reset at every move from delta to raised; counting PR
  rounds with the gate rounds would park an item on a human reviewer's request. PR-stage
  rounds stay flagged by the steward's third-round note, as today. Capping them is a
  separate decision for the owner.
- The steward's negotiation-loop nudge on a second fix round (`steward.negotiation`) is a
  report, not a stop, and stays as it is.
- The FULL track's spec-done gate has no CLI path; the cap reaches it through the common
  charter only.
- An adopted PR's first fix brief (#510, `pr_actions._fix` for an item with no build) is not
  an `open_fix` round and stays uncounted; its later rounds count.
- Design spec 5.3 states "one fix round plus one delta check per gate". The owner's newer
  decision in this issue conflicts with it; the conflict is raised in the PR body for the
  owner to amend 5.3 (as #622 did). This feature adds only the 9.2 invariant row, as the
  constitution requires for a changed decision rule. The constitution's cycle budget governs
  how WUWEI itself is built and is not changed.

## Deferred

- None.

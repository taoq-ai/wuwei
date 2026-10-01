# Feature Specification: Cruise mode, graduated autonomy per decision class, promoted from the ledger, with ceilings

**Feature Branch**: `282-cruise-mode-spec`
**Created**: 2026-10-01
**Status**: Ready for verification (the amendment text is already in the working tree)
**Input**: Issue #282, spec(decisions). Design sections 4.6, 5.4, 5.7, 5.8, 5.9, 6.8 and
15.8. Related: #175 (decision outcome and reversal), #279 (owner interview, weights), #280
(tiered gates, same evidence-first pattern). Evidence: owner request 2026-10-01 ("Cruise
mode ... proceed as you suggested").

## Root cause (read on main, fb3be19)

This is a spec gap, not a runtime failure; there is no dry-run workspace to reproduce
against (the orchestrator notes name none). Autonomy today is one binary rule with no
class, no level, no evidence loop and no off switch.

- `docs/specs/2026-09-24-wuwei-design.md:565-569` (5.8 before this change): routing is by
  reversibility only. A two-way door inside the item is decided by the seat; everything
  else goes to the owner. There is no way to give one kind of decision more or less
  autonomy than another, and no rule for earning or losing it.
- `docs/specs/2026-09-24-wuwei-design.md:554-563`: the record has no `Class:` field, and
  `Decided-by:` is `seat` or `owner`, so an outcome cannot name the rule that answered it.
- `docs/specs/2026-09-24-wuwei-design.md:575-577`: the reversal rate is measured, but its
  only consequence is a charter proposal; nothing lowers autonomy when the owner reverses.
- `docs/specs/2026-09-24-wuwei-design.md:456-462` (5.4) and `:19-22` (G1) say the owner is
  asked "for one-way-door decisions", which was already narrower than 5.8's owner list.
- `docs/specs/2026-09-24-wuwei-design.md:265-269` (4.6): `merge.auto` is a separate
  autonomy switch with no link to the decision framework.
- `docs/specs/2026-09-24-wuwei-design.md:586-591` (5.9): seat-taken two-way decisions are
  `silent`; there is no tier for an answer the owner may want to undo.
- `docs/specs/2026-09-24-wuwei-design.md:690-691` (6.8): the promote lint accepts only a
  charter override or a note as a target, so a level change has no promote path.
- The shipped code mirrors the spec: `cli/wuwei/decision.py:10-12` (FIELDS, no `Class`),
  `:63` (`Decided-by` is `seat|owner`), `:178-180` (`route` is two-way plus `own branch`
  or `own PR`), `cli/wuwei/commands/build.py:393` (the stuck-loop park writes
  `Decided-by: seat`). These change in the implementation issue, not here.

## User Scenarios & Testing

### User Story 1 - One statement of cruise mode (Priority: P1)

The owner, the builder of the later implementation issue, or a reviewer reads 5.8 and
finds classes, levels, conditions, ceilings, promotion and demotion rules and the kill
switch each stated once, with defaults.

**Independent Test**: the phrase check in plan.md "Verification commands" passes on the
worktree and fails on a `git archive main` export.

**Acceptance Scenarios**:

1. Given the amended 5.8, then a `Class:` field is in the record shape, the lint refuses
   an unknown class, and the class list is fixed (a new class is a spec amendment, not
   config).
2. Given 5.8.1, then levels L0 ask, L1 recommend, L2 notify (with an undo window) and L3
   digest are defined, and every class has a default level and a ceiling in one table:
   L2 for the two-way, inside-the-item classes seats already took on their own, L0 for
   the rest, L3 for `merge` (effective only where `merge.auto` is on).
3. Given 5.8.1, then the auto-answer conditions are listed (level L2 or L3, two-way, blast
   radius inside the workspace, weighted margin at least `decisions.cruise.margin` with the
   owner's interview weights where they exist, daily budget not exhausted, no ceiling),
   anything else goes to the owner, and the record and outcome event name the rule
   (`Decided-by: cruise <class>@L<n>`).
4. Given 5.8.1, then the ceilings (messages to people, deploys and merges to a repository
   whose base deploys, trust-boundary findings, anything one-way, anything outside the
   item's goals) stay at L0 or L1 whatever config says, and the config check refuses a
   level above a class ceiling.
5. Given 5.8.1, then promotion (steward proposal after 10 agreements and no reversal in 14
   days, landed by `wuwei promote` only with owner approval) and demotion (automatic, one
   level, on a reversal, an escaped defect or three thin-margin escalations in a row,
   recorded in the ledger) are stated, with the weekly blind sanity sample.
6. Given 5.8.1, then `decisions.cruise.enabled = false` runs every class at L0 without
   changing any running or configured level, and the status line shows `cruise off | L<max>`.

### User Story 2 - The rest of the spec agrees (Priority: P1)

**Independent Test**: same check.

**Acceptance Scenarios**:

1. Given 5.4, then the owner is asked for decisions cruise mode routes to the owner
   (pointer to 5.8.1), and the digest lists the decisions cruise mode answered.
2. Given 4.6, then the merge policy is named as the `merge` class at L2 or L3 with its own
   conditions unchanged.
3. Given G1, 5.9 and 6.8, then none contradicts 5.8.1: G1 asks the owner only for what
   cruise mode does not answer; 5.9 makes an L2 answer a `nudge` and an L3 answer
   `silent`; the 6.8 promote lint accepts one cruise level as a target.

### User Story 3 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the diff, then only `docs/specs/2026-09-24-wuwei-design.md` and this feature's
   `specs/282-cruise-mode-spec/` directory changed, and `python -m pytest -q` passes,
   including `tests/test_docs.py`.

### Edge Cases

- Before this change, "scope agreed with other people" and "spend above the budget
  threshold" routed to the owner in 5.8. Scope agreed with other people is a record-level
  ceiling, so it stays at L0 or L1 even after `scope-cut` is raised. Spend is covered by
  the `re-plan` class at L0 (raised only with owner approval) and by the 15.8 budget
  governor, which already refuses launches past the cap.
- A decision no class fits is `other` at L0 with an L1 ceiling, so a seat is never forced
  to misclassify and `other` can never be promoted past owner confirmation.
- 4.9 auto-send tiers are not decision records and are unchanged; the `message` class
  covers a decision to message a person.
- Merges keep every 4.6 condition, cap and breaker; the cruise daily budget does not count
  them; the kill switch and an L0 or L1 merge level still stop auto-merge.
- Demotion only lowers autonomy, so it needs no approval; promotion raises it, so it needs
  the owner's approval at the morning gate (the rule 5.7 already uses for goal changes).
- `Reversibility: unsure` (accepted by the shipped lint) is not two-way, so it never
  auto-answers.

## Requirements

- **FR-001**: The 5.8 record shape gains `Class:`; `Decided-by:` becomes `owner` or
  `cruise <class>@L<n>` (CLI-written); the routing paragraph routes by class and 5.8.1;
  the lint refuses an unknown class; the steward metrics count by class, and cruise
  reversals feed demotion.
- **FR-002**: New subsection 5.8.1 Cruise mode with: the four levels; the class table
  (class, what it decides, default, ceiling); `[decisions.cruise]` keys with defaults
  (`enabled` true, `margin` 0.2, `max_per_day` 20, `undo_minutes` 60, `levels.<class>`,
  which only lowers a class); the running level in `memory/cruise.json`, written only by
  `wuwei promote`, with the effective level the lowest of running, config and ceiling;
  conditions; ceilings; the merge mapping; promotion and demotion with the weekly sample;
  the kill switch with its status-line text.
- **FR-003**: 5.4 points to 5.8.1 for what reaches the owner; 4.6 names the policy as the
  `merge` class at L2 or L3 with its conditions unchanged.
- **FR-004**: G1, 5.9 and 6.8 are reworded only where they would contradict 5.8.1.
- **FR-005**: No runtime file, charter, agent, skill, template, docs site page or test
  changes.

## Success Criteria

- SC-001: The plan's phrase check fails on main and passes on this branch.
- SC-002: Each default value and the kill-switch status text appears exactly once in the
  design spec.
- SC-003: `git diff --stat main` lists only the design spec and this feature directory.
- SC-004: The amendment stays short: one new subsection, design spec net growth under 80
  lines.

## Assumptions

- The spec author writes the amendment (orchestrator notes, like #237); the builder checks
  consistency and runs the docs tests. No docs test is added: the issue's acceptance says
  only the spec changes. The implementation issue adds the runtime tests.
- L0 is today's owner path (one question per decision, recommended first, batched, 5.4)
  and L1 preselects the recommendation for a batch confirmation. The issue labels L1
  "today's behaviour for owner decisions" but also defaults owner-routed classes to L0;
  reading L0 as today keeps the defaults from changing today's behaviour.
- Classes beyond the issue's examples: `approach` (an implementation choice inside the
  item, the most common seat decision today; without it those would newly reach the
  owner), `message` (the class the ceiling list needs for its config refusal) and `other`
  (the catch-all). The issue's "retry a failing check" and "accept a residual finding"
  are `retry` and `accept-residual`.
- `merge` defaults to L3 because the 4.6 auto-merge was already digest-only (5.9 lists
  auto-merges as `silent`); `merge.auto` (default off) still gates it, so the effective
  default is the owner.
- The issue's "Decided by:" is the existing `Decided-by:` field. The rule id is
  `<class>@L<n>`. A seat writes `owner`; only the CLI writes the cruise value, and the
  CLI-only `decision.decided` event is the trusted copy (seat-written record text is never
  proof).
- Margin: (recommendation score minus the best other option's score, over all other
  options, musts ignored) divided by 10 times the sum of the weights. Ignoring musts for
  the runner-up is the conservative reading: a seat cannot widen the margin by failing
  the alternatives on a must.
- "Blast radius inside the workspace" is checkable only on fixed values: `own branch`,
  `own PR` or `workspace`; any other text is outside.
- "Trust-boundary findings" is checked per record as a record whose context cites a
  security finding; "outside the item's goals" as an `unplanned` item (5.7) or a goal
  change.
- Promotion and demotion thresholds (10 agreements, 14 days, 3 thin margins in a row, a
  weekly sample of one per class over seven days) are fixed in the spec, not config;
  changing them is a spec amendment once evidence exists (no config for values with no
  evidence of needing to change).
- The undo window counts from when the nudge reaches the owner, since 5.9 batches nudges
  up to two hours apart.
- The kill switch is the config key, in force while it is false, which covers the issue's
  "for the day". Flipping it from the control plane is not specified here; 15.4 commands
  can add it.
- The owner's interview weights (#279) do not exist on main yet; 5.8.1 uses them "where
  they exist" and leaves their storage to #279.
- The docs site, charters and agents still describe the shipped seat routing
  (`charters/_common.md:28`, `docs/site/concepts.md:82`, `docs/site/reference.md:36`).
  They change with the implementation issue, which follows #279 and the owner's first
  real day.

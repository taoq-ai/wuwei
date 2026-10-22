# Feature Specification: gates start at push, in parallel with CI, and the ready door names a failing check

**Feature branch**: `leone/1221`
**Item**: 1221 (taoq-ai/wuwei#1221), tier full, goal G-2
**Input**: the owner's issue #1221. On a client repository where CI takes 35 to 45 minutes per push,
one review round costs 1.5 to 2 hours, most of it idle: builders wait on one CI read before they
hand back, and gates start only after it.

## The promise in my words

A builder hands back as soon as its push lands and reports CI as unread. The planner launches the
gates the diff needs at that head at once, while CI runs. Gates already run the tests they need,
so they do not need CI's result. Green CI still holds ready and merge. A check that turns red
after the gates pass sends the PR back to the builder, and the fix is a new head that the delta
rule decides who re-reads.

In the runtime, the board's team row asks for a gate seat when gates are owed on a head whose CI
runs, has not started, or misses a required check; only a red head waits, since it goes to the
builder first. The ready door (the flip to ready and a reviewer request on a draft) refuses while
a check fails at the head and names the failing checks; the merge door already does. Nothing in
the hooks or `wuwei evidence` looks at CI when it counts a verdict, and a test pins that.

The acceptance scenarios, restated:

1. The builder charter says to hand back without waiting for CI and to report CI as unread.
2. A pushed draft head with CI running and gates owed, read with no gate seat running, shows the
   team row's owed-gates duty.
3. A verdict attested at head H while CI ran is counted once CI is green at H: the SubagentStop
   attests it, `wuwei evidence` shows no gap, and the merge door passes.
4. With the gates passed and a failing check at the head, `gh pr ready` (every route to the flip
   and to a reviewer request on a draft) and a merge are refused, naming the failing check; with
   CI green both pass.

Outside: the delta rule, gate seats on Claude, and the rule that a verdict counts only for the
head it read are unchanged.

## How this fails

1. Gates spend a round on a head CI later turns red, and the fix is code: the gate re-reads the
   delta. That is the price the issue accepts; the delta rule keeps it to the one gate it needs.
2. The ready door checks the red head before the gates, so a red draft names only its failing
   checks and not its missing gates. The builder fixes CI first and the gates read the new head,
   so the order matches the flow, but a reader sees the gate gap only on the next try.
3. A flaky check fails once and holds ready until it is re-run. The refusal names the check, and
   the shepherd's existing rule (a red check that also fails on the base is the base's) applies;
   the owner can accept the `CI failing` gap at that head, which the ready door honours as the
   merge door does.

## Clarifications

- Q: Does running CI hold the ready door? A: No. The promise names a failing check; running CI
  holds ready in the shepherd charter (ready once CI is green) and holds the merge door, as before.
- Q: What is "a failing check"? A: what `evidence.ci_gaps` reads as `CI failing`: a check run or
  commit status whose conclusion or state is a failure, cancelled, timed out, action required,
  startup failure or error. Review-gated contexts are not CI and are left to their own gaps.
- Q: Does an owner exception open the ready door on a red head? A: Yes, an approved exception for
  that PR at that head whose gap text is the printed `CI failing: ...` line, read by
  `evidence.excepted` as at the merge door.
- Q: Which board heads owe a gate seat now? A: every head with a gate gap and no `CI failing`
  gap. `CI running`, `CI not started` and `required check not run` no longer hide the duty.
- Q: What does the team row say? A: `orchestration: gates owed with no gate seat running`; the
  item rows below it name the gates themselves.

## Requirements

- FR-001: builder, planner, `_way`, `_pr`, shepherd and the watch skill say gates start at push,
  in parallel with CI, and green CI still holds ready and merge.
- FR-002: the board names the owed-gates duty while CI runs or has not started; a red head owes none.
- FR-003: the ready door refuses the flip and a reviewer request on a draft while a check fails at
  its head, naming the failing checks, unless the owner accepted that gap at that head.
- FR-004: a verdict attested while CI ran counts once CI is green at its head.
- FR-005: runtime stays within the item's budget (+3) and the 3,600-line cap.

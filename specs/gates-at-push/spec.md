# Feature Specification: gates start at push, in parallel with CI, and the ready door waits for green CI

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
builder first. The ready door (the flip to ready and a reviewer request on a draft) waits for
green CI at the head, as the merge door already does: it names each CI gap (`CI failing`, `CI
running`, `CI not started`, a required check not run). A review-triggered status is review
evidence, not CI, and never holds it. Nothing in
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
2. The ready door reads CI before the gates, so a draft that is not green names only its CI
   gaps and not its missing gates. The builder fixes CI first, or CI finishes, and the gates read
   that head, so the order matches the flow, but a reader sees the gate gap only on the next try.
3. A flaky check fails once and holds ready until it is re-run. The refusal names the check, and
   the shepherd's existing rule (a red check that also fails on the base is the base's) applies;
   the owner can accept the `CI failing` gap at that head, which the ready door honours as the
   merge door does.

## Clarifications

- Q: Does running CI hold the ready door? A: Yes (the planner's reading of the owner's issue:
  "gh pr ready and merge still require green CI at the head"). The door names `CI running`.
- Q: What does the door read? A: `evidence.gaps`, the merge door's reading, kept to the gaps that
  start `CI `, `required check` or `evidence unreadable`. A failing check is a check run or commit
  status whose conclusion or state is a failure, cancelled, timed out, action required, startup
  failure or error. A status from a workflow the repository runs on `pull_request_review` reads as
  `waiting on review` or `change request outstanding`, never CI, so it cannot hold the reviewer
  request that would clear it. An unreadable host holds the door.
- Q: Does an owner exception open the ready door? A: Yes, an approved exception for that PR at that
  head whose gap text is the exact printed CI gap, read by `evidence.excepted` as at the merge door.
- Q: Does the door read CI on a ready PR? A: No. A reviewer request on a ready PR passes whatever
  its CI: re-requesting an approval given at an older commit is the board's duty when a check is red.
- Q: Which board heads owe a gate seat now? A: every head with a gate gap and no `CI failing`
  gap. `CI running`, `CI not started` and `required check not run` no longer hide the duty.
- Q: What does the team row say? A: `orchestration: gates owed with no gate seat running`; the
  item rows below it name the gates themselves.

## Requirements

- FR-001: builder, planner, `_way`, `_pr`, shepherd and the watch skill say gates start at push,
  in parallel with CI, and green CI still holds ready and merge.
- FR-002: the board names the owed-gates duty while CI runs or has not started; a red head owes none.
- FR-003: the ready door refuses the flip and a reviewer request on a draft until CI is green at
  its head, naming each CI gap, unless the owner accepted that exact gap at that head; review
  statuses never hold it, and a ready PR's reviewer request is not read.
- FR-004: a verdict attested while CI ran counts once CI is green at its head.
- FR-005: runtime stays within the item's budget (+8 cap) and the 3,800-line limit.

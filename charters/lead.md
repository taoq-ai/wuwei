# Lead charter

You own discovery, ranking, scope and tier for a plan pass. You return candidates; the planner
adds them with `wuwei plan add`, which computes the score.

## Discovery

1. Read every configured repository's sources you can reach: open issues, red checks on the base
   branch, review findings, review threads asking for follow-up work, follow-ups recorded in
   recent PRs, regressions in the report. Mark a source you cannot reach as unmeasured.
2. Each candidate cites the goal in `.wuwei/goals.md` it serves, or is marked unplanned.
   Deduplicate against the plan and open PRs. Verify the work is still open.
3. On a later pass the same day, start from what changed since the last pass: merged items, parked
   items, the owner's new words.

## Ready

An item is ready when it has a promise, acceptance scenarios (given, when, then), its repository
and the files it will touch. Return only ready candidates; an item that cannot be made ready is a
question for its source, not a build.

## Scope and tier

1. Name the item's promise and what is outside it, the files it will touch and its repository.
   Build an overlap matrix from real diffs; serialise or combine overlapping work.
2. Tier: `light` for a trivial, local change; `standard` by default; `full` for a change to a
   contract, schema, boundary, auth, secrets, agent tooling or infrastructure. When unsure, go up.

## Ranking

The configured framework ranks the queue; never hand-order it.

- `wsjf`: value to the goal, time criticality, risk reduction or unblocking, and job size, each on
  1, 2, 3, 5, 8, 13, 20, each with one line of evidence.
- `rice`: reach, impact (0.25, 0.5, 1, 2, 3), confidence (0.5, 0.8, 1.0) and effort in seat-days,
  each with one line of evidence.

Red-team the plan: name the riskiest item in the queue and the cheapest way to learn early whether
it works (a spike, a probe, a prototype), and rank that learning first.

Write the candidates to `.wuwei/candidates.json`, a list of objects with `id`, `title`, `goal`,
`repo`, `tier`, `scores` (named as the framework names them: `value`, `time`, `risk`, `size`, or
`reach`, `impact`, `confidence`, `effort`), `promise`, `acceptance` (a list of given, when, then
scenarios) and a one-line `why`. The planner adds them all with `wuwei plan add --from
.wuwei/candidates.json`; the plan, not this file, is what seats read.

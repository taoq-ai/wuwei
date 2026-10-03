---
version: 1.0.0
---
# Lead charter

Read `_common.md` and `_common-authoring.md` before discovery. Own discovery, ranking, scope, overlap, track, flags and launch advice. Use configured repos and adapters; do not assume any source exists.

## Capacity and discovery

1. CAP counts running build seats, not queued, gated or shepherded items. Read CAP and host floors from `config.toml`; a slot frees at builder handoff. Do not launch if the configured floor or budget fails.
2. Discover at the morning plan, each sweep and when a freed build seat leaves the queue below `discovery.min_queue`. Query the tracker backlog, base-branch red checks, review and scanner findings, review threads, outcome-metric regressions and follow-ups from today's PRs through configured adapters. Mark missing sources unmeasured.
3. For each candidate, cite the confirmed goal it serves from `memory/goals.md`, or while it has none the goal object you propose in `goals`, or mark it `unplanned`; verify the work is still open, deduplicate against tracker and day items, and state evidence and time of measurement.
4. Scope the changed behavior, files and blast radius. Build an overlap matrix from actual diffs. Serialise or combine overlapping work. Name the item promise and what is outside it.
5. Flags: trust_surface, boundary_relevant, agent_surface are set from the actual diff. Set `trust_surface` for auth or credentials, input parsing at a trust boundary including LLM output used as instructions, tenant or workspace scoping and permission checks. Set `boundary_relevant` for any change to what a published field can be worth or thresholded at, even without a wire-shape change. Set `agent_surface` for prompts, tool definitions, agent tool permissions or MCP config. Infrastructure, secret, schema and migration paths force FULL and set `trust_surface`. Other never-auto paths route to the owner under step 7. Otherwise select SLICE or FULL by the common track rule. A flagged item cannot start without owner routing under the configured intraday policy. An optional candidate `tier` (light, standard, full) can raise the computed review tier, never lower it.
6. For `prioritisation.framework = wsjf`, give evidence for value to goal, time criticality, risk reduction or unblocking, and job size, each on the 1, 2, 3, 5, 8, 13, 20 scale; WSJF divides the first three summed components by size. For `rice`, give evidence for reach, impact (0.25, 0.5, 1, 2, 3), confidence (0.5, 0.8, 1.0) and effort in seat-days; RICE multiplies the first three and divides by effort. Cite each component in one line. Break ties by goal priority and use `wuwei rank`, never a hand-ordered queue.
7. Present the ranked queue, goal links, unplanned share, component evidence, scope, overlap, risk, track and CAP for the morning gate. Intraday starts follow `discovery.autostart`: `off` sends every candidate to the owner; `strict` starts only a confirmed-goal SLICE item above the approved queue's cut line; `goal` permits either track for a confirmed goal. Risk flags, never-auto paths, CAP or budget failures always route to the owner. Candidates that do not qualify join the next decision batch.

## Launch and escalation

1. Claim an approved item only at launch. Recheck active work, base head and PR collisions; give the planner a briefable item with its acceptance tests and dependencies.
2. Resolve local blockers within the item's budget, then park or resequence with a decision record. Route beyond-item or one-way choices to the owner through the common decision rule.

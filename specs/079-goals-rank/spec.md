# Feature Specification: Goals, discovery and rank

**Feature Branch**: `079-goals-rank`  
**Created**: 2026-09-29  
**Status**: Draft  
**Input**: Issue #79.

## User Scenarios & Testing

### User Story 1: Rank goal work

1. Given two candidates, `wuwei rank` orders them by the configured WSJF or RICE formula with goal priority as tie-break.
2. Given a candidate missing a score component or its evidence line, plan lint refuses it.
3. Given a candidate without a goal or an `unplanned` mark, plan lint refuses it.
4. Given a malformed goal, the command exits 2 and names its line.

### User Story 2: Discover work throughout the day

1. Discovery at morning planning and each sweep reports missing sources as `unmeasured` and deduplicates tracker and day items.
2. When a seat frees and the queue is below `discovery.min_queue`, discovery runs again.
3. Configured adapters are the only external data source; unavailable reads never report empty-clean.

### User Story 3: Decide intraday starts

1. Given `strict` and a FULL-track candidate, it joins the decision batch.
2. Risk-flagged, never-auto path and over-budget work joins the decision batch in every mode.
3. `off` always proposes to the owner; `goal` permits confirmed goal work on either track.

## Requirements

- Owner alone edits `memory/goals.md`; guards refuse seat writes.
- Goal blocks have id, outcome, measure, target, date and priority.
- Scoring validates allowed values and one evidence line for each component.
- New settings appear in the template and site documentation.
- Discovery and rank are callable functions and commands; planner dispatch remains out of scope.

## Assumptions

- Goals use `## G-n` headings followed by `outcome:`, `measure:`, `target:`, `date:` and `priority:` lines. Priority is a positive integer, with 1 highest.
- Ranking input is a JSON list. Each candidate has a `score` object and an `evidence_lines` object keyed by framework component.
- A candidate's `goal` is a `G-n` id; unplanned work uses `goal: unplanned`.
- Discovery candidates use existing source evidence where available and remain unscored until a lead adds score citations.

## Deferred

- Tracker backlog enumeration belongs to #121 because the tracker port has no backlog operation.
- Outcome metric regression intake needs the metric producer from #5.6; until present it reports `unmeasured`.
- Planner dispatch and automatic seat start belong to #22.

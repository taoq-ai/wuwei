# Feature specification: WUWEI morning plan

## User story

As the owner, I invoke `/wuwei plan` to review a measured lead discovery and approve the day's goals, ordered queue, seat policy, CAP and work envelope before any build starts.

## Requirements

- The skill reads workspace goals and prior day, runs a measured process and source sweep, dispatches the lead using its charter, and passes the lead's evidence, scope, overlap, track, flags and proposed order to `wuwei plan propose`.
- Proposal writes today's `plan.md` with goals, source measurements including unmeasured sources, queue and gate choices. Proposal creates no worktree and changes no approved state.
- The morning gate asks one question per decision, with text starting `Morning gate` and citing today's plan file. It confirms goals and receives explicit approval or edits to the queue, seat policy, CAP and envelope.
- `wuwei plan approve` records only selected proposed items and the confirmed goals, seat policy, CAP and envelope through a dedicated state producer. Generic state writes cannot change these fields.
- Carry-over from the previous day is an explicit option at approval. It imports unfinished previous items and records a `state.import` event. No implicit first-write import exists.
- Invalid proposal, approval or unreadable source fails closed; no worktree is created by either command.

## Acceptance scenarios

1. Given an approved gate, state holds seat policy, CAP, envelope and approved items, and no worktree exists before approval.
2. Given a proposal without approval, today's `plan.md` exists and state has no approved queue.
3. Given yesterday's unfinished items and explicit carry-over approval, they appear in today's state with a `state.import` event; without that approval they do not.
4. Given a forged generic state set or event, protected gate fields and import proof are refused.

## Assumptions

- The lead seat supplies structured JSON. The skill owns discovery and source calls, since `wuwei rank` is issue #79 and source adapters are incomplete.
- Proposed order is preserved without a ranking score; the gate displays it as proposed, pending `wuwei rank`.
- A nonempty goals file is owner authored; the morning gate confirmation is recorded as goal identifiers supplied in the proposal.
- Worktrees are created only later by dispatch, after approval.

## Deferred

- Automated WSJF/RICE scoring and plan lint belong to issue #79.
- Continuous discovery triggers and source adapter coverage beyond existing ports belong to later team issues.

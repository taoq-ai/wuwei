# Implementation Plan: `wuwei pr wait`

**Branch**: `906-shepherd-launch` | **Spec**: [spec.md](spec.md)

## Summary

One function, `pr_actions.wait(root, timeout, sleep)`, behind `wuwei pr wait [--timeout S]`. It
reads what `next` would act on for PR items (`next.step`), refreshes the listing of the repositories
that hold a raised or claimed PR when `derive.stale` says so, and exits 1 with one line per new
step. `next` returns it as the background command of its PR wait row.

## Technical Context

Stdlib-only Python 3.11+. Touches `cli/wuwei/pr_actions.py`, `commands/pr.py`,
`commands/next.py`, the planner charter, the plan skill, `docs/site/daily.md` and
`docs/site/reference.md`. No adapter change: the tick is the existing `_PULLS` listing call.

## Constitution Check

- I Stdlib only. II Exits 0 (timeout or nothing to watch), 1 (a step is due), 2 (could not run,
  through `__main__`). III The change test is `next.step` and the read is `derive.refresh`: nothing
  re-implemented. V No daemon, no service, no new config: `pr.poll_seconds` is the tick, `--timeout`
  bounds it. Constraint "the owner's session is never blocked": the planner runs it in the
  background; `next` says so.

## Design

1. `pending(root)`: `next.step(root)`; for a `set` row, every launch, duty and the decision whose
   item has a PR, as `{(item, kind, why): line}`.
2. Loop: baseline from the current listing; each tick refreshes `derive.stale` repositories that
   hold an owned PR, compares `pending` with the previous tick, prints the new lines and exits 1.
3. Sleep `pr.poll_seconds`, or until the reset a `GitHub rate limit until HH:MM:SS UTC` refusal
   names when that is later; never past the deadline.
4. `next.step`: the PR wait row becomes `wait` with command `wuwei pr wait`, action `background`
   and a `then` that says to run it in the background and run `wuwei next` when it exits.

## Cost per tick

0 requests while every owned repository's listing is younger than `pr.poll_seconds`; otherwise one
GraphQL listing request per repository holding a raised or claimed PR, whatever the PR count.

## Test plan

`tests/test_pr_wait.py`: the acceptance (two claimed PRs, a thread on one, exit 1 within one poll,
the line names the item and `shepherd`); a tick costs one call for two PRs and none inside the
interval; timeout exits 0 with no output; a rate-limit refusal sleeps until its reset; no owned PR
exits 0. `tests/test_next.py`: the PR wait row names `wuwei pr wait` in the background.

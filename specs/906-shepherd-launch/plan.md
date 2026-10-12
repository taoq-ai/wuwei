# Implementation Plan: the shepherd duty is an executable launch

**Branch**: `906-shepherd-launch` | **Spec**: [spec.md](spec.md)

## Summary

The shepherd duty stops being a record the planner writes by hand. `derive.offers` turns a due
shepherd duty on a raised item into a `shepherd` launch, keyed by the activity revision in the seat
name; the launch set resolves it with the raise path's brief-then-seat shape. `pr act` stops
guessing intent: the keyword regexes go, `--reply` is honoured first, and the seat states a fix or a
scope decision with `--fix` or `--scope` on a named `--thread`. A fresh PR read that finds no reply
owed records the duty done, timed at the read's start.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Touches `cli/wuwei/derive.py`, `dispatch.py`,
`pr_actions.py`, `commands/pr.py`, `commands/duty.py`, `commands/next.py`, the shepherd charter (and
its generated agent) and the docs. No new module, no new config key, no new event kind
(`duty.done` gains an `as_of` field).

## Constitution Check

- I Stdlib only: yes. II Exits: `pr act` keeps 0/1/2; a thread no longer owed is exit 2 with its
  fix. III One behaviour, one function: the due test stays in `derive.duties`; the seat shape is
  shared with `raise_action`; completion lives in `observe`, the one fresh-read producer. IV Tests
  first. V Ponytail: the keyword routing is deleted, not extended; no new command. VII Security: a
  shepherd seat still never merges (merge.py role check); replies still post through
  `obligations.reply` and the outward lint.
- Not touched: `guards/agent_launch.py`, `workspace.adopt_worktree`, `shepherd.claim_pr`,
  reconcile (#901 owns them).

## Design

1. `derive.revision(activity)`: the activity time in UTC as `YYYYMMDDHHMMSS`, or None.
2. `derive.duties`: the shepherd entry's record is `wuwei pr act <pr>`; its prompt says the seat
   answers it. A duty row's time is `payload.as_of` when present, else its `ts`.
3. `derive.offers`: computes the due shepherd items once. In the raised branch the old
   `claimed and shepherd due` arm becomes `shepherd due`: a `shepherd` launch when the seat
   `shepherd-<item>-<revision>` is not in `data['seats']`, else nothing (the PR waits). The arm
   keeps its place: after red checks and conflicts, before merge.
4. `derive.seated`: a `shepherd` launch is seated.
5. `dispatch._seat(root, data, item, name, body)`: the brief command when the brief is missing,
   else the seat launch when the seat is not registered, else None. `raise_action` uses it;
   `shepherd_action(root, item)` uses it with a body that names `pr act --thread` and its three
   answers. `resolve_offer` sends `kind == 'shepherd'` there.
6. `pr_actions`: delete `SCOPE` and `FIXES`. `launch` opens a round only for `conflicted` or
   `ci_red`. `_owed` returns every owed entry; `_thread(..., reply, thread, fix, scope)` selects the
   named or first owed entry, then: reply posts; fix opens the round with the thread text and the
   reason; scope asks the owner card whose record is the exact command (Yes opens the round, No
   prints the defer reply); none prints the reply action with every owed id.
7. `observe(..., as_of)`: when no reply is owed and the item's shepherd duty is due, append
   `duty.done {item, duty: shepherd, evidence, as_of}`. `evaluate` passes the time before the read.
8. `commands/duty.py`: `--evidence` on `shepherd` is refused and names `pr act`.
9. `commands/next.step`: the shepherd duty is not listed (it is a launch).

## Test plan

`tests/test_derive.py`: shepherd launch per revision, seated, none once the seat exists, a new
revision launches again; `as_of` decides the due test; the duty command refuses shepherd evidence.
`tests/test_pr_actions.py`: the three keyword questions reply; plain `pr act` opens nothing; `--fix`
opens a round; `--scope` asks the card and routes Yes and No; two threads by `--thread`; a comment
landing during a reply; completion recorded from the ledger. `tests/test_next.py`: three `next`
calls give the brief command, the seat launch, then no launch.

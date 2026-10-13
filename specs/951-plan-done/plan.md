# Plan: Owner completed plan items

## Approach

 Add `done` to the existing plan CLI. Validate the item, phase, reason, and `state.in_flight`; use `sessions.needs_owner` with a reason bound token, then write item status and event through `state._write_state`. Recheck state and live work inside the update. Make dispatch treat all done items as terminal. Make report Done include owner attribution, reason, and recorded branch and worktree; exclude done status from Parked. Existing close and Carry checks already use done status.

## Review follow-up

1. Register `plan.done` as silent in signal and its emitted-kind test map.
2. Exclude done items from build slot accounting, release held builds when their fix item is done, and skip done parked items in the resume decision loop.
3. Route done status through `dispatch.next_step` in both build `step` and `next_action`.
4. Refuse carry and park on done items. Explain the completion event and reason in `why`, and list the command in the public reference.

## Constitution Check

Stdlib only; one CLI state writer; Owner step card only; test first; no new module or external calls.

## Verification

Reproduce `owner sent both` as a parked item. Cover all allowed phases, live work, missing and spent Yes, dispatch, report, close, and worktree preservation. Run explicit importing test files with the named interpreter.

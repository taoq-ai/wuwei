---
layout: default
---

# Recovery

[Home](index.html)

The [daily path](daily.html) needs none of these commands. Each one here is recovery, not
daily use: reach for it when evidence and state disagree, a seat is lost, or the
installation changed.

## state transition

`bin/wuwei state transition <item> <phase>` moves an item's phase by hand. It is recovery,
not daily use: on the daily path `build next`, `dispatch next`, `pr raise` and an observed
merge move every phase. Use it only when the recorded phase disagrees with the evidence,
for example to resume a parked item. It accepts only the moves in the
[item phase order](reference.html#item-phase-order).

## runtime dispatch

`bin/wuwei runtime dispatch <role> <brief> <worktree>` returns launch instructions for a
logged brief. The planner uses it for lead and shepherd seats. By hand it is recovery,
not daily use: relaunch a lost sentinel from a fresh brief, or launch a Codex seat.

## runtime continue

`bin/wuwei runtime continue <job-json> <feedback>` returns the same seat's instructions
with feedback. It is recovery, not daily use: return a rejected or unmeasured verdict to
its seat, or continue a Codex sentinel with the job `runtime dispatch` printed. Claude
delta continuations come from the `seats` list of `dispatch next`.

## integrity reconfirm

`bin/wuwei integrity reconfirm` records the owner's confirmation of a development
checkout or a changed installation. It is recovery, not daily use: an intact signed
release needs no reconfirmation. Run it in a host terminal and type the displayed digest
after reviewing the contents. See the [index](index.html#development-checkouts) for what
it records.

## Other recovery

`bin/wuwei state recover` restores an unreadable `state.json` from its snapshot; see
[state recovery](reference.html#state-recovery). Owner-only commands are listed under
[host terminal actions](reference.html#host-terminal-actions).

## Seat launch contract

Write and log a brief with `wuwei brief <role> <item> <name> --body TEXT` (or
`--file PATH`, where `--file -` reads stdin), then obtain launch
instructions with `wuwei runtime dispatch <role> <brief> <worktree>`. With the Claude
runtime, pass the returned `prompt` unchanged to Agent and use its `agent_type`
(`wuwei:<role>`) as Agent's `subagent_type`. Supply an Agent description and launch
from the workspace root, which is the hook payload's `cwd`.

The exact first line is `WUWEI brief: <relative brief path>`. The path is relative
to the workspace root, for example `.wuwei/days/2026-09-29/briefs/builder-1.md`,
not relative to the item's worktree. Do not prepend instructions to the prompt.
The guard still requires the logged, unchanged brief and matching role, fresh
evidence and available capacity; a missing first line is refused with the required format.

The core function `wuwei.brief.launch_prompt` generates these instructions for all
Claude roles, including the actions `build next` and `dispatch next` return.
`wuwei runtime continue <job-json> <feedback>` preserves the reference
and includes feedback for the same seat. It does not authorize a second launch
with a consumed brief. `wuwei steward run --trigger close` returns the same contract
inside `steward_launch`, through the configured runtime adapter.

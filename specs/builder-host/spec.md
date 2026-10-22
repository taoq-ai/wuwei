# Feature Specification: a long item's builder can run as its own session

**Feature branch**: `leone/builder-host`
**Item**: builder-host, tier standard, goal G-1
**Input**: the owner's answer of 2026-10-22 ("Sounds good, let's go for that"). A session restart
dropped eight seats that day, and one builder's commits sat unpushed.

## The promise in my words

An item can say where its builder runs. `wuwei plan add <id> --host session` stores `host:
session` on the item; with no `--host` the item gets `host: agent`, and any other value is
refused. For a `session` item the planner starts the builder with the `create_session` tool: the
same environment, the item's branch, the builder charter as the brief. It records the new
session's id on the item (`wuwei plan session <id> <session id>`) and follows the builder through
the branch and the draft PR, never by messaging it.

Gates do not move. Every gate for every item still runs as an Agent-tool seat in the planner's
session, because a verdict counts only when that session's seat transcript attests it. The planner
never launches a gate inside the builder's session.

A session builder fires no subagent hook, so it has no `seat.started` row. The board reads the
item's record instead: an open `session` item with a recorded session id counts as a live builder
seat (against the seat ceiling, and against `stale`) and its row says `builder running in session
<id>`. The hook's check that refuses a launch on an item another session holds does not read this
record, so the planner's own gate launches on that item stay free.

Every builder, as an Agent-tool seat or in its own session, commits and pushes after every green
step and hands back the pushed head.

The acceptance scenarios, restated:

1. `plan add <id> --host session` then `plan show <id>` shows `host: session`; without `--host`
   it shows `agent`; `--host codex` (or `Session` through the module) is refused.
2. An open item with `host: session` and a recorded session id is a live builder seat on the
   board, and its row names the session.
3. The planner charter starts a `session` item's builder with `create_session` and every gate as
   an Agent-tool seat; the builder charter says to push after each green step.

Outside: the seat ceiling's number, gate attestation, the hook's held check, Codex jobs.

## How this fails

1. The session builder dies and its record stays: the item counts as a live seat until it closes,
   so it never shows `stale`. The planner reads the branch and the draft PR and starts a new
   session, which re-records the id.
2. The new session loads WUWEI and gets the planner's orientation at session start. The prompt
   opens `You are the builder for <id>, not the planner` so it does not run the queue.
3. A re-add of the item without `--host` sets the host back to `agent`, the same way a re-add
   resets the tier. The planner re-adds with the same flags.

## Assumptions

- `plan session` is a new plan action, not a flag on `plan run`: `run` marks an operations item,
  which changes how the board reads it. Overturned if the owner wants one action for both.
- The record is live while the item is open, with no time bound: a long item is the reason for a
  session builder, and the six-hour seat bound would drop it mid-build.
- A fix round starts a new builder session on the branch, since the planner does not message a
  session.

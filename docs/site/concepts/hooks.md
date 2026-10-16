# Hooks: the sensei

A good teacher shows the form before the move, watches without commenting on every step, corrects
on the spot, and is strict where it matters. WUWEI's hooks play that role.

| Stage | When | What happens |
| --- | --- | --- |
| Teach | before a move | the session starts with the way of working, the planner charter, goals, standards and the board; before `gh pr create`, the PR standard with a ready body |
| Watch | during | every tool call is traced, silently |
| Correct | right after | a new PR is told what it still lacks; a one-way answer is turned into an ADR note |
| Stop | where it matters | the doors; a malformed verdict sent back; one reminder when the team tries to stop with work it can close |
| Stay quiet | when all is well | no notes, no reminders, a short report |

## The hooks

| Hook | Role |
| --- | --- |
| SessionStart | orientation: the way of working, `_common.md`, the planner charter, goals, `.wuwei/standards.md`, the board |
| PreToolUse | the doors; the PR standard once per session before `gh pr create`; owner questions without a class sent back |
| PostToolUse | a trace per call; what a new PR lacks; owner answers recorded as prompts, rulings, exceptions |
| SubagentStop | every seat's stop recorded with its tokens and confidence; a sentinel's verdict linted and attested |
| Stop | a reminder only when actionable work is new since the last one, naming only what changed; once to arm the watch or to plan when the flow would stall; never a loop |

In a cloud session, SessionStart also pulls the `wuwei/state` branch and Stop pushes what changed;
see [cloud sessions](cloud.md).

## Why hooks and not only skills

A skill works when the model chooses to load it, and that choice is where guidance fails: the
model is busy and the skill stays unread. A hook fires on the event whatever the model chose. So
the standards live once (in charters and skills), and hooks deliver them at the moment they apply.

Hooks see tool calls and lifecycle events, not intent. Guidance needed before the first tool call
stays in the charters and the session start.

## The Stop reminder

When the session tries to end its turn while there is work it can close now (a PR without a test,
an item without a PR), the Stop hook blocks once with the list, at most ten lines, and says how many
waiting items it left out. It never loops and never nags: while any seat is still running it stays
silent (the seat's completion wakes the planner anyway), the same set of gaps does not block twice,
waits (CI, the owner, plan approval, an andon) never count, a closed day is quiet, and a turn already
continued by a Stop hook always passes.

Two more reminders keep the flow from stalling on the owner's nudge, each once per session: when
only waiting work is left and no watch pass ran in the last hour, it says nothing will wake
the session for the waiting work unless a check-in or PR subscription is armed, which WUWEI cannot
see, and asks it to arm `/wuwei-watch` on a schedule; when the queue is empty and goals are
set, it asks for a plan pass from the goals.

**Why:** it turns "honour the promise" into a habit without turning it into a trap.

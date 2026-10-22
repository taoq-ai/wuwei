# Hooks: the sensei

A good teacher shows the form before the move, watches without commenting on every step, corrects
on the spot, and is strict where it matters. WUWEI's hooks play that role.

| Stage | When | What happens |
| --- | --- | --- |
| Teach | before a move | the session starts with the way of working, the Decisions and Done rules, where the planner charter, goals and standards are, and the board; before `gh pr create`, the PR standard with a ready body |
| Watch | during | every tool call is traced, silently |
| Correct | right after | a new PR is told what it still lacks; a one-way answer is turned into an ADR note |
| Stop | where it matters | the doors; a malformed verdict sent back; one reminder when the team tries to stop with work it can close |
| Stay quiet | when all is well | no notes, no reminders, a short report |

## The hooks

| Hook | Role |
| --- | --- |
| SessionStart | orientation within Claude Code's 10,000-character cap on hook context: the CLI path, the way of working, `_common.md` Decisions and Done, the paths of the planner charter, goals and `.wuwei/standards.md`, the board with how many items it left out |
| PreToolUse | the doors; the PR standard once per session before `gh pr create`; owner questions without a class sent back |
| PostToolUse | a trace per call; what a new PR lacks; owner answers kept as `answer.pending`, then recorded as prompts, rulings, exceptions once the session transcript shows them (on the planner's next call, before its doors, since Claude Code writes the answer after the hook) |
| SubagentStop | every seat's stop recorded with its tokens and confidence; a sentinel's verdict linted and attested; only when the session transcript shows the seat's launch |
| Stop | a reminder only when actionable work is new since the last one, naming only what changed; once to arm the watch or to plan when the flow would stall; never a loop |

**Why the transcript:** a hand-made hook call could otherwise write a ruling or a seat stop the owner never gave.
An answer or stop the transcript does not show is recorded as `answer.unconfirmed` or
`seat.unconfirmed` with the check that failed: at once, or for an answer once its tool_result row holds
a different answer to that question or no `toolUseResult` answers (its text never counts), or after 10
minutes with no row. Each question in a batch counts
on its own, and an answer that is not recorded never blocks the planner's Stop: its note comes on the
next tool call.
A session that ends before it confirms an answer leaves the answer's `answer.pending` row, which reads
as unconfirmed. An error while
the next call confirms an answer is a `hook.error`; the doors still judge that call.

**Seat reports outside auto mode:** Claude Code refuses SubagentHandback there, so SubagentStop keeps
each seat's last message under `.wuwei/reports/`. The planner's next tool call or Stop gives a kept
report once. When a task notification in the session transcript already holds that seat's result,
the hook gives a one-line pointer to the kept file instead of the text: a queued notification can
still be dropped (the kill-agents chord, an interrupt), so the planner always has a way to the report.

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
waiting items it left out. It never loops and never nags: while a seat this session started is still
running it stays silent (the seat's completion wakes the planner anyway; a seat a dead session left
without a stop does not count), the same set of gaps does not block twice,
waits (CI, the owner, plan approval, an andon) never count, a closed day is quiet, and a turn already
continued by a Stop hook always passes.

Two more reminders keep the flow from stalling on the owner's nudge, each once per session: when
only waiting work is left and no watch pass ran in the last hour, it says nothing will wake
the session for the waiting work unless a check-in or PR subscription is armed, which WUWEI cannot
see, and asks it to arm `/wuwei-watch` on a schedule; when the queue is empty and goals are
set, it asks for a plan pass from the goals.

**Why:** it turns "honour the promise" into a habit without turning it into a trap.

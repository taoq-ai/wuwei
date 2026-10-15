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
| Stop | one reminder per distinct set of actionable gaps; never a loop |

## Why hooks and not only skills

A skill works when the model chooses to load it, and that choice is where guidance fails: the
model is busy and the skill stays unread. A hook fires on the event whatever the model chose. So
the standards live once (in charters and skills), and hooks deliver them at the moment they apply.

Hooks see tool calls and lifecycle events, not intent. Guidance needed before the first tool call
stays in the charters and the session start.

## The Stop reminder

When the session tries to end its turn while there is work it can close now (a PR without a test,
an item without a PR), the Stop hook blocks once with the list. It never loops: the same set of
gaps does not block twice, waits (CI, reviewers, an andon) let the turn end, a closed day is quiet,
and a turn already continued by a Stop hook always passes.

**Why:** it turns "honour the promise" into a habit without turning it into a trap.

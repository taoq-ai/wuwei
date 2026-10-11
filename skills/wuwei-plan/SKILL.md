---
name: wuwei-plan
description: Propose the day with lead discovery and run the morning gate before dispatch.
---

# /wuwei plan

Loop on `wuwei next`: run `wuwei next --json`, do every launch and every duty it returns, ask its one decision when there is one, and run it again when a result or a completion notification arrives. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command. Never pass it through a shell variable or a command substitution, and never invoke Python without `-P`. Read `.wuwei/charters/planner.md` when present (what the owner prefers).

Each action has a `why` and a `then`; do what `then` says.

- `run`, `check`: run the `command` as one plain Bash call, through Bash in the background when `then` says so.
- `launch`: pass `prompt` unchanged to Agent in the background, `agent_type` as `subagent_type`, with a short description.
- `continue`: the same, as a fresh Agent with the returned `prompt`; pass `resume` too only to an Agent tool that takes it (Claude Code's has none; the fresh launch continues the seat).
- `set`: do every entry this turn. A launch with action `run`, `check` or `polish` runs its `command`. Run each of its `commands` (briefs and `receive`) in order. Pass every `launch` and `continue`, a gate's `seats` included, to Agent in the background in one message so they run concurrently. A `refused` or `wait` launch names its reason. For each duty, write what it asks, send it through the configured tool and run its `record` command with the link. A `decision` command prints an Owner step card; ask it with AskUserQuestion.
- `card`: each widget command (`wuwei plan gate` and the rest) prints a list; ask the action's `widget` list with AskUserQuestion, at most four per call, passing `question`, `header`, `options` and `multiSelect` unchanged. Record each answer with its `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. A card without a widget is one line to show the owner. An owner question comes from `wuwei next`: a command that refuses with an Owner step card prints it; ask it with AskUserQuestion as printed, then run the same command again on Yes; on No leave it. An outward refusal names `wuwei config set outward.allow ... --add`; run it, it asks its card. Without AskUserQuestion (a headless run), leave the item for `wuwei next`. Seats never ask the owner. A config value the owner changes (CAP, `host.seats` or any other key): run `wuwei config set <key> <value>`; it asks its Owner step card.
- `wait`: end the turn with the output of `wuwei status --line`.
- `done`: the day is closed.

Never resume or interrupt a seat to answer the owner; answer from `wuwei status --line`. An item the owner names during the day joins with `wuwei plan add <item> --goal G-n --note "<the owner's words>"`. Rewrite any text for a person with the `humanizer` skill in embedded mode when it is installed, outward text included (tracker comments, docs pages, DMs, PR comments, review pings). Without it, apply the checklist in `charters/_common-authoring.md` under Writing for a person.

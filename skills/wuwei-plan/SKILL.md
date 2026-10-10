---
name: wuwei-plan
description: Propose the day with lead discovery and run the morning gate before dispatch.
---

# /wuwei plan

Loop on `wuwei next`: run `wuwei next --json`, do the one action it returns, and run it again when the result or a completion notification arrives. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command. Never pass it through a shell variable or a command substitution, and never invoke Python without `-P`. Read `.wuwei/charters/planner.md` when present (the owner's preferences). When the `wuwei_board` tool is available, show the board once at the start of the day; nothing depends on it.

Each action has a `why` and a `then`; do what `then` says. `wuwei guide` holds every command and rule.

- `run`, `check`: run the `command` as one plain Bash call, through Bash in the background when `then` says so.
- `launch`: pass `prompt` unchanged to Agent in the background, `agent_type` as `subagent_type`, with a short description.
- `continue`: the same, as a fresh Agent with the returned `prompt`; pass `resume` too only to an Agent tool that takes it (Claude Code's has none; the fresh launch continues the seat).
- `set`, `gates`: do every entry this turn. Run each of its `commands` (briefs and `receive`) in order. Pass every `launch` and `continue`, a gate's `seats` included, to Agent in the background in one message so they run concurrently.
- `card`: each widget command (`wuwei plan gate`, `wuwei decision show D-n --widget` and the rest) prints a list; ask the action's `widget` list with AskUserQuestion, at most four per call, passing `question`, `header`, `options` and `multiSelect` unchanged. Record each answer with its `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. A decision record command that exits non-zero on the confirmation: run the `record` command `wuwei decision show D-n --widget` prints (`wuwei decide D-n "<label>" --card <hash>`) without asking the card again. Below strict, never show the owner a host-terminal command for a card they answered. A card without a widget is one line to show the owner. Without AskUserQuestion (a headless run), run `wuwei decision route D-n` so it reaches the DM. Seats never ask the owner. A config value the owner changes is written by the answer on its card: CAP or `host.seats` through `wuwei calibrate --questions cap seats`, any other key through a decision card recorded with `wuwei config set --from-card D-n`. Each choice on that card carries `Value:` rows (`KEY = <TOML value>`) and a `Previous:` line with the current value. Never run `config set` without a card.
- `wait`: end the turn with the output of `wuwei status --line`.
- `done`: the day is closed.

Never resume or interrupt a seat to answer the owner; answer from `wuwei status --line`. An item the owner names during the day joins with `wuwei plan add <item> --goal G-n`. Rewrite any text for a person with the `humanizer` skill in embedded mode when it is installed, outward text included (tracker comments, docs pages, DMs, PR comments, review pings). Without it, apply the checklist in `charters/_common-authoring.md` under Writing for a person.

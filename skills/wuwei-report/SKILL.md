---
name: wuwei-report
description: Complete the steward retro and present the daily owner report.
---

# /wuwei report

Loop on `wuwei next`: run `wuwei next --json`, do the one action it returns, and run it again when the result or a completion notification arrives. It walks the close, the retro, the report and the final close. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command. Never pass it through a shell variable or a command substitution, and never invoke Python without `-P`.

Each action has a `why` and a `then`; do what `then` says. `wuwei guide` holds every command and rule.

- `run`, `check`: run the `command` as one plain Bash call, through Bash in the background when `then` says so.
- `launch`: pass `prompt` unchanged to Agent in the background, `agent_type` as `subagent_type`, with a short description.
- `continue`: the same, with `resume` set to the returned `resume`.
- `set`, `gates`: do every entry this turn: run each of its `commands` in order, and pass every `launch` and `continue` to Agent in the background in one message so they run concurrently.
- `card`: each widget command (`wuwei close --widget`, `wuwei decision show D-n --widget` and the rest) prints a list; ask the action's `widget` list with AskUserQuestion, at most four per call, passing `question`, `header`, `options` and `multiSelect` unchanged. Record each answer with its `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. A card without a widget is one line to show the owner. Without AskUserQuestion (a headless run), run `wuwei decision route D-n` so it reaches the DM. Seats never ask the owner.
- `wait`: end the turn with the output of `wuwei status --line`.
- `done`: the day is closed.

The report is local owner text; present it in one short message. Keep unavailable measures as `unmeasured`.

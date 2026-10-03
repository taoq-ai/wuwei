---
name: wuwei-consolidate
description: Review workspace memory weekly, fold supported duplicates, and archive old days.
---

# /wuwei consolidate

Run `wuwei next` first and follow the step it names; run the steps below when it names this skill or the owner asked for it. Run inside a WUWEI workspace. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command, for example `/opt/wuwei/bin/wuwei mcp check` when the file holds `/opt/wuwei/bin/wuwei`; never through a shell variable or a command substitution. Never invoke Python without `-P`.

Owner questions. When the AskUserQuestion tool is available (the desktop app, the terminal and the IDE all have it), ask every owner question with the widget a command prints: `wuwei decision show D-n --widget`, `wuwei mcp check --widget`, `wuwei doctor --fix --widget` or `wuwei calibrate --questions`. Ask at most four per call and pass `question`, `header`, `options` and `multiSelect` unchanged. Record the answer with the widget's `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. When that command says it runs in a host terminal, show the owner that line. Without AskUserQuestion (a headless run), write the decision record, run `wuwei decision route D-n` so it reaches the DM, and keep working with assume-and-record where the mandate allows. Seats never ask the owner.

1. Schedule this skill once each week as an owner task, or add it to the existing sweep cadence. Do not run a separate daemon.
2. Run `wuwei consolidate`. Exit 0 means no findings; exit 1 means review the listed findings; exit 2 means evidence could not be read and the reason must be resolved before treating the review as complete.
3. Review stale summaries, potential contradictions, near-duplicates and archive candidates. For a supported duplicate, create a `fold` proposal under today's `days/<date>/proposals/` with a live note survivor, a reason and an evidence path. Run `wuwei promote` to snapshot memory and charters, archive the retired note and commit the result. A fold never deletes the original.
4. Re-run `wuwei consolidate` after proposals land. Days older than `consolidation.archive_after_days` move into `archive/`, and their report summary lines stay in `memory/index.md`.

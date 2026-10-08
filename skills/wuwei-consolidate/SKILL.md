---
name: wuwei-consolidate
description: Review workspace memory weekly, fold supported duplicates, and archive old days.
---

# /wuwei consolidate

Run `wuwei next` first and follow the step it names; run the steps below when it names this skill or the owner asked for it. Run inside a WUWEI workspace. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command. For example, run `/opt/wuwei/bin/wuwei mcp check` when the file holds `/opt/wuwei/bin/wuwei`. Never pass it through a shell variable or a command substitution. Never invoke Python without `-P`.

Owner questions. When the AskUserQuestion tool is available (the desktop app, the terminal and the IDE all have it), ask every owner question with the widget a command prints: `wuwei decision show D-n --widget`, `wuwei mcp check --widget`, `wuwei doctor --fix --widget` or `wuwei calibrate --questions`. Ask at most four per call and pass `question`, `header`, `options` and `multiSelect` unchanged. Record the answer with the widget's `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. When that command says it runs in a host terminal, show the owner that line. Without AskUserQuestion (a headless run), write the decision record, run `wuwei decision route D-n` so it reaches the DM, and keep working with assume-and-record where the mandate allows. Seats never ask the owner.

1. Schedule this skill once each week as an owner task, or add it to the existing sweep cadence. Do not run a separate daemon.
2. Run `wuwei consolidate`. Exit 0 means no findings; exit 1 means review the listed findings; exit 2 means evidence could not be read and the reason must be resolved before treating the review as complete.
3. Review stale summaries, potential contradictions, near-duplicates and archive candidates. Run `wuwei consolidate --widget` and ask each forgetting proposal with the widget it prints. The owner records the answer with `bin/wuwei memory forget F-n <label>` in a host terminal. That archives the note or drops the rule through promotion, and keeps the before text under `memory/archive/`. Nothing is forgotten without that answer.
4. Re-run `wuwei consolidate` after answers land. Days older than `consolidation.archive_after_days` become tarballs under `archive/<year>/`, readable with `wuwei memory show <date>`, and the week and month digests stand for them in the session payload.

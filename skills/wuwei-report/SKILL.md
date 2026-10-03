---
name: wuwei-report
description: Complete the steward retro and present the daily owner report.
---

# /wuwei report

Run `wuwei next` first and follow the step it names; run the steps below when it names this skill or the owner asked for it. Run inside a WUWEI workspace. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command, for example `/opt/wuwei/bin/wuwei mcp check` when the file holds `/opt/wuwei/bin/wuwei`; never through a shell variable or a command substitution. Never invoke Python without `-P`.

Owner questions. When the AskUserQuestion tool is available (the desktop app, the terminal and the IDE all have it), ask every owner question with the widget a command prints: `wuwei decision show D-n --widget`, `wuwei mcp check --widget`, `wuwei doctor --fix --widget`, `wuwei close --widget` or `wuwei calibrate --questions`. Ask at most four per call and pass `question`, `header`, `options` and `multiSelect` unchanged. Record the answer with the widget's `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. When that command says it runs in a host terminal, show the owner that line. Without AskUserQuestion (a headless run), write the decision record, run `wuwei decision route D-n` so it reaches the DM, and keep working with assume-and-record where the mandate allows. Seats never ask the owner.

1. Run `wuwei close`. For each open item it names, ask the owner with `wuwei close --widget` (carry is recommended) and run the widget's `record` command with the chosen label; `Skip` means keep working on that item. Without AskUserQuestion, run `wuwei plan carry <item>` yourself and say so in the report. Pending owner decisions it names go through `wuwei decision show D-n --widget`. Rerun `wuwei close` until it prints `steward_launch`, and launch that steward with Agent exactly as returned.
2. Follow `/wuwei retro` through the close check. Do not count a proposal as applied until `wuwei promote` lands it.
3. Run `wuwei report` and present the local report to the owner. It shows outcome measures beside the owner's baseline, open work, parked work and its decisions, answered decisions and carry. Keep unavailable measures as `unmeasured`.
4. Run `wuwei close` again until it exits 0. The Stop hook is the final close guard.

The report is local owner text. Any outward post must use the existing outbound tier and stay a draft when that tier requires approval.

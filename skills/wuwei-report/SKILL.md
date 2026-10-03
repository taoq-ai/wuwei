---
name: wuwei-report
description: Complete the steward retro and present the daily owner report.
---

# /wuwei report

Run inside a WUWEI workspace using the executable recorded in `.wuwei/executable`. Never invoke Python without `-P`.

Owner questions. When the AskUserQuestion tool is available (the desktop app, the terminal and the IDE all have it), ask every owner question with the widget a command prints: `wuwei decision show D-n --widget`, `wuwei mcp check --widget`, `wuwei doctor --fix --widget` or `wuwei calibrate --questions`. Ask at most four per call and pass `question`, `header`, `options` and `multiSelect` unchanged. Record the answer with the widget's `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. When that command says it runs in a host terminal, show the owner that line. Without AskUserQuestion (a headless run), write the decision record, run `wuwei decision route D-n` so it reaches the DM, and keep working with assume-and-record where the mandate allows. Seats never ask the owner.

1. Follow `/wuwei retro` through the close check. Do not count a proposal as applied until `wuwei promote` lands it.
2. Run `wuwei report` and present the local report to the owner. It shows outcome measures beside the owner's baseline, open work, parked work and its decisions, answered decisions and carry. Keep unavailable measures as `unmeasured`.
3. Run `wuwei close` and resolve findings. The Stop hook is the final close guard.

The report is local owner text. Any outward post must use the existing outbound tier and stay a draft when that tier requires approval.

---
name: wuwei-retro
description: Compile the steward retro, promote supported charter learnings, and check close evidence.
---

# /wuwei retro

Run `wuwei next` first and follow the step it names; run the steps below when it names this skill or the owner asked for it. Run inside a WUWEI workspace. For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute path it holds as the first word of a plain command. For example, run `/opt/wuwei/bin/wuwei next` when the file holds `/opt/wuwei/bin/wuwei`. Never pass it through a shell variable or a command substitution. Never invoke Python without `-P`.

Owner questions. When the AskUserQuestion tool is available (the desktop app, the terminal and the IDE all have it), ask every owner question with the widget a command prints: `wuwei doctor --fix --widget`. Ask at most four per call and pass `question`, `header`, `options` and `multiSelect` unchanged. Record the answer with the widget's `record` command, `<label>` replaced by the chosen label (labels joined by commas for a multi-select, or the Other text); `Skip` records nothing. An owner question comes from `wuwei next`: a command that refuses with an Owner step card prints it; ask it with AskUserQuestion as printed, then run the same command again on Yes; on No leave it. Without AskUserQuestion (a headless run), leave the item for `wuwei next`. Seats never ask the owner.

1. Run `wuwei close` first if it has not run today. It runs the close steward review once and prints `steward_launch`; launch that steward with Agent in the background exactly as returned. While an open item or a pushed branch without a PR remains, it prints one question per open item and launches nothing. Answer them as step 1 of `/wuwei report` says, then run it again. It then refuses until the retro exists. Do not run `wuwei steward run --trigger close` yourself: a second close review the same day writes no brief and says so. Read captured role notes, verdicts, events and the steward metrics.
2. Run `wuwei retro`. Review the per-role table, cycle table and generated proposals. A `Change: Hard rule: ...` note becomes a line under `## Hard rule changes` for the owner. Do not edit a guard or hard rule from the retro.
3. Run `wuwei promote` to land supported charter proposals. Inspect rejections and resolve them through a corrected proposal when evidence warrants it. Promotion writes the charter, dated changelog and ledger in a local commit with the promotion trailer.
4. Run `wuwei retro` again so Applied reflects landed proposals. Run `wuwei close --check retro` and address any owed or unmeasured evidence before closing the day.

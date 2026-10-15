---
name: wuwei-plan
description: Plan or re-plan the WUWEI day. Use at the start of the day, when the queue runs dry, when the owner adds, drops or changes work, or whenever the day changes. Can run any number of times a day.
---

# /wuwei-plan

A plan pass. The plan in `.wuwei/plan.json` is a running queue; this pass adds, drops or re-ranks.

1. Run `wuwei plan pass --reason "<why this pass: morning, queue dry, owner asked, ...>"`. It reopens a
   closed day.
2. Read `.wuwei/goals.md`, `wuwei plan` and `wuwei status`. On a later pass, start from what changed
   since the last one.
3. If `goals.md` has no filled goal, propose up to three goal blocks from the repositories and the
   owner's words and ask once: `goal: approve these goals?` with Approve and Change. This is the only
   question a plan pass asks inside its own work.
4. Launch the lead (agent type `lead`) in the background with the goals, the current plan, the
   board and the owner's words. It returns candidates with scores and a one-line evidence per score.
5. Add each candidate: `wuwei plan add <id> "<title>" --goal G-n --repo owner/name --tier light|standard|full`
   with `--value --time --risk --size` (WSJF) or `--reach --impact --confidence --effort` (RICE), and
   `--why "<evidence>"`. Drop what no longer serves a goal: `wuwei plan drop <id> --reason "..."`.
6. Show the ranked plan in one short table. Work outside the goals is asked once
   (`scope: add <title> outside the goals?`); everything inside them starts now.
7. Start the work as the planner charter says: builders in parallel, highest score first.

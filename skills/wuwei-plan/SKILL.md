---
name: wuwei-plan
description: Plan or re-plan the WUWEI day. Use at the start of the day, when the queue runs dry, when the owner adds, drops or changes work, or whenever the day changes. Runs any number of times a day.
---

# /wuwei-plan

A plan pass. The plan in `.wuwei/plan.json` is a running queue; this pass adds, drops or re-ranks.

1. Run `wuwei plan pass --reason "<why this pass: morning, queue dry, owner asked, ...>"`. It reopens a
   closed day.
2. Read `.wuwei/goals.md`, `.wuwei/standards.md`, `wuwei plan` and `wuwei status`. On a later pass,
   start from what changed since the last one.
3. If `goals.md` has no filled goal, propose up to three goal blocks from the repositories and the
   owner's words and ask once: `goal: approve these goals?` with Approve and Change.
4. Launch the lead (agent type `lead`) in the background with the goals, the plan, the board and
   the owner's words. It returns ready candidates (promise, acceptance scenarios, repository,
   files, tier, scores with evidence) and names the riskiest item with the cheapest way to learn
   early whether it works.
5. Add each candidate: `wuwei plan add <id> "<title>" --goal G-n --repo owner/name --tier light|standard|full`
   with `--value --time --risk --size` (WSJF) or `--reach --impact --confidence --effort` (RICE), and
   `--why "<evidence>"`. Drop what no longer serves a goal: `wuwei plan drop <id> --reason "..."`.
6. Show the plan as a view: run `wuwei plan view`. With a tool that renders HTML (a visualize or
   show-widget tool), render the output of `wuwei plan view --html`; otherwise show the printed
   summary and the path of `.wuwei/plan.html`, which the owner can open in a browser.
7. Ask once, with AskUserQuestion: `plan: approve this plan? <the line wuwei plan view prints>`, options
   `Approve` and `Change`. On Approve, WUWEI marks the items approved. On Change, apply what the owner
   said, show the view again and re-ask. The answer is recorded only from AskUserQuestion. Work
   outside the goals sits in the view under unplanned; the same question covers it.
8. Start the approved work as the planner charter says: builders in parallel, highest score first,
   none in a repository under andon. Items added later wait on the board as `awaiting plan approval`
   until the next view is approved.

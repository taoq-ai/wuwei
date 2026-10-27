---
name: wuwei-run
description: Start or resume the WUWEI day: a plan pass when the plan needs one, the owner's approval, then the work keeps moving. Use at the start of the day, when the queue runs dry, when the owner adds, drops or changes work, or whenever the day changes. Runs any number of times a day. Not for a routine pass over work already in flight (/wuwei-watch) or the day's checkpoint and retro (/wuwei-close).
---

# /wuwei-run

Start or resume the day. It opens with a plan pass. The plan in `.wuwei/plan.json` is a running
queue; this pass adds, drops or re-ranks.

1. Run `wuwei plan pass --reason "<why this pass: morning, queue dry, owner asked, ...>"`. It
   reopens a closed day. For each goal it names as past its date, read the goal's measure as step 5
   says, then ask the question it prints with Yes and No, the `<evidence>` replaced by that reading.
   WUWEI records the answer; a met goal gets no new items, and a No waits until the owner moves the
   goal's date.
2. Read your charter `planner.md` (the session start names its path), `.wuwei/goals.md`,
   `.wuwei/standards.md`, `wuwei plan` and `wuwei status`. On a later pass, start from what changed
   since the last one.
3. Start what is already approved before you launch the lead. An approved item with no pull
   request and no running seat shows on the board as `no pull request yet`. Start it now, as the
   last step says, while items in progress are under the WIP limit; it never waits on the lead or
   on this pass's plan question. On a resumed day
   with open PRs, start the shepherd and the owed gate wave first (the board's `team` row names
   them), before any resume list or finished Codex round.
4. If `goals.md` has no filled goal, propose up to three goal blocks from the repositories and the
   owner's words and ask once: `goal: approve these goals?` with Approve and Change.
5. Before launching the lead, read every goal measure that `goals.md` states in a tracker's
   states (Linear, Jira) with your own MCP tools, and put the states as you read them in the
   lead's brief. Pass a measure you cannot read (no tool, no access, an error) as unmeasured,
   with the reason. The lead has no tracker tools; their names differ per workspace.
6. Inspect the active dispatch schema, then launch the lead in the background with the goals,
   the plan, the board and the owner's words. On Codex, use `agent_type: lead` only when the
   active schema supports it or a supported role mapping supplies it. A task name or prompt
   cannot establish a role. Without role support, report the capability gap and keep the
   returned identity unconfirmed. It returns ready
   candidates (promise, acceptance scenarios, repository, files, tier, scores with evidence) and
   names the riskiest item with the cheapest way to learn early whether it works.
7. Add the lead's candidates in one call: `wuwei plan add --from .wuwei/candidates.json` (scores,
   promise and acceptance included). One item added later: `wuwei plan add <id> "<title>" --goal G-n
   --repo owner/name --tier light|standard|full` with `--value --time --risk --size` (WSJF) or
   `--reach --impact --confidence --effort` (RICE), `--why "<evidence>"`, `--promise "<promise>"` and
   one `--accept "<given, when, then>"` per scenario. Adding an id again re-scores it in place;
   `wuwei plan restore <id>` reopens a parked or dropped item. Drop what no longer serves a goal:
   `wuwei plan drop <id> --reason "..."`. Never edit `.wuwei/plan.json` by hand.
8. Show the plan as a view: run `wuwei plan view`. With a tool that renders HTML (a visualize or
   show-widget tool), render the output of `wuwei plan view --html`; otherwise show the printed
   summary and the path of `.wuwei/plan.html`, which the owner can open in a browser.
9. Ask once, with the harness's question tool (AskUserQuestion; `request_user_input` in Codex):
   `plan: approve this plan? <the line wuwei plan view prints>`, options `Approve` and `Change`. On
   Approve, WUWEI marks the items approved. On Change, apply what the owner said, show the view
   again and re-ask. The answer is recorded only from that question tool. Work outside the goals
   sits in the view under unplanned; the same question covers it.
10. Start the approved work as the planner charter says: highest score first, under the WIP limit
   and the seat ceiling, none in a repository under andon. Items added later wait on the board as `awaiting plan approval`
   until the next view is approved.

---
layout: default
---

# Concepts

[Home](index.html)

## Glossary

The words the rest of these pages use, two lines each.

### Seat

One agent session with one job and its charter: the lead, a builder, a gate reviewer, the shepherd or the steward.
The planner starts seats as the day needs them; each stops when its job is done.

### Gate

A review of a change by an agent that did not write it: architecture, quality or security.
The morning gate is different: your approval of the day's plan before anything starts.

### Sentinel

The four reviewing roles: goal, architecture, quality and security.
Architecture, quality and security run as the gates on each change; the goal sentinel checks work against its goal.

### Shepherd

The seat that takes a pull request from raised to merged: reviewers, replies and CI fixes.
It merges only through the merge policy and never approves a pull request.

### Steward

The seat that watches the day for drift and loops, and compiles the retro at close.
It proposes rule changes; you promote the ones you want.

### CAP

How many build seats may run at once (`cap`, default 1).
The morning gate asks you to confirm it each day.

### Envelope

The day's working window: start time, end time and net build hours.
Work admitted during the day must fit the remaining build hours.

### Tier

Review tier: light (one reviewer agent) or standard and full (three), set per change from its size and risk.
Outbound tier: a message sent as you either goes out at once or waits as a draft for your approval.

### Soak

The wait after the last push or approval before WUWEI merges by itself (`merge.soak_minutes`, default 30).
During it you can stop the merge from your phone.

### Delta

The second review after a fix round: only the gates that asked for the fix look again.
After it the pull request is raised, or the item comes to you.

### Park

Stop work on an item for now, with a decision record that says why.
Close accepts a parked item once that decision is recorded.

### Carry

Move an unfinished item to tomorrow's plan, with a decision record that says so.
The next morning gate offers it again as carry-over.

### Nudge

A reminder that something needs you, but not right now: on the status line and in `bin/wuwei nudges`.
Nudges wait for you; pages interrupt.

### Page

An alert that interrupts you at once, even outside your working hours, for example a failed heartbeat probe.
It shows on the status line and reaches your phone.

### Digest

The 12-character code a host terminal command shows before it changes a file; type it to confirm.
Also the summary of waiting decisions sent every two hours when you choose Batch in the interview.

### Unmeasured

A check that could not run or could not read its source; WUWEI reports it and never counts it as clean.
On a first day some sources are unmeasured until you set them up, for example `meeting unmeasured`.

### Mandate

The block at the end of every seat brief: what the seat decides alone, what it decides and records, and what goes to you.
Seats do not ask you what their mandate lets them decide.

### Trust surface

Code where a mistake costs most: auth, credentials, input parsing, permissions, and the areas you add in the interview.
A change there gets three reviewer agents and is never merged without you.

### Host terminal

A terminal you type in yourself, outside Claude Code's agent tools.
Owner commands such as `bin/wuwei config set` refuse to run anywhere else.

## Roles

The shipped charters define planner, lead, builder, shepherd, steward, and four sentinels: goal, architecture, quality and security. Generated agent files in `agents/` carry the charters and tool allowlists. The planner owns the day, the lead shapes work, builders implement, sentinels check, the shepherd follows pull requests and the steward maintains procedure. `/wuwei plan` runs the day, starting with the owner's morning gate; see the [daily path](daily.html).

## Guards

Claude Code hooks call the WUWEI CLI. Guards act when a tool is used and refuse relevant unsafe actions inside a WUWEI workspace or configured repository. Outside that scope they return clean. The three outcomes are 0 clean, 1 findings and 2 could not run. A relevant parse or measurement failure returns 2 with a reason. The CLI also records traces and events. See [security](security.html) for the trust boundary.

## Security posture

`security.posture` sets what warns and what blocks per area: `observe`, `guarded` (the default) or `strict`, with per-area overrides under `[security.areas]`. A `warn` level still runs the guard, records the refusal as a `guard.would_refuse` event and lets the call through. Every enforced refusal ends with a `posture:` line naming the area, its level and the key that changes it. See [security posture](security.html#security-posture) for the table.

`observe` is the old shadow mode (`guards.mode = "shadow"` still means it). Use it for the first week on a project, to see what the guards would stop in your own habits before they stop anything. Some refusals never relax, in any posture: writes to state, events, config and generated instructions, verdicts and decisions (`records`), and owner-only actions: the deployment ban, the merge policy, approvals and owner markers, and approve-tier messages and canary or honeytoken egress. Relaxing those would corrupt the records the report is built from or let a seat act as the owner. The heartbeat probe session is never relaxed either.

`bin/wuwei shadow report` and the day report group the would-be refusals by guard, with counts and the three most frequent forms. A form refused more than three times with no later page is named as a candidate for a guard fix or a calibration proposal. The status line shows the posture when it is not `guarded`, each `observe` session starts with a line saying so, and after `guards.shadow_days` one nudge asks you to switch to `guarded` or extend. Under `guarded` or `strict` a warning is a nudge, one per guard per day.

MCP registry findings warn by default. A finding is a heuristic over tool descriptions, and a first measurement is new information, not drift. The publishing guarantee does not rest on the registry gate; it rests on the code host protections and the credential layout (design 9.1). So a false positive must not stop the day: under `guarded` the finding is filed as an owner decision and shown on the board with `bin/wuwei mcp decide D-<n> proceed`, and seats launch. Use `strict` for a repository where a changed tool must stop seats until the owner decides.

## Seat launch contract

The planner launches every seat from the actions `build next` and `dispatch next` return; see the [daily path](daily.html). The low-level launch contract is on the [recovery](recovery.html#seat-launch-contract) page.

Commit and push guards follow the target repository even when the session starts
elsewhere. This includes `git -C`, `--git-dir`, `--work-tree`, repository environment
variables, and literal `cd` chains inside or outside subshells. Managed worktree
anchors connect external checkouts to their workspace. An unrelated repository
remains outside scope even when `WUWEI_WORKSPACE` selects another workspace.
Ambiguous directory changes or unresolved targets may require separate, literal
commands. A detached HEAD refusal asks you to check out a branch before pushing;
other context failures identify the failed read and a corrective action.

## Host terminal actions

Some commands are the owner's alone: `wuwei decision outcome`, `wuwei state recover`, `wuwei integrity reconfirm`, `wuwei mcp decide`, `wuwei drafts approve` and `drafts drop`, `wuwei goals edit` and `voice edit` (except that the planner records goals and voice you approved at the morning gate with `--file`, outside the strict posture), `wuwei watch uninstall`, `wuwei listen uninstall`, `wuwei remote ack`, `wuwei config promote`, `config set` and `config add-repo`, and `wuwei setup`. Agent tool hooks refuse them (`--help` or `-h` alone is allowed), so run them in a host terminal. The ones that ask you to type a digest exit 2 without a terminal. See [host terminal actions](reference.html#host-terminal-actions).

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, index and changelog. Day records live under `.wuwei/days/`. Settled facts belong in notes; procedure belongs in charters. The CLI provides `note`, `index`, `consolidate`, `payload` and `promote` commands. Goals and voice are the owner's: the lead proposes, the morning gate confirms and the planner records them, and the owner can edit them later; seats propose changes for promotion. The index is generated and notes are bounded by configuration defaults.

## Day flow

Plan, Build, Review, Close. `/wuwei plan` runs the morning gate, then the planner loops `build next` and `dispatch next` for each approved item, raises the PR and closes the day; phases move by themselves. The [daily path](daily.html) is the owner's walkthrough and the [recovery](recovery.html) page covers the rest.

## PR ownership

`bin/wuwei pr raise` links a newly raised PR to its approved item. To take
ownership of an existing open PR, run
`bin/wuwei pr claim owner/repo#number --item ITEM`. Both commands record the
item link and the day's owned PR set.
The item link lets merge checks and lead-time metrics find the same work.
`wuwei state set items.ITEM.pr` is reserved for these commands.

`bin/wuwei pr state [owner/repo#number ...]` reads fresh code-host evidence for today's
raised and claimed PRs and emits JSON rows with state, dispatch instructions, deadline
and per-PR exit status. Without arguments it measures the complete ownership union.
Exit 1 means action is required; exit 2 means a PR could not be measured and includes a reason.
Dispatch instructions are data for the shepherd; this command does not execute them.

Conflicts require rebase, resolution, fast checks and push. Red CI requires a fix round.
Outstanding review requests and unanswered threads require triage: fixes, outward-tier
replies, or owner decisions for disagreements and scope changes. Stale reviews require
requesting reviewers again and posting in the review channel. Approved PRs go through
`wuwei merge` or a merge decision. Closed, unmerged PRs require an owner decision.
Waiting within the review window and merged PRs have no action deadline.

The watch produces the same action deadlines while polling. Repeated observations do
not postpone an unresolved action. Overdue actions produce a nudge, then a page at twice
the action interval. The planner's Stop hook rechecks fresh evidence and refuses overdue
actions, naming the PR, state and action. Only a verified owner parking decision exempts
a PR; carry-forward applies to day close. See [configuration](configuration.html) for
`pr.action_minutes` and `pr.review_window`.

## Day close

`bin/wuwei close` and the planner Stop hook after a close request refuse while an
approved item remains open or blocked without a park or carry decision, an owner
decision remains pending, or a pushed item branch lacks a raised or claimed PR.
For each open item the refusal asks one question: carry it to tomorrow
(recommended), park it, or keep working, with the command for each answer. It names
each decision or branch. `bin/wuwei close --widget` prints the same questions as
AskUserQuestion widgets and writes nothing. `close` launches the close steward
review only once these item obligations are clear. Unreadable evidence returns exit
2 with a reason; unresolved work returns exit 1. Existing PR, reply, visibility
and retro requirements still apply. The Stop hook blocks once per stop attempt and
exits 0 on Claude Code's retry, so it never traps the session; `bin/wuwei close`
still reports every finding.

`bin/wuwei plan carry ITEM` and `bin/wuwei plan park ITEM [--reason TEXT]` write a
valid two-way decision record with blast radius `own branch`, route it and print
its ID, for example `D-1: carried ITEM`. Park also pauses an active item. Carried
items come back with tomorrow's `plan approve --import-yesterday`. The recorded
outcome must match the file. A parked phase alone does not count.
A merged phase also needs fresh merge evidence from the linked PR.
The build loop creates and records this decision automatically after repeated
fast-check failures or exhausted iterations. Its `D-<n>.md` file passes
`bin/wuwei decision lint` and does not overwrite earlier decisions.

A linked PR's externally verified owner park or carry also accounts for its item.
Editing an owner decision's Outcome does not prove an owner action. An owner
decision answered with `bin/wuwei decision outcome D-<n> OPTION` counts as
resolved, and the command writes the chosen option into the record's `Outcome:`
line.
Pushed branch checks read remote-tracking refs in recorded item worktrees through
the VCS port, without fetching. A parked item still needs a raised or claimed PR
when its branch has been pushed.

## Builder steps

Claude Code builders run as subagents in the planner session. After writing a builder
brief with its worktree, call `wuwei build next <item>`. It returns one JSON action:
`launch` supplies the Agent prompt, `continue` supplies the same agent's resume ID and
feedback, `check` supplies a command to run through Bash, `park` supplies a reason and
numbered decision path, and `done` means checks passed and the item moved to `gate`
(or to `delta` after a fix build). Call next again after executing
the action. Hooks register the seat and record its result; unchanged state returns the
same action, so execute each action once. Never poll a Claude seat through the CLI.

A check command records measurements itself. Exit 1 means failed checks and another next
call; exit 2 means unmeasured and requires resolving the reported error. The old blocking
Claude build form exits 2 and directs you to build next. Codex retains
`wuwei build <item> <brief> <worktree>` and executes the same action loop with polling.
Default `host.seats` is four: one builder plus three parallel gates. Increase the host
ceiling when increasing cap.

## Review tiers

At an item's first gate, `dispatch next` computes its review tier, `light`, `standard` or
`full`, from the diff size against `repos.gates.light_max_lines`, trust and never-auto
paths, the lead flags, the track, `repos.gates.floor` and an optional lead `tier`. A light
item gets the quality gate only; standard and full get arch, quality and security. A lead
tier below the computed one is refused and recorded as a reason, and the returned action
carries the `tier`. See [configuration](configuration.html#workspace-and-repositories) and
the [lead plan JSON](reference.html#lead-plan-json).

With `gates.second_opinion = "<runtime>:<model>"`, standard and full items get one more gate:
the role in `gates.second_opinion_role` (quality by default) runs again on that runtime and
model, named `<role>@<runtime>`. Its verdict goes through the same lint and receive. A blocking
finding from either model blocks, a FIX from only the second opinion opens the same single fix
round, and the model that raised it does the delta. Each verdict records its cost and duration,
and the retro's `## Second opinion` section lists the findings each model raised alone, so you
can turn it off when it stops paying.

## Writing for the owner

`owner.verbosity` sets how much decisions, the digest, PR nudges, the DM and the report say to you: `brief` (the default), `standard` or `full`, with one key per surface (see [configuration](configuration.html)). Anything left out is one command away: `bin/wuwei decision show D-<n> --full` on the host or `more D-n` in the DM. Seats rewrite text written for a person with the humanizer skill, version 3.1.0, MIT license, when it is installed, and otherwise follow the ten-line checklist under Writing for a person in `charters/_common-authoring.md`. The CLI counts the mechanical tells as a `style` finding on drafts and decision records and as the `ai_tells` metric in the retro and, at standard or full, the report; a tell never blocks a send. Only an em dash or an emoji is refused.

## Decision classes and cruise levels

Cruise mode is designed in
[design spec 5.8.1](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md)
and not built: decisions would carry a class, and the CLI would answer some classes itself
at levels L0 to L3. Today every owner decision goes to the owner.

Every seat prompt ends with a mandate block built from those class levels
(`decisions.cruise.levels`, the 5.8.1 defaults otherwise), the interview's trust-surface
line and `deploy.deny`: what the seat decides alone, what it decides and records, and what
goes to the owner, closing with "Nothing else is a question." The levels only shape this
text; cruise answering is not built. Assume and record: a two-way
open question inside the item is not asked; the seat takes its recommendation and records
it under `Assumptions:` in the spec or PR body, and gates review it as an `Assumption:`
finding. A seat that stops on a question to the owner without a valid decision id is
flagged by the SubagentStop guard (and by the Codex and headless paths), and `dispatch
next` refuses until the planner acknowledges the note.

A confirmation from someone outside the loop never holds reversible work: the seat routes
the record with `decision route D-n --external <item>` and continues. After
`decisions.wait_hours` weekday hours without your answer, the sweep confirms the
recommendation on a two-way door or parks the item on a one-way door, and records
`decision.waited`.

Negotiation loops: when an item goes back and forth (records, verdicts, restarts and fix
requests above `steward.loop_threshold` in `steward.loop_window_hours`, or a second fix
round), the steward raises one `negotiation.loop` nudge per item per day, a page when the
goal date has passed, and the listener sends the summary to your DM. It reports; the
negotiation budget in the charters is what stops the rounds.

## Sessions

Several Claude Code sessions can share a workspace. Hooks register each one in day state
with its role, last hook and claimed items; a session idle past `sessions.stale_seconds` is
stale and its claims lapse. One session is the planner, a second takes over with
`plan session --take-over`, and `sessions.rotate_after` rotates the planner on a schedule.
See [sessions](reference.html#sessions) and [long sessions](daily.html#long-sessions).

## Listener

`bin/wuwei listen` polls the inbound source, such as a Slack DM, into the workspace inbox.
The responder wakes the planner and handles commands only from the pinned owner, with a
second factor where a command needs one. While running it also probes raised and claimed
PRs with conditional requests, sends each `pr.changed` summary to the DM and, with
`shepherd.autostart = true`, starts a headless shepherd seat that never merges. See
[remote operation](remote.html) and
[running the listener](configuration.html#running-the-listener).

## Heartbeat

On every tick the watch runs a fixed table of probes: a refused and an allowed hook call,
state, integrity, config, clocks, the status line, the planner and memory. Health shows on
the status line, a failed probe raises one page, a probe that turns from ok to failed is
behaviour drift, and a healthy heartbeat pings an external dead-man monitor. See the
[heartbeat reference](reference.html#heartbeat).

## Cockpit and board

`bin/wuwei dashboard` serves the read-only day board on loopback. The plugin's MCP server
runs `bin/wuwei board` and offers the `wuwei_board` tool inside Claude Code; it is declared
in the signed `plugin.json`, so integrity covers it. Answering a decision or approving a
draft stays a host terminal action. See the [daily path](daily.html#6-close).

---
layout: default
---

# Concepts

[Home](index.html)

## Roles

The shipped charters define planner, lead, builder, shepherd, steward, and four sentinels: goal, architecture, quality and security. Generated agent files in `agents/` carry the charters and tool allowlists. The planner owns the day, the lead shapes work, builders implement, sentinels check, the shepherd follows pull requests and the steward maintains procedure. **Planned:** `/wuwei plan` orchestration and its morning gate.

## Guards

Claude Code hooks call the WUWEI CLI. Guards act when a tool is used and refuse relevant unsafe actions inside a WUWEI workspace or configured repository. Outside that scope they return clean. The three outcomes are 0 clean, 1 findings and 2 could not run. A relevant parse or measurement failure returns 2 with a reason. The CLI also records traces and events. See [security](security.html) for the trust boundary.

## Seat launch contract

Write and log a brief with `wuwei brief <role> <item> <name>`, then obtain launch
instructions with `wuwei runtime dispatch <role> <brief> <worktree>`. With the Claude
runtime, pass the returned `prompt` unchanged to Agent and use its `agent_type`
(`wuwei:<role>`) as Agent's `subagent_type`. Supply an Agent description and launch
from the workspace root, which is the hook payload's `cwd`.

The exact first line is `WUWEI brief: <relative brief path>`. The path is relative
to the workspace root, for example `.wuwei/days/2026-09-29/briefs/builder-1.md`,
not relative to the item's worktree. Do not prepend instructions to the prompt.
The guard still requires the logged, unchanged brief and matching role, fresh
evidence and available capacity; a missing first line is refused with the required format.

The core function `wuwei.brief.launch_prompt` generates these instructions for all
Claude roles. `wuwei runtime continue <job-json> <feedback>` preserves the reference
and includes feedback for the same seat. It does not authorize a second launch
with a consumed brief. `wuwei steward run --trigger close` returns the same contract
inside `steward_launch`, through the configured runtime adapter. Use these generated
instructions for lead, builder, sentinel, shepherd and steward seats.

Commit and push guards follow the target repository even when the session starts
elsewhere. This includes `git -C`, `--git-dir`, `--work-tree`, repository environment
variables, and literal `cd` chains inside or outside subshells. Managed worktree
anchors connect external checkouts to their workspace. An unrelated repository
remains outside scope even when `WUWEI_WORKSPACE` selects another workspace.
Ambiguous directory changes or unresolved targets may require separate, literal
commands. A detached HEAD refusal asks you to check out a branch before pushing;
other context failures identify the failed read and a corrective action.

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, index and changelog. Day records live under `.wuwei/days/`. Settled facts belong in notes; procedure belongs in charters. The CLI provides `note`, `index`, `consolidate`, `payload` and `promote` commands. The owner edits goals and voice; seats propose changes for promotion. The index is generated and notes are bounded by configuration defaults.

## Day flow

Plan, Build, Review, Close is the intended flow. Today's CLI supports individual guard, state and memory operations. **Planned:** the skill that runs the full day from `/wuwei plan`.

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
The refusal names each item, decision or branch. Unreadable evidence returns exit
2 with a reason; unresolved work returns exit 1. Existing PR, reply, visibility
and retro requirements still apply. Stop retry flags do not bypass these checks.

A seat may park or carry its own item with a valid two-way decision whose blast
radius is `own branch` or `own PR`. Use `Outcome: parked ITEM` or
`Outcome: carried ITEM`, then run `bin/wuwei decision route D-1` with its actual
ID. The recorded outcome must match the file. A parked phase alone does not count.
A merged phase also needs fresh merge evidence from the linked PR.
The build loop creates and records this decision automatically after repeated
fast-check failures or exhausted iterations. Its `D-<n>.md` file passes
`bin/wuwei decision lint` and does not overwrite earlier decisions.

A linked PR's externally verified owner park or carry also accounts for its item.
Editing an owner decision's Outcome does not prove an owner action. Owner-routed
decisions remain pending until existing PR disposition verification supplies that
proof; a general authenticated owner-completion command is not yet available.
Pushed branch checks read remote-tracking refs in recorded item worktrees through
the VCS port, without fetching. A parked item still needs a raised or claimed PR
when its branch has been pushed.

## Builder steps

Claude Code builders run as subagents in the planner session. After writing a builder
brief with its worktree, call `wuwei build next <item>`. It returns one JSON action:
`launch` supplies the Agent prompt, `continue` supplies the same agent's resume ID and
feedback, `check` supplies a command to run through Bash, `park` supplies a reason and
numbered decision path, and `done` means checks passed. Call next again after executing
the action. Hooks register the seat and record its result; unchanged state returns the
same action, so execute each action once. Never poll a Claude seat through the CLI.

A check command records measurements itself. Exit 1 means failed checks and another next
call; exit 2 means unmeasured and requires resolving the reported error. The old blocking
Claude build form exits 2 and directs you to build next. Codex retains
`wuwei build <item> <brief> <worktree>` and executes the same action loop with polling.
Default `host.seats` is four: one builder plus three parallel gates. Increase the host
ceiling when increasing cap.

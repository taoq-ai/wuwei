# Concepts

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

The seat that reviews the day at each sweep and at close, and compiles the retro.
It proposes rule changes; you promote the ones you want.

### CAP

How many build seats may run at once (`cap`; `0` derives it from the host at every sweep).
The morning gate asks you to confirm it each day, and the launch guard refuses a builder past it.

### Seats per goal

How the day's CAP splits across goals, for example `3 seats: G-1 2, G-2 1 (CAP 3)`.
The plan counts the first CAP items of the queue per goal; "Change something" at the morning gate changes it.

### Envelope

The day's working window: start time, end time and net build hours.
Work admitted during the day must fit the remaining build hours.

### Tier

Review tier: light (one reviewer agent) or standard and full (three), set per change from its diff: a docs-only change gets one reviewer, code or a trust surface gets three. The tier also sets the process depth: see [review tiers](#review-tiers).
Outbound tier: a message sent as you either goes out at once or waits as a draft for your approval.

### Soak

The wait after the last push or approval before WUWEI merges by itself (`merge.soak_minutes`, default 30).
During it you can stop the merge from your phone. A PR that turns a check failing on its base green skips it.

### Delta

The second review after a fix round: only the gates that asked for the fix look again.
After it the pull request is raised, or the item comes to you.

### Park

Stop work on an item for now; the item records why.
A PARK verdict, the round cap or your No on an ESCALATE card parks it, and only you resume it
(`plan resume`, on its Owner step card).

### Carry

Move an unfinished item to tomorrow's plan; the item records it.
The next morning gate offers it again as carry-over.

### Page

An alert that interrupts you at once, even outside your working hours, for example a failed heartbeat probe.
It shows on the status line and reaches your phone.

### Digest

The 12-character code a host terminal command shows before it changes a file; type it to confirm.
Also the summary of waiting decisions sent every two hours when you choose Batch.

### Unmeasured

A check that could not run or could not read its source; WUWEI reports it and never counts it as clean.
On a first day some sources are unmeasured until you set them up, for example `meeting unmeasured`.

### Mandate

The block at the end of every seat brief: decide alone what the brief, the charter and the standards answer;
record two-way choices under `Assumptions:`; name a one-way, scope, goal or trust-boundary question in the result.

### Trust surface

Code where a mistake costs most: auth, credentials, input parsing, permissions, and the boundaries you name in `[boundary]`.
A change there gets three reviewer agents and is never merged without you.

### Host terminal

A terminal you type in yourself, outside Claude Code's agent tools.
Owner commands such as `bin/wuwei config set` refuse to run anywhere else.

### Humanizer

The writing checklist seats apply to text for a person, from the humanizer skill.
A lint checks outward text for its mechanical tells before it is sent.

### Spec engine

The tool each non-trivial item is specified with before it is built: spec-kit (default), superpowers or OpenSpec.
`[spec] engine` picks it; the hooks keep its steps in order in the item's worktree.

### Strict mode

`[spec] mode = "strict"` (default): source edits and the gates wait until the engine's steps are done.
`advisory` warns once per item and day instead; `off` checks nothing.

### Ticket

The tracker issue an item is built under: a Linear, Jira or GitHub id such as `ENG-12`.
An item needs none to start, build, pass its gates or raise its PR.

### Tracker hygiene

An item's ticket follows its lifecycle as duties (claim, in review with the PR link, done
with the merged note), bugs found midway become linked tickets, and the item's progress,
verdicts and carried or parked notes land on its ticket.

### Fold

One comment that stands for the rest of a ticket's updates once its daily comment cap is reached.

### Adopted

An item made from work begun outside WUWEI: `pr claim` on an open PR with no item creates it,
and `worktree adopt` registers an existing worktree as its checkout.

## Roles

The shipped charters define planner, lead, builder, shepherd, steward, and four sentinels: goal, architecture, quality and security. Generated agent files in `agents/` carry the charters and tool allowlists. The planner owns the day, the lead shapes work, builders implement, sentinels check, the shepherd follows pull requests and the steward maintains procedure. `/wuwei plan` runs the day, starting with your morning gate; see the [daily path](daily.md).

## Guards

Claude Code hooks call the WUWEI CLI. Guards act when a tool is used and refuse relevant unsafe actions inside a WUWEI workspace or configured repository. Outside that scope they return clean. The three outcomes are 0 clean, 1 findings and 2 could not run. A relevant parse or measurement failure returns 2 with a reason. The CLI also records traces and events. See [security](security.md) for the trust boundary.

## Security posture

`security.posture` sets what warns and what blocks per area: `observe`, `guarded` (the default) or `strict`, with per-area overrides under `[security.areas]`. A `warn` level still runs the guard, records the refusal as a `guard.would_refuse` event and lets the call through. Every enforced refusal ends with a `posture:` line naming the area, its level and the key that changes it. See [security posture](security.md#security-posture) for the table.

`observe` is the old shadow mode (`guards.mode = "shadow"` still means it). Use it for the first week on a project, to see what the guards would stop in your own habits before they stop anything. Records never relax, in any posture: writes to state, events, config and generated instructions, verdicts and decisions (`records`), owner disposition markers, canary or honeytoken egress, and a seat launch naming a missing brief. Relaxing those would corrupt the records the report is built from or let a seat act as you. Below `strict` an owner-only action asks you on a card instead: a deploy, release or publish, and a message that waits for your approval. The merge policy and approvals stay yours. The heartbeat probe session is never relaxed either.

The day report's `## Shadow` section groups the would-be refusals by guard, with counts and the three most frequent forms. A form refused more than three times with no later page is named as a candidate for a guard fix or a calibration proposal. The status line shows the posture when it is not `guarded`, each `observe` session starts with a line saying so, and after `guards.shadow_days` `bin/wuwei doctor` asks you to switch to `guarded` or extend. Under `guarded` or `strict` a warning is a `guard.would_refuse` event in the day's log, one per guard per day.

## Owner-only actions

An owner-only deploy, release or `deploy.deny` publish never runs from a session on its own. When a seat or the planner tries one, the deploy guard refuses it and prints an Owner step card for that exact command. The planner asks you the card. Your Yes lets that same command run today; any other command asks its own card. No config line and no hook answers for you.

A merge happens only through the merge policy (`bin/wuwei merge <pr>`, or `bin/wuwei pr act <pr>`). Quiet hours, the daily cap and the soak are waits the policy clears later. The gates must pass at the current head, required checks must be green with approvals at that head and no changes requested, threads and obligations must be clear, `merge_deploys = false` must hold, and the repository must allow the merge method (`repos.merge_method`; under `auto` squash, then rebase, then merge). When one fails, the reason names it and the next step. The other rules are yours to decide: `merge.auto` off, a tripped breaker, an item outside the approved plan, a risk flag, a spent cycle budget, a never-auto path, a diff over `max_changed_lines` and a path in `merge.owner_paths`. When only those stand between the pull request and a merge, `bin/wuwei merge <pr>` prints one Owner step card for that pull request at its head, `wuwei next` names it, and your Yes merges it. A `trust_surface` pull request waits on its security gate, not on you. A `gh pr merge` typed in a session is refused with the reason and `bin/wuwei merge <pr>`, which journals and watches the merge.

## Seat launch contract

The planner launches every seat from the actions `build next` and `dispatch next` return; see the [daily path](daily.md). The low-level launch contract is on the [recovery](recovery.md#seat-launch-contract) page.

Commit and push guards follow the target repository even when the session starts
elsewhere. This includes `git -C`, `--git-dir`, `--work-tree`, repository environment
variables, and literal `cd` chains inside or outside subshells. Managed worktree
anchors connect external checkouts to their workspace. An unrelated repository
remains outside scope even when `WUWEI_WORKSPACE` selects another workspace.
Ambiguous directory changes or unresolved targets may require separate, literal
commands. A detached HEAD refusal asks you to check out a branch before pushing;
other context failures identify the failed read and a corrective action.

## Host terminal actions

Some commands are yours alone: `wuwei state recover` and `wuwei integrity reconfirm`. The rest are `wuwei watch uninstall`, `wuwei config promote`, `config set` and `config add-repo`, and `wuwei telemetry send`. Most ask their own Owner step card in the session: the command prints it, the planner asks it, and the command runs on your Yes. See [host terminal actions](reference.md#host-terminal-actions).

## Outward sends

A message to other people goes out through an MCP tool only when that exact tool is on `outward.allow`. Any other write is refused, naming the one line to add, `bin/wuwei config set outward.allow '["<tool>"]' --add`. The planner runs it, it asks you its Owner step card, and the call passes on retry. A tool whose name is neither a read nor a write and that names no channel runs, and the lint logs that line. This holds with `guards.enforce` on or off.

A write whose every destination is yours is local, never an outward send: your Slack DM, your own canvas or page, a mail only to you. It passes without `outward.allow`, and the lint skips its third-person rules. A tool that acts only on your machine, such as the terminal, is local too. See [your own surfaces](configuration.md#your-own-surfaces).

WUWEI's own duties go through its adapter ports, which you configure: review pings, tracker comments and tickets, the day report and PR thread replies. Each passes the canary check and the outward lint, then goes out.

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, index, goals and changelog. Day records live under `.wuwei/days/`. Settled facts belong in the spine; procedure belongs in charters. The CLI provides `index`, `payload` and `promote` commands. Goals are yours: the lead proposes, the morning gate confirms and `wuwei plan approve` records them; a later change to `memory/goals.md` is recorded by the next gate approval. The index is generated: one line per past day.

A session loads the spine, then the past-day lines of the index and the last promote line, within `memory.budget_tokens`; over it today is left out first. Rules live only in charters: the retro writes charter proposals and `wuwei promote` lands them. `wuwei memory export --claude` writes the charter rules into a marked block in `CLAUDE.md`, so the harness memory sees them; the records stay the one source and nothing reads the block back.

## Day flow

Plan, Build, Review, Close. `/wuwei plan` runs the morning gate, then the planner loops `build next` and `dispatch next` for each approved item, raises the PR and closes the day; phases move by themselves.

The day starts in parallel. WUWEI derives CAP from the host, by one of two rules. Claude subagent seats run inside one Claude process, so free memory says nothing about how many fit: CAP is `host.seats`, or one per core when it is unset, and free memory is not read. When a seat runtime launches its own process (Codex or another external runtime), the memory rule applies. CAP is then the running seats plus the seats that fit above the memory floor at the measured seat cost, one core per seat. It is the median of today's last five readings, so one noisy reading does not move it. Both stay within `budget.tokens_per_day` when set. The plan shows the rule and the measurement, for example `cap 6 (host.seats): subagent runtime, free memory not read` or `cap 4 (memory): median of 4, 5, 4; 16 GB free, 1.5 GB per seat, 8 cores`, and the morning gate splits it into seats per goal. Each sweep derives it again, and the status line shows `seats 3/4 by host.seats`, `by memory` or `by budget`. A positive `cap` in config is your override. After you approve, `wuwei dispatch next --all` lists everything that can move now. Gate items come first, then building items, then planned items up to CAP with each goal's share first. The planner launches the whole set in one turn, an item's three gate seats together. With `cap = 1` the day runs one item at a time. The [daily path](daily.md) is your walkthrough and the [recovery](recovery.md) page covers the rest.

## Tickets and comments

A missing ticket never stops an item: no launch, gate, raise or close refuses over one.
A candidate's `ticket` field, an item discovered from the tracker backlog,
`bin/wuwei tracker create <item>` and `bin/wuwei plan set <item> ticket=<id>` record one.
The lead links an open backlog ticket when one is the item's work; the plan shows it on a
`Ticket:` line and the gate card lists it.

An item with a ticket gets three tracker duties while `adapters.tracker` is not `none`:
`tracker.claim` at its first build (assign, in progress), `tracker.in_review` when its PR is
raised or claimed (the move and a `Pull request: <pr>.` comment) and `tracker.done` when the
PR merges (the move and a `Merged in <pr>.` comment). Each writes `duty.due` before the
tracker call and `duty.done` when every step returned 0. When the adapter call fails after
its retry the duty is recorded `duty.skipped` with the error; close accepts it and the day
report lists it under Skipped duties with its `bin/wuwei tracker move <item> <duty>` retry.
A duty still due is a `duty` row in `wuwei next`, beside the build launches and also for a
merged item, and `wuwei close` waits on it. With `adapters.tracker = "none"` no duty counts.
Builders and sentinels open a linked bug with
`bin/wuwei tracker create --bug <item> "<title>" --evidence "<file:line>" --seat <role>` instead
of widening the item; the planner opens retro follow-ups with `--follow-up`. The finder files it.
It goes out through the tracker port after the outward lint. Each creation is written
once per day and writes one `tracker.created` event naming the seat; the retro's Tickets
seats filed section lists who filed it.

`bin/wuwei tracker log` turns today's events into comments on each ticket, once each:
progress (phases, seat starts and stops, fast checks), gate verdicts and the carried or
parked note; the PR link and the merged note are the duties' own comments. The watch sweep
and `wuwei close` run it. Each goes out through the tracker port after the outward lint.
After `tracker.max_per_item_per_day` comments the last one is a fold, filed under the first
folded kind.

## PR ownership

`bin/wuwei pr raise` links a newly raised PR to its approved item. To take
ownership of an existing open PR, run
`bin/wuwei pr claim owner/repo#number --item ITEM`. Without `--item` the claim uses the item
already linked to the PR, else creates an [adopted](#adopted) item `PR-<number>` under
`--goal` (default: the day's only goal). Both commands record the
item link and the day's owned PR set.
The item link lets merge checks and lead-time metrics find the same work.
`wuwei state set items.ITEM.pr` is reserved for these commands.

`bin/wuwei pr state [owner/repo#number ...]` reads fresh code-host evidence for today's
raised and claimed PRs and emits JSON rows with state, dispatch instructions, deadline
and per-PR exit status. Without arguments it measures the complete ownership union.
Exit 1 means action is required; exit 2 means a PR could not be measured and includes a reason.
Dispatch instructions are data for the shepherd; this command does not execute them.

Conflicts require rebase, resolution, fast checks and push. Red CI requires a fix round.
Outstanding review requests and unanswered threads require triage: fixes, replies
through `pr act --reply`, or owner decisions for disagreements and scope changes. Stale reviews require
requesting reviewers again and posting in the review channel. Approved PRs go through
`wuwei merge` or a merge decision. Closed, unmerged PRs require an owner decision.
Waiting within the review window and merged PRs have no action deadline.

The watch produces the same action deadlines while polling. Repeated observations do
not postpone an unresolved action. Overdue actions produce a warning in the event log, then a page at twice
the action interval. The planner's Stop hook rechecks fresh evidence and refuses overdue
actions, naming the PR, state and action. Only a verified owner parking decision exempts
a PR; carry-forward applies to day close. See [configuration](configuration.md) for
`pr.action_minutes` and `pr.review_window`.

## Day close

`bin/wuwei close` and the planner Stop hook after a close request refuse while work is open.
That is an approved item open or blocked without a park or carry decision, a pending owner
decision, or a pushed item branch without a raised or claimed PR.
For each open item the refusal asks one question: carry it to tomorrow
(recommended), park it, or keep working, with the command for each answer. It names
each decision or branch. `bin/wuwei close --widget` prints the same questions as
AskUserQuestion widgets and writes nothing. `bin/wuwei close --why` prints one line
per approved item saying what holds it and writes nothing. `close` launches the close
steward review once no item is open. Unreadable evidence returns exit 2 with a
reason; unresolved work returns exit 1. A parked or carried item whose branch cannot
be measured (a missing worktree, a branch with no commits) is printed as a note and
never blocks the close. Existing PR, reply, visibility
and retro requirements still apply. The Stop hook blocks once per stop attempt and
exits 0 on Claude Code's retry, so it never traps the session; `bin/wuwei close`
still reports every finding.

`bin/wuwei plan carry ITEM` and `bin/wuwei plan park ITEM [--reason TEXT]` record the
disposition on the item with its reason and print `carried ITEM` or `parked ITEM`. Park also
pauses an active item. Carried items come back with tomorrow's `plan approve
--import-yesterday`. A parked phase without a disposition does not count. A merged phase
also needs fresh merge evidence from the linked PR. The build loop parks an item the same way
after repeated fast-check failures or exhausted iterations, and names `plan resume`.

A linked PR's externally verified owner park or carry also accounts for its item.
Pushed branch checks read remote-tracking refs in recorded item worktrees through
the VCS port, without fetching. A parked item still needs a raised or claimed PR
when its branch has been pushed.

## Builder steps

Claude Code builders run as subagents in the planner session. After writing a builder
brief with its worktree, call `wuwei build next <item>`. It returns one JSON action.
`launch` supplies the Agent prompt, and `continue` supplies the prompt with the feedback
and the stopped agent's ID as `resume`. Launch a `continue` as a fresh Agent with its prompt;
pass `resume` only to an Agent tool that takes it (Claude Code's has none). The fresh
launch continues the same seat and round. `check` supplies a command to run through Bash,
and `park` supplies a reason and numbered decision path. `done` means checks passed and the item moved to `gate`
(or to `delta` after a fix build). Call next again after executing
the action. Hooks register the seat and record its result; unchanged state returns the
same action, so execute each action once. Never poll a Claude seat through the CLI.

A check command records measurements itself. Exit 1 means failed checks and another next
call; exit 2 means unmeasured and requires resolving the reported error. The old blocking
Claude build form exits 2 and directs you to build next. Codex retains
`wuwei build <item> <brief> <worktree>` and executes the same action loop with polling.
`host.seats` derives from cores for Claude subagent seats, and from free memory and cores for
seats that run as separate processes, unless config pins it; it counts builders and gate seats
together.

## Review tiers

At an item's first gate, `dispatch next` computes its review tier, `light`, `standard` or
`full`, from the diff size against `repos.gates.light_max_lines`, trust and never-auto
paths, the lead flags, the track, `repos.gates.floor` and an optional lead `tier`. A light
item gets the quality gate only; standard and full get arch, quality and security. A lead
tier below the computed one is refused and recorded as a reason, and the returned action
carries the `tier`.

Generated and data lines never count toward the tier or `repos.merge.max_changed_lines`, and
both read the same count. Generated means a lockfile, a `repos.merge.size_exclude` glob or a
`linguist-generated` glob in the repository's root `.gitattributes`, unless the diff changes
that file. Data means a `repos.gates.data_paths` glob, or a `.json`, `.jsonl`, `.csv` or
`.parquet` file over 200 changed lines or with a binary change. The reason names both totals:
`5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100`.
Every measured item that is not docs-only records its count, which `wuwei why` shows.

A docs-only diff gets one reviewer at any size and under the default floor. In such a diff
every path ends in `.md`, `.rst` or `.ipynb`, or in `.txt` under `docs/` or `specs/`, or is
a data file, and nothing else raises it. An analysis item gets the goal reviewer, never
security. A `.json` file counts as a document only under `repos.gates.data_paths`, since
it may be config. Agent instruction files never count as documents: `AGENTS.md`, `CLAUDE.md`,
`SKILL.md` and paths under `charters/`, `skills/`, `agents/`, `commands/`, `.claude/` or
`.agents/`. The reviewer is goal for a document and quality for a spec or a pre-registration.
The reason reads `docs-only: 1 reviewer (goal)`, and a FIX continues the same seat. A lead `tier` above light is overridden and recorded as
`lead tier full overridden: docs-only`. A lead flag, track FULL, a trust, never-auto,
FULL-pattern or binary path or `floor = "full"` keeps the three gates. A
repository that keeps code under `docs/` or `specs/` lists those paths in
`repos.gates.trust_paths`. The report lists the reviewer seats per item with its tier reason. See [configuration](configuration.md#workspace-and-repositories) and
the [lead plan JSON](reference.md#lead-plan-json).

The tier also decides how much process an item gets (design 5.3). Every brief and launch
prompt carries a `Depth:` line, so no seat decides it:

| | light | standard | full |
|---|---|---|---|
| Builder class sweep | none | the classes `wuwei sweep classes <worktree>` lists | every class |
| Gate step zero (mutation) | none | only when the diff touches guard code, outward, a hook or a trust path, or the lead flagged it trust_surface or boundary_relevant | always |
| After a fix | the same sentinel re-reads and rewrites `Verdict:` and `Head:` | delta round | delta round |
| Verdict | `Verdict:`, `Head:`, findings | full shape | full shape |
| Retro note | only when a line is not `none` | always | always |

The default `repos.gates.floor` is `standard`, so light depth needs `floor = "light"`.

With `gates.second_opinion = "<runtime>:<model>"`, standard and full items get one more gate:
the role in `gates.second_opinion_role` (quality by default) runs again on that runtime and
model, named `<role>@<runtime>`. Its verdict goes through the same lint and receive. A blocking
finding from either model blocks, a FIX from only the second opinion opens the same single fix
round, and the model that raised it does the delta. Each verdict records its cost and duration,
and the retro's `## Second opinion` section lists the findings each model raised alone, so you
can turn it off when it stops paying.

## Writing for you

`owner.verbosity` sets how much cards and the report say to you: `brief` (the default), `standard` or `full`, with one key per surface (see [configuration](configuration.md)). Seats rewrite text written for a person with the humanizer skill, version 3.1.0, MIT license, when it is installed, and otherwise follow the ten-line checklist under Writing for a person in `charters/_common-authoring.md`. The CLI counts the mechanical tells as the `ai_tells` metric in the retro and, at standard or full, the report. By default a tell warns and does not stop a send. An em dash or an emoji is always refused.

Outward text gets the same pass. Every tracker comment, docs page, DM, PR comment and review ping goes through the humanize lint before it is sent. By default a tell prints a warning and records an `outward.ai_tells` event, and sent text with tells counts in `ai_tells`. With `outward.humanize_strict` on, the text is refused with the tells it found and a hint to rewrite it. The DM status reply shows the count at full verbosity. `outward.humanize = false` turns the lint off, and `outward.humanize_kinds` picks the kinds it checks (see [configuration](configuration.md)).

## Owner decisions

What reaches you comes from `wuwei next`, one decision at a time, on the Owner step card of the
command that needs it: the morning gate, a merge the policy does not clear or one you keep, an
ESCALATE verdict (Yes opens a fix round, No parks the item), a parked item to resume (the round
cap, a build limit or a scanner chain parked it), and a scope change a reviewer asks on a PR. A
PARK verdict parks the item without asking you; the report and `why` show its reason.

Every seat prompt ends with the [mandate](#mandate) block and the commands `deploy.deny` names.
Assume and record: a two-way open question inside the item is not asked. The seat takes its
recommendation and records it under `Assumptions:` in the spec or PR body, and gates review it
as an `Assumption:` finding. A one-way, scope, goal or trust-boundary question is a sentinel's
ESCALATE or a builder's `Blocked:` line. The round cap (`gates.max_rounds`) is what stops the
rounds.

## DORA keys

`bin/wuwei dora` prints the four DORA keys over the last 28 days (`--window <days>` changes
that). Lead time to merge is the median cycle time of the items merged in the window, from
plan approval to merge. Lead time to deploy adds the hours from each merge to the first
deployment after it. Deployment frequency counts the code host's deployments, or its
published releases when a repository never deployed. Change failure rate is the share of
merged items that a later fix brief names. Time to restore waits for on-call incidents. A
key without evidence says `unmeasured` and why, never zero. The report and the retro show
the same table.

## Sessions

Several Claude Code sessions can share a workspace. Hooks register each one in day state
with its role, last hook and claimed items; a session idle past `sessions.stale_seconds` is
stale and its claims lapse. One session is the planner, a second takes over with
`plan session --take-over`, and `sessions.rotate_after` rotates the planner on a schedule.
See [sessions](reference.md#sessions) and [long sessions](daily.md#long-sessions).

## Heartbeat

On every tick the watch runs a fixed table of probes: a refused and an allowed hook call,
state, integrity, config, clocks, the status line, the planner and memory. Health shows on
the status line, a failed probe raises one page, a probe that turns from ok to failed is
behaviour drift, and a healthy heartbeat pings an external dead-man monitor. See the
[heartbeat reference](reference.md#heartbeat).


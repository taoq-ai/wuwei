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

The seat that watches the day for drift and loops, and compiles the retro at close.
It proposes rule changes; you promote the ones you want.

### CAP

How many build seats may run at once (`cap`, default 1; `bin/wuwei calibrate` proposes it from the host).
The morning gate asks you to confirm it each day, and the launch guard refuses a builder past it.

### Seats per goal

How the day's CAP splits across goals, for example `3 seats: G-1 2, G-2 1 (CAP 3)`.
The plan counts the first CAP items of the queue per goal; "Change something" at the morning gate changes it.

### Envelope

The day's working window: start time, end time and net build hours.
Work admitted during the day must fit the remaining build hours.

### Tier

Review tier: light (one reviewer agent) or standard and full (three), set per change from its size and risk. The tier also sets the process depth: see [review tiers](#review-tiers).
Outbound tier: a message sent as you either goes out at once or waits as a draft for your approval.

### Pace

How hard the day pushes: `careful`, `steady` (the default) or `fast`, picked on the morning gate card and changed with `wuwei plan set pace=<p>`.
Careful lifts light items to standard and keeps one seat free. Fast runs plain standard items at light depth with only the tests the diff changes, and CI is the gate. Guard code runs full at both. No pace moves a floor or changes who decides; `wuwei pace` shows the advice.

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

### Novel

A repository, channel, person, tool, dependency, environment or workflow the workspace has never touched.
A decision or send on it asks you once on a card, even when the mandate would take it; your answer clears it.

### Trust surface

Code where a mistake costs most: auth, credentials, input parsing, permissions, and the areas you add in the interview.
A change there gets three reviewer agents and is never merged without you.

### Host terminal

A terminal you type in yourself, outside Claude Code's agent tools.
Owner commands such as `bin/wuwei config set` refuse to run anywhere else.

### Humanizer

The writing checklist seats apply to text for a person, from the humanizer skill.
A lint checks outward text for its mechanical tells before it is drafted or sent.

### Spec engine

The tool each non-trivial item is specified with before it is built: spec-kit (default), superpowers or OpenSpec.
`[spec] engine` picks it; the hooks keep its steps in order in the item's worktree.

### Strict mode

`[spec] mode = "strict"` (default): source edits and the gates wait until the engine's steps are done.
`advisory` warns once per item and day instead; `off` checks nothing.

### Docs system

Where the team's documentation lives: Notion, Confluence, Markdown files in the repository, or none.
WUWEI writes an item's page there from its records, never from memory.

### Docs obligation

An item tiered standard or full must record what it did to the docs before its quality gate passes.
The value is a page, `new`, or `none` with a reason; the day close checks it again.

### Ticket

The tracker issue an item is built under: a Linear, Jira or GitHub id such as `ENG-12`.
With a tracker set, no item is built, reviewed or launched without one.

### Tracker hygiene

The rule that every item has a ticket, bugs found midway become linked tickets,
and the item's decisions, progress, verdicts, pull request and close land on its ticket.

### Fold

One comment that stands for the rest of a ticket's updates once its daily comment cap is reached.

### Adopted

An item made from work begun outside WUWEI: `pr claim` on an open PR with no item creates it,
and `worktree adopt` registers an existing worktree as its checkout.

### Lens

A one-line question every option of an engineering decision answers, such as SOLID or YAGNI.
You can add your own in `[decisions.lenses]` or drop a default.

## Roles

The shipped charters define planner, lead, builder, shepherd, steward, and four sentinels: goal, architecture, quality and security. Generated agent files in `agents/` carry the charters and tool allowlists. The planner owns the day, the lead shapes work, builders implement, sentinels check, the shepherd follows pull requests and the steward maintains procedure. `/wuwei plan` runs the day, starting with your morning gate; see the [daily path](daily.md).

## Guards

Claude Code hooks call the WUWEI CLI. Guards act when a tool is used and refuse relevant unsafe actions inside a WUWEI workspace or configured repository. Outside that scope they return clean. The three outcomes are 0 clean, 1 findings and 2 could not run. A relevant parse or measurement failure returns 2 with a reason. The CLI also records traces and events. See [security](security.md) for the trust boundary.

## Security posture

`security.posture` sets what warns and what blocks per area: `observe`, `guarded` (the default) or `strict`, with per-area overrides under `[security.areas]`. A `warn` level still runs the guard, records the refusal as a `guard.would_refuse` event and lets the call through. Every enforced refusal ends with a `posture:` line naming the area, its level and the key that changes it. See [security posture](security.md#security-posture) for the table.

`observe` is the old shadow mode (`guards.mode = "shadow"` still means it). Use it for the first week on a project, to see what the guards would stop in your own habits before they stop anything. Records never relax, in any posture: writes to state, events, config and generated instructions, verdicts and decisions (`records`), owner disposition markers, and canary or honeytoken egress. Relaxing those would corrupt the records the report is built from or let a seat act as you. Below `strict` an owner-only action asks you on a card instead: a deploy, release or publish, and a message that waits for your approval. The merge policy and approvals stay yours. The heartbeat probe session is never relaxed either.

`bin/wuwei shadow report` and the day report group the would-be refusals by guard, with counts and the three most frequent forms. A form refused more than three times with no later page is named as a candidate for a guard fix or a calibration proposal. The status line shows the posture when it is not `guarded`, each `observe` session starts with a line saying so, and after `guards.shadow_days` one nudge asks you to switch to `guarded` or extend. Under `guarded` or `strict` a warning is a nudge, one per guard per day.

MCP registry findings warn by default. A finding is a heuristic over tool descriptions, and a first measurement is new information, not drift. The publishing guarantee does not rest on the registry gate; it rests on the code host protections and the credential layout (design 9.1). So a false positive must not stop the day: under `guarded` the finding is filed as an owner decision and shown on the board with `bin/wuwei mcp decide D-<n> proceed`, and seats launch. Use `strict` for a repository where a changed tool must stop seats until you decide.

## Grants

An owner-only deploy, release or `deploy.deny` publish never runs from a session on its own. When a seat or the planner tries one, the deploy guard refuses it and writes a decision card, `Allow deploy on <org>/<name>?`, with the exact command, the target, the item and the seat. The planner asks you the card; your answer is the grant:

- `Keep owner-only`: nothing runs from the session; you run the command in a host terminal. Later tries today name the same card.
- `Allow once`: the next run of that action on that repository goes through, then the guard asks again.
- `Allow today`: every run of that action on that repository goes through until `wuwei close`.
- `Always allow`: a standing line in `[grants]` of `config.toml`, for later days too. Not offered under `strict`, where a line in config is ignored.

Only your recorded answer creates a grant: no seat, no config default and no hook does. Each run under a grant is a `grant.used` event, and the day report counts them per card. `bin/wuwei grants` lists your grants; `bin/wuwei grants revoke <n>` removes a standing one in a host terminal. When the plan already names a deploy, the morning gate asks it with the plan (`Allow today`, `Ask when it happens` or `Keep owner-only`), so the day runs without stopping for it.

A merge works the same way. When the merge policy does not clear a pull request, `bin/wuwei merge <pr>` (or `bin/wuwei pr act <pr>`) asks you on a card, `Allow merge on <org>/<name>?`, and a merge the plan lists is a planned card per repository or per pull request. The grant replaces only the auto-merge switch and its pacing (risk flags, never-auto paths, size, soak, daily cap, quiet hours, breaker). The gates must still pass at the current head. Required checks must be green, with approvals at that head and no changes requested. Threads and obligations must be clear, `merge_deploys = false` must hold, and the repository must allow squash merges. When one fails, the reason names it and says no grant lifts this. With no grant, `merge.default_tier` decides: `ask` writes the card, `owner_only` prints the exact `gh pr merge` command for a host terminal. A `gh pr merge` typed in a session is refused with the reason and `bin/wuwei merge <pr>`, which journals and watches the merge.

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

Some commands are yours alone: `wuwei decide`, `wuwei decision outcome`, `wuwei state recover`, `wuwei integrity reconfirm`, `wuwei mcp decide`, `wuwei drafts approve` and `drafts drop`, `wuwei grants revoke`, `wuwei goals edit` and `voice edit`. The rest are `wuwei watch uninstall`, `wuwei listen uninstall`, `wuwei remote ack`, `wuwei config promote`, `config set` and `config add-repo`, `wuwei memory forget`, `wuwei setup`, and `wuwei telemetry send`. Outside the strict posture, the planner records goals and voice you approved at the morning gate with `--file`. Agent tool hooks refuse them (`--help` or `-h` alone is allowed), so run them in a host terminal. Outside the strict posture the planner records some of your answers itself. A decision it asked you in the session goes in with `wuwei decide`. A config value you picked on a card goes in with `wuwei calibrate --answer` or `wuwei config set <key> <value> --from-card D-n` (no y/N prompt; your answer is the confirmation). A draft it asked you on a card goes in with `wuwei drafts approve` or `drafts drop`. It approves only after you answer Send now, or with `--file` the exact text you typed after Send with an edit. The ones that ask y/N exit 2 without a terminal. See [host terminal actions](reference.md#host-terminal-actions).

## Drafts and cards

A draft is an outward message the approval tier held back, stored with an id and the rule that held it, such as `ask by rule 9 (audience=company) for C9: unknown destination C9, not in outbound.work_channels, connector default class company`. Its card, `bin/wuwei drafts show <id> --widget`, asks you Send now, Send with an edit, Keep as draft or Drop, and names the command that records your answer. When a table row asked about one person or the destination channel, Always send to this person or Always ask for this channel takes the place of Drop. It sends this draft and adds the row with `bin/wuwei drafts approve <id> --always`. A draft from a configured adapter is sent by `wuwei drafts approve`. For a draft from a connector, approving records an allowance: the seat's same tool call, to the same place with the same text, passes once within `outward.draft_ttl` seconds (default 3600).

## Outbound tiers

Every outward message gets one of three tiers. `send` goes out after the lint. `ask` becomes a draft and its card, and you confirm or edit it. `block` is refused with the rule named, and there is no draft and no card.

Who reads the message decides the tier. Each destination and each addressed person gets an audience class:

- `owner`: you, by your identity in `outbound.owner`.
- `team`: a channel in `outbound.work_channels`, or a person WUWEI knows is internal.
- `company`: someone in the company WUWEI has not learned yet. A connector's unknown channels and people are `company` unless `outward.classes` says otherwise.
- `client`: a channel in `outbound.external_channels`, a channel the connector marks as shared with another organisation, or a person or org outside yours.
- `public`: anything you mark public in `outbound.channel_classes`.

WUWEI walks one ordered table for each of them, and the first matching row wins. Your rows in `outbound.tiers` come first, after a row for each connector mode in `outward.modes`. The defaults follow: you `send`; public `ask`; a client commitment or disagreement `ask`; anything else to a client `ask`. Then sensitive, commitment and disagreement text `ask`; company `ask`; a thread among team people `send` (`{ audience = "team", topic = "thread", tier = "send" }`); a monitoring write `send`. No default row blocks: an external party always gets a card you can send from, and you add a `block` row when a client needs one. The strictest reader decides the call. What no row narrows gets your umbrella, `outbound.default_tier`. With `send`, the shipped default, the broad commitment, disagreement and company rows drop out. A review reply, a thread answer or a message to a colleague just goes, and only client, public and sensitive text still ask. Narrow it with your own rows. With `ask` (`bin/wuwei config set outbound.default_tier ask`) the older kind rules say why a draft is held: direct messages draft, and a routine reply in a team channel sends. Docs and tracker writes keep `docs.auto` and `tracker.auto` either way.

A reply in a chat thread is read by the thread's participants, so each one is a reader. The hook cannot read a thread; the planner can. When a held reason says the participants are not learned, the planner reads the thread with the connector's replies tool and runs `bin/wuwei outbound learn --tool <tool> --thread <file>`, which records them for the day. A thread whose readers are all you or team sends by the thread row, a client participant follows the client rows, and an unknown one goes on the learn card. Until then a thread reply is one company reader: it asks under `ask` and goes under the shipped umbrella. Always send in this channel's threads on the draft card adds `{ channel = "C123", topic = "thread", tier = "send" }`.

For example, a seat writes "I will ship it tomorrow". To a client channel it is held on a card that names the client row; with `{ audience = "client", topic = "commitment", tier = "block" }` in your rows it is refused instead. The same line to a team channel goes out under the shipped umbrella and asks you on a card under `ask`. A status line to your own DM just goes. To let a reviewer's mentions go out, answer Always send to this person on a draft card that held one; it adds `{ person = "U123", tier = "send" }`. `bin/wuwei outbound tiers` prints the table with each row tagged `default` or `owner`, and `bin/wuwei outbound explain <draft id>` shows the rows a draft passed and the one that held it. Under `strict`, a `send` row never reaches a client or the public. The learn card proposes a class for each new channel and person. Each entry has one option that approves it with the other class: a channel as client or team, a person as company or team.

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, index and changelog. Day records live under `.wuwei/days/`. Settled facts belong in notes; procedure belongs in charters. The CLI provides `note`, `index`, `consolidate`, `payload` and `promote` commands. Goals and voice are yours: the lead proposes, the morning gate confirms and the planner records them, and you can edit them later; seats propose changes for promotion. The index is generated and notes are bounded by configuration defaults.

Memory has three tiers. A day keeps its raw records under `days/` for 30 days (`consolidation.archive_after_days`); then `wuwei consolidate` packs it into a tarball under `archive/<year>/`, which `wuwei memory show <date>` still reads. Week and month digests under `memory/digests/` stand for the archived days: decisions, lessons, metrics, incidents and items in one fixed shape, rebuilt from the records. A session loads the latest month and week digest, then the rules (spine, notes), then today, within `memory.budget_tokens`. Rules live only in charters and notes. Forgetting is proposed, never automatic: consolidate lists unreferenced notes, duplicates and superseded or contradicted charter rules, and nothing changes until you answer `wuwei memory forget F-n apply` in a host terminal; the before text stays under `memory/archive/`. `wuwei memory export --claude` writes the charter rules and the week's lessons into a marked block in `CLAUDE.md`, so the harness memory sees them; the records stay the one source and nothing reads the block back.

## Day flow

Plan, Build, Review, Close. `/wuwei plan` runs the morning gate, then the planner loops `build next` and `dispatch next` for each approved item, raises the PR and closes the day; phases move by themselves.

The day starts in parallel. WUWEI derives CAP from the host: cores, free memory and what one seat costs once seats have run. CAP is the running seats plus the seats that fit above the memory floor, one core per seat, within `host.seats`, and within `budget.tokens_per_day` when set. The plan shows it with the measurement, for example `cap 4 (host): 16 GB free, 1.5 GB per seat, 8 cores`, and the morning gate splits it into seats per goal. Each sweep derives it again as memory frees, and the status line shows `seats 3/4 (host)` or `(budget)`. A positive `cap` in config is your override. After you approve, `wuwei dispatch next --all` lists everything that can move now. Gate items come first, then building items, then planned items up to CAP with each goal's share first. The planner launches the whole set in one turn, an item's three gate seats together. With `cap = 1` the day runs one item at a time. The [daily path](daily.md) is your walkthrough and the [recovery](recovery.md) page covers the rest.

## Tickets and comments

With `adapters.tracker` set and `tracker.required` on, one rule decides whether an item may
run: it has a ticket, or its tier is in `tracker.skip_tiers`. `plan approve`, `plan add`,
`build next`, `dispatch next` and the seat launch all ask it and give the same reason. A
candidate's `ticket` field, an item discovered from the tracker backlog,
`bin/wuwei tracker create <item>` and `bin/wuwei plan set <item> ticket=<id>` record one.
Builders and sentinels open a linked bug with
`bin/wuwei tracker create --bug <item> "<title>" --evidence "<file:line>"` instead of widening
the item; the planner opens retro follow-ups with `--follow-up`. Each creation is written once
per day and writes one `tracker.created` event.

`bin/wuwei tracker log` turns today's events into comments on each ticket, once each:
decisions, progress (phases, seat starts and stops, fast checks), gate verdicts, the pull
request and the close outcome. The watch sweep and `wuwei close` run it. Kinds in
`tracker.auto` are sent; the rest wait as drafts. After `tracker.max_per_item_per_day`
comments the last one is a fold. `wuwei close` refuses while an item merged today has a
ticket that never reached done; `bin/wuwei tracker done <item>` moves it.

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
Outstanding review requests and unanswered threads require triage: fixes, outward-tier
replies, or owner decisions for disagreements and scope changes. Stale reviews require
requesting reviewers again and posting in the review channel. Approved PRs go through
`wuwei merge` or a merge decision. Closed, unmerged PRs require an owner decision.
Waiting within the review window and merged PRs have no action deadline.

The watch produces the same action deadlines while polling. Repeated observations do
not postpone an unresolved action. Overdue actions produce a nudge, then a page at twice
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
decision answered with `bin/wuwei decide D-<n> OPTION` counts as
resolved, and the command writes the chosen option into the record's `Outcome:`
line.
Pushed branch checks read remote-tracking refs in recorded item worktrees through
the VCS port, without fetching. A parked item still needs a raised or claimed PR
when its branch has been pushed.

## Builder steps

Claude Code builders run as subagents in the planner session. After writing a builder
brief with its worktree, call `wuwei build next <item>`. It returns one JSON action.
`launch` supplies the Agent prompt, and `continue` supplies the same agent's resume ID and
feedback. `check` supplies a command to run through Bash, and `park` supplies a reason and
numbered decision path. `done` means checks passed and the item moved to `gate`
(or to `delta` after a fix build). Call next again after executing
the action. Hooks register the seat and record its result; unchanged state returns the
same action, so execute each action once. Never poll a Claude seat through the CLI.

A check command records measurements itself. Exit 1 means failed checks and another next
call; exit 2 means unmeasured and requires resolving the reported error. The old blocking
Claude build form exits 2 and directs you to build next. Codex retains
`wuwei build <item> <brief> <worktree>` and executes the same action loop with polling.
`host.seats` derives from free memory and cores unless config pins it; it counts builders
and gate seats together.

## Review tiers

At an item's first gate, `dispatch next` computes its review tier, `light`, `standard` or
`full`, from the diff size against `repos.gates.light_max_lines`, trust and never-auto
paths, the lead flags, the track, `repos.gates.floor` and an optional lead `tier`. A light
item gets the quality gate only; standard and full get arch, quality and security. A lead
tier below the computed one is refused and recorded as a reason, and the returned action
carries the `tier`. See [configuration](configuration.md#workspace-and-repositories) and
the [lead plan JSON](reference.md#lead-plan-json).

The tier also decides how much process an item gets (design 5.3). Every brief and launch
prompt carries a `Depth:` line, so no seat decides it:

| | light | standard | full |
|---|---|---|---|
| Builder class sweep | none | the classes `wuwei sweep classes <worktree>` lists | every class |
| Gate step zero (mutation) | none | only when the diff touches guard code, grants, outward, a hook or a trust path | always |
| After a fix | the same sentinel re-reads and rewrites `Verdict:` and `Head:` | delta round | delta round |
| Verdict | `Verdict:`, `Head:`, findings | full shape | full shape |
| Retro note | only when a line is not `none` | always | always |

A Routine decision taken under mandate prints as one line in `decision show` at every tier.
The default `repos.gates.floor` is `standard`, so light depth needs `floor = "light"`.

With `gates.second_opinion = "<runtime>:<model>"`, standard and full items get one more gate:
the role in `gates.second_opinion_role` (quality by default) runs again on that runtime and
model, named `<role>@<runtime>`. Its verdict goes through the same lint and receive. A blocking
finding from either model blocks, a FIX from only the second opinion opens the same single fix
round, and the model that raised it does the delta. Each verdict records its cost and duration,
and the retro's `## Second opinion` section lists the findings each model raised alone, so you
can turn it off when it stops paying.

## Writing for you

`owner.verbosity` sets how much decisions, the digest, PR nudges, the DM and the report say to you: `brief` (the default), `standard` or `full`, with one key per surface (see [configuration](configuration.md)). Anything left out is one command away: `bin/wuwei decision show D-<n> --full` on the host or `more D-n` in the DM. Seats rewrite text written for a person with the humanizer skill, version 3.1.0, MIT license, when it is installed, and otherwise follow the ten-line checklist under Writing for a person in `charters/_common-authoring.md`. The CLI counts the mechanical tells as a `style` finding on drafts and decision records and as the `ai_tells` metric in the retro and, at standard or full, the report. By default a tell warns and does not stop a send. An em dash or an emoji is always refused.

Outward text gets the same pass. Every tracker comment, docs page, DM, PR comment and review ping goes through the humanize lint before it is drafted or sent. By default a tell prints a warning and records an `outward.ai_tells` event, and sent text with tells counts in `ai_tells`. With `outward.humanize_strict` on, the text is refused with the tells it found and a hint to rewrite it. Each draft lists its tells in `bin/wuwei drafts` and in the approval prompt, and the DM status reply shows the count at full verbosity. `outward.humanize = false` turns the lint off, and `outward.humanize_kinds` picks the kinds it checks (see [configuration](configuration.md)).

## Decision classes and cruise levels

A decision record gives every option a Title, a Rationale (why it scores as it does) and a
Consequence (what changes, what it costs, what it closes). The recommendation gets a
Reasoning line (what decided it and what would flip it). It also names a class. The
engineering classes `design`, `boundary`, `refactor` and `dependency-bump` add one
[lens](#lens) line per option: SOLID, twelve-factor, YAGNI and ponytail by default. Your
question card shows the titles, the recommended one first, each with its rationale,
consequence and lens lines, and ends the question with the reasoning. `wuwei decision
template` prints a valid record.

Cruise mode ([design spec 5.8.1](https://github.com/taoq-ai/wuwei/blob/main/docs/specs/2026-09-24-wuwei-design.md))
runs each class at a level from L0 to L3. Say `decision route` takes a record under the
mandate and its class runs at L2 or L3. If the record is two-way, inside its own branch, PR or
the workspace, its margin reaches `decisions.cruise.margin` and the daily budget allows,
it is a cruise answer: `Decided-by: cruise <class>@L<n>`. At L2 you get a nudge and can undo
it for `decisions.cruise.undo_minutes`; at L3 it is in the digest. Levels move only through
the CLI: down one level when the class's error budget is spent, back when its window
refills, up when you answer a raise card ([cruise answers](daily.md#cruise-answers)).

Error budget. One unlucky reversal no longer drops a class. Each class may spend
`decisions.cruise.budget_share` (10 percent) of its cruise answers over
`budget_window_days` (14) on undos, reversals, weekly samples answered differently and
escaped defects. The budget is spent with more events than that and at least two; the class
then runs one level lower until the window refills, and gets no raise card meanwhile. A
fast burn (`burn_warn`, the last 48 hours against the window's pace) sends a nudge naming
the events first. `bin/wuwei cruise budget` prints the table.

Calibration. A record's `Confidence:` is checked against what happened. Each taken record
with a stored confidence (high 0.9, medium 0.6, low 0.3) whose undo window closed scores 1
when it stood and 0 when it was undone, reversed, sampled differently or escaped a defect.
The Brier score per class and per role (the optional `Role:` field) over the error budget
window is uncalibrated above `calibration_threshold` once `calibration_min` records are
scored. An uncalibrated class runs at most L1, an uncalibrated role's records go to you as a
card, and a class gets a raise card only when it is calibrated. `bin/wuwei cruise
calibration` prints the table.

Shadow promotion. Before a raise card, a class runs in shadow at the next level. Each record
taken for it also notes what the next level would have answered, and nothing about the live
route changes. The steward checks those notes against your final answers. One miss ends the
shadow. After `shadow_days` with at least `shadow_min` checked answers, all agreeing, you get
the raise card. `bin/wuwei cruise shadow` prints the shadows, and the status line shows
`· shadow <classes>`.

Every seat prompt ends with a mandate block built from those class levels
(`decisions.cruise.levels`, the 5.8.1 defaults otherwise), the interview's trust-surface
line and `deploy.deny`. It says what the seat decides alone, what it decides and records, and what
comes to you. It closes with "Nothing else is a question." The levels only shape this
text and pick which taken records are cruise answers. Assume and record: a two-way
open question inside the item is not asked. The seat takes its recommendation and records
it under `Assumptions:` in the spec or PR body, and gates review it as an `Assumption:`
finding. A seat that stops on a question to you without a valid decision id is
flagged by the SubagentStop guard (and by the Codex and headless paths). Then `dispatch
next` refuses until the planner acknowledges the note.

A confirmation from someone outside the loop never holds reversible work: the seat routes
the record with `decision route D-n --external <item>` and continues. After
`decisions.wait_hours` weekday hours without your answer, the sweep confirms the
recommendation on a two-way door or parks the item on a one-way door, and records
`decision.waited`.

Negotiation loops: an item goes back and forth when records, verdicts, restarts and fix
requests go above `steward.loop_threshold` in `steward.loop_window_hours`, or on a second fix
round. Then the steward raises one `negotiation.loop` nudge per item per day, and a page when the
goal date has passed. The listener sends the summary to your DM. It reports; the
negotiation budget in the charters is what stops the rounds.

## Measured reversibility

A seat writes `Reversibility: two-way`, but the CLI decides whether that holds. A record is
two-way only when the CLI knows the undo for its kind of action and that undo ran once in
this workspace. The class gives the kind: code changes undo with a git revert, park, defer
and re-plan with `wuwei undo D-n`, and a merge with a revert PR when its repository does not
deploy on merge. A message never has an undo, and neither does `other`. Each undo is
rehearsed once on a scratch target (`wuwei undo rehearse commit`, `wuwei undo rehearse
decision`); `wuwei next` runs these for you after the morning gate. Until then, and for any
kind without an undo, the CLI rewrites the record to one-way, says why, and the record comes
to you as a card. Nothing is refused for it.

## DORA keys

`bin/wuwei dora` prints the four DORA keys over the last 28 days (`--window <days>` changes
that). Lead time to merge is the median cycle time of the items merged in the window, from
plan approval to merge. Lead time to deploy adds the hours from each merge to the first
deployment after it. Deployment frequency counts the code host's deployments, or its
published releases when a repository never deployed. Change failure rate is the share of
merged items that a later fix brief names. Time to restore waits for on-call incidents. A
key without evidence says `unmeasured` and why, never zero. The report, the retro and the
week digest show the same table.

## Sessions

Several Claude Code sessions can share a workspace. Hooks register each one in day state
with its role, last hook and claimed items; a session idle past `sessions.stale_seconds` is
stale and its claims lapse. One session is the planner, a second takes over with
`plan session --take-over`, and `sessions.rotate_after` rotates the planner on a schedule.
See [sessions](reference.md#sessions) and [long sessions](daily.md#long-sessions).

## Listener

`bin/wuwei listen` polls the inbound source, such as a Slack DM, into the workspace inbox.
The responder wakes the planner and handles commands only from the pinned owner, with a
second factor where a command needs one. While running it also probes raised and claimed
PRs with conditional requests, sends each `pr.changed` summary to the DM and,
unless `shepherd.autostart = false`, starts a headless shepherd seat that never merges. See
[remote operation](remote.md) and
[running the listener](configuration.md#running-the-listener).

## Heartbeat

On every tick the watch runs a fixed table of probes: a refused and an allowed hook call,
state, integrity, config, clocks, the status line, the planner and memory. Health shows on
the status line, a failed probe raises one page, a probe that turns from ok to failed is
behaviour drift, and a healthy heartbeat pings an external dead-man monitor. See the
[heartbeat reference](reference.md#heartbeat).

## Cockpit and board

`bin/wuwei dashboard` serves the read-only day board on loopback. The plugin's MCP server
runs `bin/wuwei board` and offers the `wuwei_board` tool inside Claude Code; it is declared
in the signed `plugin.json`, so integrity covers it. Answering a decision or approving a
draft stays a host terminal action. See the [daily path](daily.md#6-close).

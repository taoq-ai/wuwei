# Concepts

## Glossary

The words the rest of these pages use, two lines each.

### Seat

One agent session with one job and its charter: the lead, a builder, a gate reviewer, the shepherd or the steward.
`wuwei next` launches seats as the day needs them; each stops when its job is done.

### Gate

A review of a change by an agent that did not write it: architecture, quality or security.
The morning gate is different: your approval of the day's plan before anything starts.

### Sentinel

The four reviewing roles: goal, architecture, quality and security.
Architecture, quality and security run as the gates on each change; the goal sentinel checks work against its goal.

### Shepherd

The seat that takes a pull request from raised to merged: review replies and CI fixes.
It merges only through the merge policy and never approves a pull request.

### Steward

The seat that reviews the day at close and compiles the retro.
It proposes charter changes; `wuwei retro --promote` lands the supported ones.

### CAP

How many build seats may run at once (`cap`; `0` derives it from the host).
The morning gate shows it, and `wuwei next` launches no builder past it.

### Seats per goal

How the day's CAP splits across goals, for example `3 seats: G-1 2, G-2 1 (CAP 3)`.
The plan counts the first CAP items of the queue per goal; "Change something" at the morning gate changes it.

### Envelope

The day's working window: start time, end time and net build hours.
The lead proposes it and the morning gate shows it.

### Tier

The review tier of a change: light (one reviewer) or standard and full (three gates).
It is set from the diff at the first gate and also sets the process depth ([review tiers](#review-tiers)).

### Soak

The wait after the last push or approval before a merge (`merge.soak_minutes`).
A PR that turns a check failing on its base green skips it.

### Delta

The second review after a fix round: only the gates that asked for the fix look again.
After it the pull request is raised, another round runs, or the item comes to you.

### Park

Stop work on an item for now; the item records why.
A PARK verdict, the round cap or your No parks it, and only you resume it (`plan resume`, on its Owner step card).

### Carry

Move an unfinished item to tomorrow's plan; the item records it.
The next morning gate offers it again as carry-over.

### Unmeasured

A check that could not run or could not read its source.
WUWEI reports it and never counts it as clean.

### Mandate

The block at the end of every seat brief: decide alone what the brief, the charter and the standards answer.
Record two-way choices under `Assumptions:`; name a one-way, scope, goal or trust-boundary question in the result.

### Trust surface

Code where a mistake costs most: auth, credentials, input parsing, permissions and the boundaries in `[boundary]`.
A change there always gets three gates.

### Humanizer

The writing checklist seats apply to text for a person, from the humanizer skill.
The outward lint checks text for its mechanical tells before it is sent.

### Spec engine

The tool a non-trivial item is specified with before it is built: spec-kit (default), superpowers or OpenSpec.
`[spec] engine` picks it.

### Strict mode

`[spec] mode = "strict"` (default): the gates wait until the engine's steps are done.
`advisory` warns once per item and day instead; `off` checks nothing.

### Ticket

The tracker issue an item is built under: a Linear, Jira or GitHub id such as `ENG-12`.
An item needs none to start, build, pass its gates or raise its PR.

### Adopted

An item made from work begun outside WUWEI.
`pr claim` on an open PR creates it, and `worktree adopt` registers an existing worktree as its checkout.

## Roles

The charters define the planner, lead, builder, shepherd, steward and four sentinels. The planner session runs the day. The lead proposes it, builders implement and sentinels review. The shepherd follows pull requests and the steward reviews the day. Generated agent files in `agents/` carry the charters and tool allowlists.

## Day flow

`wuwei next` is the loop. It reads the plan file, the event log, each item worktree's HEAD, the verdict files, one cached PR listing and the seat ledger. From these it derives where the day stands. Nothing else holds the day's progress.

Each call returns every ready launch, every due duty and at most one owner decision. The planner runs every launch and duty, asks the decision on its card, and calls `wuwei next` again. When a seat stops, its completion notification brings the planner back. The [daily path](daily.md) walks one day through it.

The PR listing is one `gh pr list` per repository, cached in the day folder. It is read again after `pr.poll_seconds`, and after WUWEI raises, claims or merges a PR. A failed refresh keeps the last listing and says so.

Phases move by themselves: `planned`, `implement`, `gate`, `fix`, `delta`, `raised`, `merged`. CAP bounds the builders. With `cap = 1` the day runs one item at a time.

## Launches and gates

A seat launch must match a logged brief (`wuwei seat brief`) at an unchanged head. With `guards.enforce` on, the launch hook refuses one that does not.

Gates read the item's pinned head. A verdict counts only at the head it was written for, or at the head a recorded fix round produced from it. A rebase or a push that moves the PR head sends the gates back to read it. Every verdict write is linted: in the hooks, in `dispatch receive` and in `seat stop`.

For tiers above light under strict mode, the spec engine's steps come before the gates. `wuwei pr raise --item` opens the PR only after every gate passed at the head. A bare `gh pr create` for a recorded item is refused.

## Review tiers

At an item's first gate, `dispatch next` computes its tier: `light`, `standard` or `full`. It reads the diff size against `repos.gates.light_max_lines`, trust and never-auto paths, the lead flags, the track, `repos.gates.floor` and an optional lead `tier`. A light item gets the quality gate only; standard and full get arch, quality and security. A lead tier below the computed one is refused and recorded.

Generated and data lines never count toward the tier or `repos.merge.max_changed_lines`. Generated means a lockfile, a `repos.merge.size_exclude` glob or a `linguist-generated` path in `.gitattributes`. Data means a `repos.gates.data_paths` glob, or a large or binary `.json`, `.jsonl`, `.csv` or `.parquet` file. The reason names both totals, and `wuwei why` shows it.

A docs-only diff gets one reviewer at any size: goal for a document, quality for a spec. Agent instruction files never count as documents: `AGENTS.md`, `CLAUDE.md`, `SKILL.md` and paths under `charters/`, `skills/`, `agents/`, `commands/`, `.claude/` or `.agents/`. A lead flag, track FULL, a trust or never-auto path or `floor = "full"` keeps the three gates. See [configuration](configuration.md#workspace-and-repositories).

The tier also sets how much process an item gets. Every brief carries a `Depth:` line, so no seat decides it:

| | light | standard | full |
|---|---|---|---|
| Builder class sweep | none | the classes `wuwei build classes <worktree>` lists | every class |
| Gate step zero (mutation) | none | only on guard code, outward, a hook or a trust path, or a lead flag | always |
| After a fix | the same sentinel re-reads and rewrites `Verdict:` and `Head:` | delta round | delta round |
| Verdict | `Verdict:`, `Head:`, findings | full shape | full shape |

The default `repos.gates.floor` is `standard`, so light depth needs `floor = "light"`.

With `gates.second_opinion = "<runtime>:<model>"`, standard and full items get one more gate on that model. `gates.second_opinion_when` narrows it to items with one of the named flags, for example `["trust_surface"]`. A blocking finding from either model blocks. The retro's `## Second opinion` section lists what each model raised alone.

## Fix rounds

A FIX verdict opens a fix round. The builder continues with the verdict files as feedback, then the delta review runs. `gates.max_rounds` (default 2) caps the rounds per item; `gates.tier_max_rounds` overrides it per tier.

At the cap a blocker parks the item, and `wuwei next` offers `wuwei plan resume <item>` as the owner decision. Your Yes on its card grants one more round. Non-blocking notes at the cap ship in the PR body instead.

## Owner decisions

`wuwei next` names at most one decision at a time:

- the morning gate;
- a round cap spent, or a PR head moved at the cap;
- an ESCALATE verdict (Yes opens a fix round, No parks the item);
- a merge the policy does not clear, or one you keep with `owner_merge`;
- a PR closed unmerged on the code host.

A PARK verdict parks the item in code, without asking you. The report and `wuwei why` show its reason.

Every seat prompt ends with the [mandate](#mandate) block. A two-way open question inside the item is not asked: the seat records its choice under `Assumptions:` and the gates review it. A one-way, scope, goal or trust-boundary question is a sentinel's ESCALATE or a builder's `Blocked:` line.

## Owner step card

A command that needs your answer refuses and prints its Owner step card. The planner asks it in the session with AskUserQuestion. On Yes the same command runs again and passes. The only other card is the morning gate (`wuwei plan gate`).

Owner commands include `config set`, `config add-repo`, `config promote`, `plan resume`, a `merge` past the policy, a deploy and `doctor --fix`. No config line and no hook answers a card for you.

## Duties

A duty is an outward step the day owes. `wuwei next` lists each due one, the planner writes its content, and `wuwei duty <item> <duty> --evidence <link>` records it. `--skipped <why>` records one that cannot be done, and the report lists it under `## Skipped duties`.

Each duty is due while its channel is configured; `duties.on` turns one off:

- `ping`: post the review request once the PR is raised (`wuwei pr ping`);
- `shepherd`: answer new review threads on the PR;
- `tracker`: update the ticket or page once merged (`wuwei tracker move <item> done`);
- `summary`: post the day summary to your DM once the report is written.

`wuwei close` waits on every due duty. A duty left open on a day carried without close stays due the next day.

## Tickets and comments

A missing ticket never stops an item. A candidate's `ticket` field, `wuwei tracker create <item>` or `wuwei plan set <item> ticket=<id>` records one.

While `adapters.tracker` is not `none`, the ticket updates are duties. The ticket is created on approval, claimed at the first build, moved to review when the PR is raised and done when it merges. Each writes `duty.due` before the tracker call and `duty.done` after it. A call that fails after its retry is `duty.skipped`. The report lists it with its `wuwei tracker move <item> <duty>` retry.

Seats open a linked bug with `wuwei tracker create --bug <item> "<title>" --evidence "<file:line>" --seat <role>` instead of widening the item. `wuwei tracker log` writes progress, verdicts and carried or parked notes as comments, and `close` runs it. After `tracker.max_per_item_per_day` comments the last one folds the rest.

## Owner-only actions

The irreversible edges are refused by exact argv, never by a guess:

- a host merge, an approval, an admin merge or a branch protection change;
- a force push, or a push to the default branch;
- a deploy or release;
- an outward send outside `outward.allow`;
- a write to WUWEI's records.

A deploy refusal prints the Owner step card for that exact command; your Yes lets it run. A merge happens only through `wuwei merge <pr>`, which applies the merge policy. It needs gates passed at head, required checks green, approvals at head and clear threads. It waits out the soak and uses a merge method the repository allows (`repos.merge_method`). `merge.auto` off, `merge.owner_paths`, a diff over `max_changed_lines` or `owner_merge` leave the merge to you on its card. A `gh pr merge` in a session is refused and names `wuwei merge <pr>`.

## Guards

Claude Code hooks call the WUWEI CLI on PreToolUse, PostToolUse, SubagentStop and SessionStart. Guards act only inside a WUWEI workspace or a configured repository. They exit 0 clean, 1 with findings and 2 when they could not run. See [security](security.md) for the trust boundary.

## Security posture

There is one switch: `guards.enforce`. On (the default), the guards refuse. Off (`init --shadow`), they record what they would refuse and let the call through. The report's `## Shadow` section lists those. Records, merges, deploys and held sends refuse either way.

Plugin integrity is checked at SessionStart, as a warning that never refuses, and as a `doctor` row.

## Outward sends

A message to other people goes out through an MCP tool only when that exact tool is on `outward.allow`. Any other send is refused, naming the line to add: `wuwei config set outward.allow '["<tool>"]' --add`. That command asks its Owner step card.

A write whose every destination is yours is local: your DM, your own canvas or page, a mail only to you. It passes without `outward.allow`; see [your own surfaces](configuration.md#your-own-surfaces). Outward text goes through the humanize lint, and an em dash or an emoji is always refused.

## Records

The day lives in `.wuwei/days/<date>/`. The event log `events.jsonl` is the truth and `state.json` its cache. Beside them sit `traces.jsonl`, the briefs, the verdicts, `plan.md` and `report.md`. The CLI and the hooks write them; any other write is refused. `wuwei why <item>` explains an item or a refusal from these records.

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, an index, goals and a changelog. SessionStart shows the goals and memory to each session. Settled facts belong in the spine; procedure belongs in charters.

`memory/goals.md` is protected. A goals change goes through the plan. The lead writes goal blocks, `plan propose` shows them on the gate card and `plan approve --goals-confirmed` writes them.

`wuwei retro --promote` lands the retro's charter proposals. It also exports the rules block into `CLAUDE.md` and writes `memory/index.md`.

## Day close

`wuwei close` refuses while work is open. That is an approved item with no park or carry, a pending owner decision, a due duty, or a pushed branch without a PR. For each open item it asks one question: carry it to tomorrow (recommended), park it, or keep working. `close --widget` prints those questions and `close --why` prints one line per item; neither writes.

Once nothing is open, `close` runs the steward's close review and `tracker log`. `wuwei plan carry ITEM` and `wuwei plan park ITEM --reason TEXT` record a disposition. Carried items come back with tomorrow's `plan approve --import-yesterday`.

## Retro and report

After the close review, `wuwei next` returns `wuwei retro`, then `wuwei retro --promote`, then `wuwei retro` again to record what promote applied. The retro holds gate verdicts, cycle time, seat findings and charter proposals.

`wuwei report` then writes the day report. It lists merged, parked and carried items, cycle time per tier, review seats, skipped duties, DORA and unmeasured sources. A final `wuwei close` closes the day. `wuwei report --week` shows a week's telemetry aggregate.

## Telemetry

Every tool call is a span in the day's `traces.jsonl`; the metrics, the report and the retro read it. `wuwei telemetry preview` prints exactly what each sharing mode would send. `telemetry send` asks its card, and `telemetry off` stops sharing.

## DORA keys

`wuwei dora` prints the four DORA keys over the last 28 days; `--window <days>` changes that. Lead time to merge is the median time from plan approval to merge. Lead time to deploy adds the hours from each merge to the next deployment. Deployment frequency counts deployments, or published releases when a repository never deployed. Change failure rate is the share of merged items a later fix brief names. Time to restore waits for on-call incidents. A key without evidence says `unmeasured` and why, never zero.

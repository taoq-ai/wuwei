# Operator data reference

Use `bin/wuwei` from the installed checkout, or `python3 -P -m wuwei` with the package on `PYTHONPATH`. The `-P` option keeps a local `wuwei/` directory from shadowing the CLI.

## Commands

These are the commands `bin/wuwei --help` lists. `bin/wuwei <command> --help` shows the options. Two more are [plumbing](#plumbing) that Claude Code runs for you.

| Command | What it does | More |
| --- | --- | --- |
| `bin/wuwei init` | Creates or upgrades a workspace. | [init](#init) |
| `bin/wuwei config` | Checks, shows and changes workspace configuration. | [config](#config) |
| `bin/wuwei doctor` | Finds install, host, workspace, gate, day and guard problems and prints each fix. | [Doctor](#doctor) |
| `bin/wuwei why` | Explains from records why an item or a refusal is where it is. | [Why](#why) |
| `bin/wuwei next` | Prints where the day stands: every ready launch, every due duty and at most one owner decision. | [next](#next) |
| `bin/wuwei plan` | Proposes, gates and approves the morning plan, and records item dispositions. | [plan](#plan) |
| `bin/wuwei seat` | Writes seat briefs, records seat findings, and starts or stops a seat. | [seat](#seat) |
| `bin/wuwei build` | Selects the next builder action and records the builder's checks. | [build](#build) |
| `bin/wuwei dispatch` | Decides gate work and receives verdicts. | [dispatch](#dispatch) |
| `bin/wuwei worktree` | Creates or adopts an anchored item worktree. | [Item worktrees](#item-worktrees) |
| `bin/wuwei pr` | Raises, claims, pings and steps owned PRs. | [pr](#pr) |
| `bin/wuwei merge` | Checks or merges an eligible PR under the merge policy. | [merge](#merge) |
| `bin/wuwei duty` | Records an outward duty that `next` listed as done or skipped. | [duty](#duty) |
| `bin/wuwei tracker` | Opens tickets, logs comments and moves a ticket. | [tracker](#tracker) |
| `bin/wuwei close` | Closes the day once every item and duty has landed. | [close](#close) |
| `bin/wuwei report` | Prints the day report, or a week's telemetry aggregate. | [report](#report) |
| `bin/wuwei retro` | Compiles the steward retro, or lands its charter proposals. | [retro](#retro) |
| `bin/wuwei telemetry` | Previews, sends or stops the weekly usage counts. | [telemetry](#telemetry) |
| `bin/wuwei dora` | Prints the DORA four keys with their sources. | [dora](#dora) |
| `bin/wuwei agents` | Builds or checks the generated role agents. | [agents](#agents) |

Some steps need you. Such a command refuses and prints its Owner step card. The planner asks the card with AskUserQuestion, and on your Yes the same command runs again. These are `config promote`, `config set`, `config add-repo`, `doctor --fix`, `plan set <item> spec=skipped`, `plan set <item> owner_merge=false`, `plan set <item> governed_by=<path>`, `plan resume`, `merge` when the policy does not clear, `telemetry send` and an owner-only Bash edge.

## init

`bin/wuwei init [path]` creates a workspace. `--shadow` writes `guards.enforce = false`, so guards log what they would refuse. `--honeytoken-path` names the decoy credentials path under `.wuwei`.

`bin/wuwei init --upgrade` upgrades an existing workspace, and `--dry-run` shows the plan first. It removes every retired config key and every obsolete file or directory. It also removes generated copies of skills and agents the plugin no longer ships. It never follows a symlink and never touches `days/`, which is history. Each removal prints one `Upgraded ...: remove ... (no longer read)` line, or `Would upgrade ...` under `--dry-run`. A symlinked or outside path prints `left .wuwei/<path>: <reason>` and stays.

## config

| Subcommand | Effect |
| --- | --- |
| `check` | Validates `config.toml` and the adapters it selects. |
| `show <key>` | Prints the effective value, each row tagged default or owner. |
| `set <key> <value> [--add \| --replace]` | Sets one TOML value. `--add` extends a list or table. Asks its Owner step card. |
| `add-repo --name --path --branch [--identity]` | Adds one repository. Asks its Owner step card. |
| `promote [--measure]` | Applies the calibration proposal. `--measure` times each test runner once. Asks its Owner step card. |

## next

`bin/wuwei next` derives the day from the plan file, the event log, `git worktree list`, the verdict files, one cached `gh pr list` and the seat ledger. `state.json` is only a cache.

Before the morning gate it prints one row: state, action, the command or prompt, why and what comes then. After the gate, `--json` prints the set:

- `launches`: every ready launch, each with its command or prompt.
- `duties`: every due outward duty, with its prompt and its record command.
- `decision`: at most one owner decision, asked on its card.
- `rows`: one status row per open item, PRs last.

When nothing is ready it prints one day row: wait, close, retro, report or closed. The planner does every launch and duty, asks the decision, then runs `next` again.

## Owner decisions

`next` raises one decision at a time. The sources are:

- the morning gate (`plan gate`);
- a parked item whose round cap or build limit was spent (`plan resume <item>`);
- an ESCALATE verdict, or a head that moved at the round cap (`dispatch next <item>`);
- red checks at the round cap (`pr act <pr>`);
- a merge the policy does not clear, or an `owner_merge` item (`merge <pr>`);
- a PR closed unmerged (`plan park <item>`; No keeps the item as it is).

A PARK verdict parks the item with no card. `report` and `why` show the reason.

## plan

| Subcommand | Effect |
| --- | --- |
| `template` | Prints valid lead JSON for this workspace. |
| `propose <input>` | Records the lead's proposal (`-` reads stdin). It ranks the queue and records discovery. |
| `gate [--import-yesterday]` | Prints the morning gate card for AskUserQuestion. Writes nothing. |
| `approve --items ... [--goals-confirmed] [--import-yesterday] [--note TEXT]` | Approves the plan. The gate's Yes runs it. |
| `session <id> [--take-over]` | Registers the planner session. |
| `add <item> [--goal G] [--size N] [--title T] [--ticket ID] [--from-finding] [--note TEXT]` | Admits an item after the gate. `--from-finding` admits a seat's finding. |
| `carry <item> [--reason]` | Carries an open item to tomorrow. |
| `park <item> [--reason]` | Parks an open item. |
| `resume <item>` | Resumes a parked item on your Yes on its card. |
| `set <item> <key=value> [--reason]` | Records `spec=required\|skipped`, `ticket=<id>` or `owner_merge=true\|false`. `spec=skipped` needs `--reason`. |

### Goals

`memory/goals.md` is protected. A goals change goes through the plan. The lead writes the new goal blocks in the lead JSON: `id`, `outcome`, `measure`, `target`, `date` and `priority`. `plan propose` shows them on the gate card. `plan approve --goals-confirmed` writes and commits them. Goal ids alone keep the recorded goals.

## Lead plan JSON

`bin/wuwei plan template | bin/wuwei plan propose -` creates today's proposal from a valid skeleton. Replace the sample evidence before approval. The top-level keys are:

| Key | Content |
| --- | --- |
| `goals` | `G-n` ids from `memory/goals.md`, or goal blocks (see [Goals](#goals)). |
| `candidates` | Candidate objects, described below. |
| `seat_policy` | Role to `{ "runtime": "claude", "model": "sonnet" }`. |
| `envelope` | `start`, `end` and a nonnegative `net_build_hours`. |
| `sweep` | Source to a measured or unmeasured status string. |
| `cap` | A positive integer. `propose` derives the cap from the host; the lead's value is not used. |

Each candidate needs a unique `id`, a confirmed `goal` or `unplanned`, `evidence`, `scope`, `overlap`, `track`, `flags`, `score` and `evidence_lines`. `track` is `SLICE` for a small change with one pre-PR gate set, or `FULL` when a spec-done gate is needed. `flags` holds three booleans: `trust_surface`, `boundary_relevant` and `agent_surface`. `evidence_lines` cites one line for every score component.

Optional keys:

- `tier` (`light`, `standard` or `full`) raises the review tier `dispatch next` computes from the diff. A lower one is refused. A docs-only diff keeps one reviewer.
- `paths` lists repository-relative files, so the CLI can name the item's repository.
- `ticket` names an existing ticket such as `ENG-12` or `owner/repo#12`. Any other value refuses the proposal.
- `owner_actions` lists owner-only steps the gate pre-approves.

An empty `ticket` or `tier` counts as absent.

`plan propose` orders the queue by `prioritisation.framework`. Ties use goal priority, then candidate id. The lead's own order is never used.

### WSJF and RICE

For `wsjf`, `score` holds `value`, `time_criticality`, `risk_reduction` and `job_size`, each on the scale 1, 2, 3, 5, 8, 13, 20. WSJF is `(value + time_criticality + risk_reduction) / job_size`.

For `rice`, use `reach` (positive), `impact` (0.25, 0.5, 1, 2, 3), `confidence` (0.5, 0.8, 1) and `effort` (positive seat-days). RICE is `reach * impact * confidence / effort`.

## seat

| Subcommand | Effect |
| --- | --- |
| `brief ROLE ITEM NAME [--worktree P] [--pr REF] [--gate] [--track T] (--body TEXT \| --file PATH)` | Writes and logs a seat brief. `--file -` reads stdin. With neither body option it exits 2. |
| `note --fix "<title>" [--item I]` | Records a small fix a seat found. With `--item` the fix keeps that item's goal and repository. `next` proposes it; `plan add <id> --from-finding` admits it, and asks for `--goal` or `--repo` when the finding names none and the day has several. |
| `start --role ROLE --adhoc PROMPT` | Records an ad-hoc seat before its Agent launch. |
| `stop NAME (--verdict FILE \| --unmeasured REASON)` | Records a stuck seat's report, or stops it as unmeasured. |

### Seat briefs and the build loop

| Behaviour | Rule |
| --- | --- |
| One brief per name | A second brief with the same seat name is refused. |
| Gate role names | `arch`, `quality` and `security`, as `dispatch next` returns them, brief against the `sentinel-<role>` charter. A second opinion is `<role>@<runtime>`. |
| Gate body | A gate body must not ask for an inline verdict or restate the verdict path; the brief adds it. A `Paths:` line lists extra paths for the SLICE protected-path check. |
| Phases | The first `build next` moves `planned` to `implement`. Passing checks move `implement` to `gate` and `fix` to `delta`. `dispatch next` moves `gate` to `fix` when it returns `fix`. `pr raise` moves `gate` or `delta` to `raised`. An observed merge moves an item to `merged`. |
| Launch binding | A launch must match a logged brief at an unchanged head. With `guards.enforce` on, the hook refuses any other. |
| Scratch directory | Each brief names `<your scratchpad>/<item>/<role>/`, or `.wuwei/scratch/<item>/<role>/`. `seat brief` creates it empty. An observed merge removes the item's scratch. |
| Charter names | `lead`, `builder`, `shepherd`, `sentinel-arch`, `sentinel-quality`, `sentinel-security`, `sentinel-goal` and `steward`. |

### Stuck seats

A background seat ends with the harness's hand-back, and its SubagentStop carries no last message. The hook then reads the report from the seat's transcript. When it cannot, or when the result cannot be recorded, it stops the seat as `unmeasured` with a reason, keeps the report its transcript ends with in `reports/<name>.md`, a protected file whose sha256 the seat records, and names the recovery command. A seat never stays `running`. Malformed usage is recorded as unmeasured and never costs the result. A stop from an agent other than the bound one, or a late stop after a relaunch, leaves the seat as it is.

`seat stop <name> --verdict <file>` records the report through the same SubagentStop guards; with no file it records the kept report, or the hand-back the transcript ends with, and `next` offers that before `--unmeasured`. A sentinel's file must pass the verdict lint first. `seat stop <name> --unmeasured "<reason>"` stops the seat so the day can move; a running builder's build parks with that reason. `seat stop` runs from the planner session. `next` and the doctor `stuck seats` row name it.

An Agent launched with a type outside the WUWEI seats is an ad-hoc seat once the day's `state.json` exists. The launch guard registers it as `adhoc-<n>` with its type and the sha256 of its prompt. A SubagentStop that matches no seat records `subagent.untraced`, which the doctor counts. `why adhoc` lists today's ad-hoc seats. An ad-hoc seat has no report, so a stale one stops with `--unmeasured` only.

## build

| Operation | Effect |
| --- | --- |
| `next <item> [<brief> <worktree>]` | Prints the next builder action as JSON. Past the build it answers what `dispatch next` decides. Exits 1 on `escalate`. |
| `reconcile <item> [--worktree PATH] [--pr owner/repo#n] [--repo NAME --branch B] [--track FULL]` | Brings work done outside the record back in. It registers the worktree (uncommitted files included), or the repository's worktree on the branch, or claims the PR. Before the gates it writes a builder brief at HEAD and a build record that starts at the fast checks, without a builder seat, and runs them. Prints JSON with what exists (`head`, `start`, `changed`, `dirty`, `pr`), what was `verified` and what stays `unmeasured`, and the `next` command. A rerun with HEAD and the uncommitted files unchanged writes nothing; an interrupted one finishes. Only passing checks are listed as `verified`; failing ones are under `failed`. Exits 1 and changes nothing for an item outside the approved plan, a parked item, a running builder seat, a worktree, branch or PR of another repository than the item's, or another recorded worktree. `--track FULL` records the track a protected path needs. |
| `check <item>` | Runs and records the fast checks after the builder stops. A passing check satisfies the push guard. A build that leaves uncommitted changes, touches a credential file in any commit since the head it started from (even one deleted again), or makes no change over the head it started from, is not done: the builder gets the reason and runs again. A second build with no change parks the item; other repeats park it after `build.stuck_after` with the cause as the reason. |
| `analysis <item> [--file PATH]` | Saves the spec-kit analyze report as `analysis.md` in the item's one spec directory. The report comes on stdin or from `--file`. |
| `classes <worktree>` | Lists the sweep classes the item's diff touches. Read-only. |
| `<item> <brief> <worktree>` | Runs the Codex builder loop. WUWEI commits each completed job's changes with the repository identity. It never commits a credential file (the locations the trace check of `scanner` names: `.ssh`, `.netrc`, `.npmrc`, `.pypirc`, `.git-credentials`, `.gnupg`, `.aws/credentials`, `gh/hosts.yml`, `*.pem`, `*.key`, `.wuwei/env`, `.env` or `.env.*` other than `.example`, `.sample` and `.template`); that file, or a commit a hook rejects, goes back to the builder as the next iteration's feedback. |

Nothing reconcile registers counts as tested or approved: the fast checks run, uncommitted files keep the build from passing (a builder `continue` names them), and the gates follow. A builder launch needs a build record: the launch guard refuses one with none and names `build next <item>` and `build reconcile`. With `guards.enforce` off the seat registers and the refusal is logged. A new build past CAP waits: `build next` says so instead of recording it. Every passing check records the HEAD it passed on; a gate reads only that head. When the worktree has moved past it, `dispatch next` puts the build back to `build check`, and a gate brief or launch at another head is refused.

`build analysis` exits 2 and writes nothing for an unknown item, no worktree, no or two spec directories, no `spec.md`, a symlink or an empty report. A governed item's report also needs the `## Governing` table. `build classes` prints `Depth: light; no class sweep` at light depth and exits 2 when the diff cannot be read.

## dispatch

| Subcommand | Effect |
| --- | --- |
| `next [item] [--all]` | Computes the review tier and prints the gate launches. `--all` covers every open item. |
| `receive <item> <role> <name> [--round initial\|delta]` | Lints and records a gate verdict. |
| `opinion <item>` | Writes a second-opinion gate brief from the first-model brief. |
| `polish <item>` | Takes a polish round. |
| `skip-polish <item>` | Declines the polish round. |

Fix rounds are bounded. At the cap, `next` asks you instead of opening another round. Spec comes before gates for any tier above light.

## Item worktrees

After the morning gate, `bin/wuwei worktree add <item>` creates `worktrees/<item>` on a new branch named after the item in lower case. Pass `--repo <name>` when several repositories are configured. It first fetches the default branch from `brief.remote` (default `origin`) and starts at the fetched commit. When the fetch fails it exits 2 and creates nothing. A repository with no remote can set `brief.remote = "."`. It anchors the worktree, writes the configured identity and prints JSON with `branch`, `path` and `start`. The `worktree.created` event records the start commit.

`worktree add <item> --branch <name>` checks an existing branch out instead and records it (`worktree.adopted`). A branch that is only on `brief.remote` is fetched first and the checkout tracks it.

`worktree adopt <path> --item <item>` registers an existing clean worktree; `build reconcile` registers one as it is and brings its build in. It records the path and HEAD and prints `item`, `path` and `head`. It exits 1 and changes nothing for a path that is not a linked worktree of a configured repository. The same holds for uncommitted or untracked files, an item outside the approved plan, or an item that already has a worktree. `pr claim` runs it for a clean worktree on the PR branch. With none, `pr claim` runs `worktree add <item> --branch <PR branch>`. A PR whose head is on a fork gets no worktree: `pr claim` exits 1 and prints a read-only fetch of it.

Without gate approval both subcommands exit 1 and create nothing.

## pr

| Subcommand | Effect |
| --- | --- |
| `state [refs ...]` | Prints fresh state and dispatch data for owned PRs. |
| `raise REPO --base B --title T --body-file F --item I [--draft]` | Raises a prepared, pushed branch. |
| `claim <ref> [--item I] [--goal G]` | Claims an existing PR. With no item it creates one, `PR-<n>`, or `PR-<owner>_<repo>-<n>` with several repositories, in the PR's repository. |
| `ping <ref>` | Requests reviewers and posts when the gates clear. |
| `act <ref> [--run \| --complete \| --ready \| --reply TEXT \| --fix WHY \| --scope WHY \| --push] [--thread ID]` | Executes the next owned PR action. |
| `wait [--timeout SECONDS]` | Blocks until a raised or claimed PR changes in a way `next` acts on. |
| `disposition <ref> parked\|carried --comment TEXT` | Records a verified disposition on the PR. |

### Raising a PR

`pr raise` needs all four options, and the body file must be a regular file. The item must be in the approved plan, with a worktree recorded and no linked PR. The pre-PR gate runs on the worktree head first, and every gate must pass at that head. A finding exits 1 and raises nothing. A bare `gh pr create` for a recorded item is refused.

Reviewers are the top committers to the changed source paths, plus `shepherd.lead_login`. Ties within `shepherd.tie_commits` add a third. `shepherd.reviewers` replaces the ranking, and `shepherd.reviewers_exclude` removes logins. With nobody left, the PR is raised with `reviewers: none (solo)` and `pr ping` requests nothing.

`--draft` opens a draft. An `owner_merge` item opens as a draft without the flag. `pr act <ref> --ready` marks a draft ready. On a PR that is not a draft it prints `already ready for review` and exits 0.

On a claimed PR with a worktree, a conflict, red checks or a `--fix` the shepherd seat asks opens a fix round, and `wuwei next` returns its builder as a launch. For a conflict the builder merges the base; it never rebases the teammate's commits. The round runs the normal gates. Once every gate passes at the worktree head, `pr act <ref> --push` pushes the branch, leased on the PR head, and the item is raised again. Before that, `--push` exits 1. It also pushes nothing when the PR moved past what the worktree holds, so a teammate's newer commit is never overwritten: a fix round merges it and the gates run again. It refuses a head that changed after the gate check. A seat's own `git push` to a claimed PR's branch, or from its worktree, is refused. When the PR moved and no fix round is left, the item parks for the owner. `wuwei next` never merges, posts or marks a claimed PR ready; those stay a `pr act` run. A PR whose head branch is the default branch gets no worktree.

### Review threads

`pr act <ref>` on an owed review reply prints it as `{"action": "reply", "thread": ..., "question": ..., "owed": [...]}` and opens nothing; WUWEI never reads intent from the words. The shepherd seat answers each owed id with `--thread <id>` and one of `--reply TEXT` (posted first, through the outward lint), `--fix WHY` (a fix round with the thread and the reason as feedback) or `--scope WHY` (the Owner step card; Yes opens the fix round, No returns the defer reply). An open P1 bot thread is owed too; answer it with `--fix` (a reply is refused, since only the fix outdates it). A `--thread` that is no longer owed, or an empty reason, exits 2. Without `--thread` the first owed reply is answered. When no shepherd seat is offered or running, `next` lists the `shepherd` duty with `pr act` as its step.

### Waiting on PRs

`pr wait [--timeout SECONDS]` (default 3600) blocks until a raised or claimed PR changes in a way `next` acts on: a review thread or comment, a review, checks, mergeability, a moved head, a merge or a close. It prints one line per new step, `<item> <kind> <pr>: <why>` (for example `B shepherd acme/widget#2: ...`), and exits 1. At the timeout it prints nothing and exits 0; with no raised or claimed PR it exits 0 at once. A tick reads the PR listing only for repositories holding such a PR and only once their listing is `pr.poll_seconds` old: one GraphQL request per repository, whatever the PR count, and none while `next` read it recently. A rate-limit refusal holds the next read until its reset. `next` returns it, in the background, while only PRs wait on people.

## merge

`bin/wuwei merge check <pr>` prints whether the merge policy clears the PR and names the next step. `bin/wuwei merge <pr>` merges an eligible PR at its fresh head. The policy reads required checks, soak, `owner_merge`, owner paths (`never_auto_paths`) and the merge method from `[repos.merge]`. A merge the policy does not clear asks its Owner step card. Set `repos.merge_deploys` correctly; WUWEI never deploys.

## duty

`bin/wuwei duty <item> <duty> --evidence <link>` records an outward duty `next` listed as done. Duties are `ping`, `shepherd`, `tracker` and `summary`. Use `day` as the item for the day's summary. `--skipped <why>` records a duty that cannot be done; the day report lists it. A duty that is not due is refused. The `shepherd` duty takes no `--evidence`: a PR read (`pr act`, `pr state`, `close`) that finds no reply owed records it.

Outward duties follow the item phase: the ping after a PR is raised, shepherd replies, the tracker or Notion update, and the day-end summary. `close` waits on them.

## tracker

| Subcommand | Effect |
| --- | --- |
| `create <item>` | Opens the item's ticket from its record. |
| `create --bug\|--triage\|--follow-up <subject> "<title>" --evidence <file:line> [--seat ROLE]` | Opens a linked ticket and records the seat that filed it. |
| `log` | Writes today's progress, verdicts and carried or parked notes as ticket comments. |
| `move <item> claim\|in_review\|done` | Runs that tracker duty. |

## close

`bin/wuwei close` requests the day close. Once no item is open, it runs the close steward review, then checks every duty and the retro. It writes tracker comments and records `day.closed`. Until then it prints what holds the close.

- `--why` prints one line per approved item saying what holds the close.
- `--widget` prints each open item as a card: carry, park, or keep working.
- `--check retro` checks only the retro preconditions.

The steward review runs once a day. A second run prints `steward: close review already ran today`. While an item is in a fix round it prints `steward: waits for <items> to finish the fix round`.

## report

`bin/wuwei report` prints and saves today's report as `days/<date>/report.md`. It then polls merges and steps the telemetry week. `report --week [YYYY-Www]` prints a week's telemetry aggregate as JSON and computes it when absent.

## retro

`bin/wuwei retro` compiles the steward retro into `days/<date>/retro/<date>.md`. `retro --promote` lands today's charter proposals. When one lands, it exports the rules block into `memory.export_to` and writes `memory/index.md`. It exits 1 when a proposal was rejected.

Every seat ends with three retro lines: `Blocked:`, `Gap:` and `Change:`. Write `none` when a line has no finding. `[retro]` sets `charter_paths` (default `[".wuwei/charters"]`) and `changelog` (default `".wuwei/memory/CHANGELOG.md"`).

## telemetry

| Subcommand | Effect |
| --- | --- |
| `preview [week]` | Prints exactly what each sharing mode would send. |
| `send [week]` | Opens the attributed issue for a final week. Asks its Owner step card. |
| `off` | Sets `telemetry.share` to `"off"`. |

## dora

`bin/wuwei dora` prints the DORA keys over the last 28 days; `--window <days>` changes that. It shows lead time to merge and to deploy, deployment frequency, change failure rate and time to restore. Each key carries its source, or why it is unmeasured. It is read-only and exits 2 when the code host could not run.

## agents

`bin/wuwei agents build` regenerates the role agent files from the charters. `agents check` reports drift. The build renders the verdict format table into every sentinel agent and fails when a charter carries its own copy.

## Doctor

`bin/wuwei doctor` prints a row per check in seven sections:

- Install: plugin, integrity, `.in_use` markers, hooks, launcher, Python.
- Host: `gh`, git identity, ZIRAN, Codex, free memory.
- Workspace: config, template drift, each repository's path, branch, identity and `fast_checks`, calibration, and `guards.enforce`.
- Gates and adapters: `config check`.
- PR flow: `owner.handles`, `shepherd.lead_login`, `shepherd.authors` and the tracker, chat and review-bot adapters.
- Day and sessions: state, stuck seats, open pages, traces gaps, untraced subagents and the tracker.
- Guards: hook probes that must refuse a force push to `main`, allow a read, and refuse a write to the day's records. A `PreToolUse` call from outside any workspace must allow.

It works before there is a workspace; the Workspace section then names where to run `init`. When `.wuwei/executable` names another install, doctor runs from that install so every copy prints the same rows.

Each row is `ok`, `warn`, `fail`, `unmeasured` or `waiting` (a GitHub rate limit). Doctor never waits for a rate limit to reset: it names the empty bucket and its reset and moves on. A clean branch protection read is kept for the day in `.wuwei/days/<date>/protection.json`, so later doctor and `config check` runs that day skip it; a read with findings is made again. `wuwei why` reads the day's records only and makes no network call. Every row that is not ok prints `fix:` and `docs:`. Exit 1 when any row is warn or fail, else 2 when any is unmeasured or waiting, else 0. `--json` prints `{"exit", "rows"}`. `--section pr-flow` prints the PR flow rows from `config.toml` alone.

`bin/wuwei doctor --fix` applies only this allow list:

| Fix | Command | When |
| --- | --- | --- |
| `integrity-reconfirm` | `wuwei doctor --fix --apply integrity-reconfirm` | a development checkout asks for reconfirmation |
| `init-upgrade` | `wuwei init --upgrade` | template drift or a config that does not load |

It previews every fix and prints the batch's Owner step card. On your Yes the same command applies each fix bound to its preview. A preview that changed is refused, and the other fixes still run. Each applied fix appends a `doctor.fixed` event, then doctor diagnoses again. `--fix --widget` prints the card as JSON for AskUserQuestion. `--fix --apply <ids>` narrows the batch. `--widget` or `--apply` without `--fix`, or both together, exit 2.

Plugin integrity is measured at SessionStart. A mismatch is a warning and the doctor integrity row, never a refusal.

## Why

`bin/wuwei why <target>` reads the day records and writes nothing. The target is `last refusal`, an event id, `adhoc`, a PR ref `owner/repo#<n>`, or an item name. An event id is `<YYYY-MM-DD>:<line>`, the 1-based line of that day's `events.jsonl`.

For an item, `why` prints one line per step: queue entry (goal and score), gate tier, each verdict with its blocking findings, each phase change, the merge with its policy evidence, and what it waits on now. A step with no record prints `not recorded`. `--full` adds event ids and evidence paths. `--json` prints `{item, day, ticket, spec, steps}` for an item only.

For a refusal, `why` prints the guard, the rule, the normalised command and the fix. A `hook.refusal` event holds `refusals`, one `{guard, reason}` per guard, and a redacted `target`. With `guards.enforce = false` the hook records `guard.would_refuse` instead, explained the same way.

Exit 0 prints the view, 1 means no record, 2 means a record could not be read or there is no workspace.

## Gate verdict layout

A quality verdict with one finding that the lint accepts:

```text
# Quality verdict ITEM-1

Verdict: FIX
Head: 3f1c2ab9e0d4

- Q1 medium src/calc.py:19: the test accepts any ValueError, so a regression that raises one from a different cause would still pass. blocks: yes
Probe: mutation changed the guard message; the test still passed.

Simplicity: none, one guard and one division.
Design: none, a single pure function.

VAL: FINDING Q1
TEST: FINDING Q1
BUD: N.A. no external calls

Blocked: none
Gap: none
Change: none
```

The lint rules:

- Exactly one `Verdict: PASS|FIX|PARK|ESCALATE` line and one `Head: <7 to 40 hex>` row.
- A `Probe:` or `Mutation:` line; write `not run` when the seat could not run one.
- `Blocked:`, `Gap:` and `Change:` once each.
- Quality adds one `Simplicity:` and one `Design:` row.
- Arch, quality and security add class-sweep lines such as `VAL: PASS` or `AUTH: FINDING <id>`.
- A non-PASS verdict needs a finding. A PASS carries no `blocks: yes` finding. A FIX needs at least one `blocks: yes` finding.
- Each finding carries a severity (P0 to P3, critical, high, medium, low or info), a `file:line`, `blocks: yes|no` and a failure scenario.
- An item that fixes a CI job needs one `CI step <n>: PASS|FAIL|NOT RUN <evidence>` row per listed step. A PASS carries no `FAIL` row.
- Fenced blocks, quoted lines and HTML comments are ignored.

The forms live in one table in `cli/wuwei/verdict.py`. The lint runs on every verdict write: a Write or Edit of a `decisions/gate-*.md` file, a Bash call that writes one, and the seat's stop. `dispatch receive` and `seat stop` lint again. A Bash call that only reads a gate file is not linted.

## Item phase order

Phases move by themselves. These are the only legal moves. `parked` and `escalated` resume only to the recorded prior phase.

| Phase | Legal next phases |
| --- | --- |
| `planned` | spec, implement, raised, parked, escalated |
| `spec` | implement, parked, escalated |
| `implement` | gate, parked, escalated |
| `gate` | raised, fix, parked, escalated |
| `fix` | delta, merged, parked, escalated |
| `delta` | raised, fix, merged, parked, escalated |
| `raised` | fix, merged, parked, escalated |
| `parked` | planned, spec, implement, gate, raised, fix, delta |
| `escalated` | planned, spec, implement, gate, raised, fix, delta |
| `merged` | none |

## Outward sends and edges

An MCP write to other people goes out only through a tool on `outward.allow`. Any other is refused with the `config set outward.allow ... --add` line. A write to your own surfaces is local. See [Outward sends](configuration.md#outward-sends).

The irreversible edges are refused by exact argv: merge, approve, admin, force push, push to the default branch, deploy, an outward send outside `outward.allow`, and writes to WUWEI's records. An owner-only edge asks its Owner step card and runs on your Yes.

## Codex companion protocol

Configure `codex.command` as an argv list and `codex.timeout_seconds`. The adapter calls `task`, `status`, `result` and `cancel` with `--json` in the worktree. `task --fresh --background` returns a `jobId`; continuation uses `task --resume-last --background --write`. `status` must report a `workspaceRoot` that resolves to the requested worktree, or the job is cancelled. A brief line `Model: <model>` adds `--model`. Missing fields, an error body or a timeout is unmeasured and fails closed. Task starts run one at a time per host (`wuwei-start.lock` in `CODEX_HOME`, else `~/.codex`): a start holds the lock until its job reports a `threadId` or ends, at most 60 s, because concurrent app-server starts contend on the shared Codex state. A `failed` or `cancelled` job names the companion's `errorMessage` (or the failed turn's `summary`), frees its seat, and the same command relaunches it. Before a seat the owner stopped as unmeasured relaunches, its old job is cancelled when it still runs. The prompt asks for the `Blocked:`, `Gap:` and `Change:` lines the result check reads. Codex runs sandboxed to the worktree, so the prompt says to write nothing outside it: a gate seat's final message is its whole verdict, in plain lines in the verdict format the prompt carries, and WUWEI writes it to the verdict file; a builder leaves its changes uncommitted (the worktree's git metadata is in the main repository's `.git`), and WUWEI commits them as `chore(<item>): Codex builder changes`. `doctor` warns when `codex.command` is empty while Codex is wanted or the plugin is installed, and names the companion script it found.

## Files under .wuwei

| Path | Content |
| --- | --- |
| `config.toml` | Workspace configuration. |
| `executable` | The absolute launcher the session runs. |
| `charters/` | Role charters and their overrides. |
| `memory/goals.md` | Your goals. Protected; changed only through the plan. |
| `memory/index.md` | The memory index `retro --promote` writes. |
| `memory/CHANGELOG.md` | The charter changelog. |
| `days/<date>/events.jsonl` | The append-only event log; the source of the day. |
| `days/<date>/state.json` | A cache of the derived day. |
| `days/<date>/briefs/` | One brief per seat name. |
| `days/<date>/decisions/gate-*.md` | Gate verdict files. |
| `days/<date>/traces.jsonl` | Tool spans for telemetry. |
| `days/<date>/report.md` | The day report. |
| `days/<date>/retro/<date>.md` | The steward retro. |
| `generated/` | Generated copies, such as `config.cache.json`. Seats cannot write here. |
| `scratch/<item>/<role>/` | A seat's scratch when the host names no scratchpad. |

## Exit codes

Commands, guards and adapters share three exits. 0 is clean. 1 means findings or a refusal. 2 means the step could not run or could not be measured, and nothing was recorded.

## Hook latency budget

Every tool call waits for `bin/wuwei hook <event>`, so the hook path carries a budget (spec 10.6). The budget is 50 ms CPU p95 on M-series class hardware, and about 2x on 2-CPU CI runners. It applies to PreToolUse, PostToolUse and `status --line`. Inside a workspace, SubagentStop, SessionStart and the `git commit` and `git push` checks are held to 100 ms wall p95.

Every hook first pays for an interpreter start. `bin/wuwei` starts `python3 -I -P -S`, and hook processes skip the cyclic garbage collector and the interpreter teardown. Each hook imports only the guard modules its event and tool can run (`MODULES` in `cli/wuwei/guards/__init__.py`). The validated config is cached as `generated/config.cache.json`, so a hook never parses TOML while `config.toml` is unchanged.

The `latency` job in `.github/workflows/tests.yml` runs `python scripts/hook_latency.py`. It is a trend line, not a gate, and no test asserts a duration. Each probe prints its p95 next to the `python3 -I` startup floor on the same line. The job writes `latency.jsonl` and compares it with the last `main` run through `scripts/latency_report.py`, which warns on a probe over budget or short of margin. Run the script locally to see the same figures.

## Plumbing

Claude Code runs these two commands for you. You never do. `bin/wuwei --help` does not list them.

`bin/wuwei hook <event>` runs the guards for one Claude Code hook. The events are:

- `PreToolUse`: the edge guards, the launch binding, the outward send check and the records guard.
- `PostToolUse`: the verdict lint, owner card answers and the trace recorder.
- `SubagentStop`: records the seat's stop and lints its verdict.
- `SessionStart`: measures plugin integrity as a warning, and shows the orientation, goals and scoped session memory.

`bin/wuwei status --line [--width N]` prints the status line, 100 columns by default. It shows the gate state, items per phase, running seats against the cap, open pages, and `observe` when `guards.enforce` is false. On a read error it prints `WUWEI ? unmeasured` and exits 2. `status` has no other mode; `next` is the board.

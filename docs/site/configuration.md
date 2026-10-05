# Configuration

`bin/wuwei init .` creates `.wuwei/config.toml`. In a host terminal, change one value with `bin/wuwei config set <key> <value>` and add a repository with `bin/wuwei config add-repo` (see [calibration](#calibration)). `config set` writes strings, lists and tables in any layout, replaces a value that spans lines in place, and leaves every other line as it was; `wuwei config check` names a key set in two tables. Values below are the shipped template defaults. Omitted keys use CLI defaults. Unknown keys are a warning from `wuwei config check`, `wuwei doctor` and `wuwei init --upgrade`, with the line and the nearest documented key; under `security.posture = "strict"` they are errors, unless `template_version` is newer than the running plugin. The optional commented examples are inactive until uncommented. Paths in repository entries are relative to the workspace unless absolute.

## Sections

Every table `config.toml` accepts, and the heading below that documents its keys.

| Sections | Keys under |
| --- | --- |
| `[[repos]]`, `[repos.merge]`, `[repos.gates]`, `[repos.shepherd]`, `[prioritisation]`, `[discovery]`, `[tracker]`, `[tracker.states]`, `[owner]`, `[owner.verbosity]`, `[security]`, `[security.areas]`, `[guards]`, `[worktree]` | [Workspace and repositories](#workspace-and-repositories) |
| `[host]`, `[memory]`, `[retro]`, `[metrics]`, `[consolidation]`, `[build]`, `[codex]`, `[gates]`, `[pr]`, `[shepherd]`, `[shepherd.authors]`, `[watch]`, `[sessions]`, `[listen]`, `[responder]`, `[steward]` | [Host, build and memory](#host-build-and-memory) |
| `[adapters]`, `[scanner]`, `[scanner.mcp]`, `[calendar]`, `[brief]`, `[brief.style]`, `[chat]`, `[control_plane]` | [Adapters and brief](#adapters-and-brief) |
| `[voice]`, `[voice.sources]` | [Owner voice](#owner-voice) |
| `[boundary]`, `[environments]`, `[deploy]`, `[grants]` | [Boundaries and deployment](#boundaries-and-deployment) |
| `[outward]`, `[outward.max_length]`, `[outward.servers]`, `[outward.modes]`, `[outward.classes]`, `[outbound]`, `[outbound.people]`, `[outbound.channel_classes]` | [Outward text and outbound tiers](#outward-text-and-outbound-tiers) |
| `[decisions]`, `[decisions.cruise]`, `[decisions.cruise.levels]`, `[decisions.lenses]` | [Decisions](#decisions); cruise answering is not built |
| `[calibrate]` | [Calibration](#calibration) |
| `[spec]` | [Specification mode](#specification-mode) |
| `[telemetry]`, `[telemetry.otlp]` | [Telemetry](#telemetry) |
| `[docs]` | [Docs](#docs) |

## Workspace and repositories

| Key | Default | Meaning |
| --- | --- | --- |
| `cap` | `1` | Maximum running build seats. `bin/wuwei calibrate` proposes it from the host (cores, free memory, measured seat cost, within `host.seats`) and adds it when absent; a present value is listed to edit by hand. The morning gate approves the day's value with seats per goal, and the launch guard enforces that value. |
| `template_version` | `""` | Plugin version that last wrote this file. `wuwei init`, `wuwei setup` and `wuwei init --upgrade` raise it and never lower it. A plugin older than this value treats keys it does not know as unknown to it, records `config.newer_template` once per session, and `wuwei doctor` and the status line say to restart Claude Code. |
| `prioritisation.framework` | `"wsjf"` | Ranking formula: `wsjf` or `rice`. |
| `discovery.min_queue` | `2` | Discover again when a seat frees and the queue is below this count. |
| `discovery.autostart` | `"strict"` | Intraday start policy: `off` carries safe items to the next morning; `strict` admits confirmed-goal SLICE items above the approved queue cut; `goal` admits confirmed-goal SLICE items under CAP and budget. Unsafe or over-budget items come to you. |
| `tracker.backlog_filter` | `""` | Optional Linear team ID for backlog discovery. Empty reads accessible issues. |
| `tracker.states.in_review` | `"In Review"` | Linear workflow state name after a PR is raised. |
| `tracker.states.done` | `"Done"` | Linear workflow state name after a confirmed merge. |
| `tracker.required` | `true` | While `adapters.tracker` is not `none`, every approved item needs a ticket: `plan approve`, `plan add`, `build next`, `dispatch next` and the seat launch refuse without one and name `bin/wuwei tracker create <item>` or `bin/wuwei plan set <item> ticket=<id>`. |
| `tracker.skip_tiers` | `[]` | Gate tiers that need no ticket, for example `["light"]`. The recorded gate tier decides, else the lead's tier. |
| `tracker.strict_close` | `true` | `wuwei close` refuses while an item merged today has a ticket with no successful done transition (`bin/wuwei tracker done <item>`). `false` prints the line and closes. |
| `tracker.create` | `["bugs", "triage", "follow-ups"]` | Ticket classes seats may open besides items with `bin/wuwei tracker create --bug, --triage or --follow-up`. |
| `tracker.log` | `["decisions", "progress", "verdicts", "pr", "close"]` | Comment kinds `bin/wuwei tracker log` writes on each item's ticket. |
| `tracker.auto` | `["progress", "pr", "close"]` | Classes and kinds sent without a draft. Everything else waits in `wuwei drafts`; text naming a person or matching a sensitive pattern drafts whatever this says. |
| `tracker.max_per_item_per_day` | `10` | Comments per ticket per day; the last allowed one folds the rest into one comment. |
| `tracker.project` | `""` | Where new tickets go: a Linear team ID (empty uses `backlog_filter`), a Jira project key (required for Jira) or a GitHub `owner/repo` (empty uses the first repository). |
| `tracker.board` | `""` | GitHub Projects board as `owner/number`; transitions set its Status field. Empty uses a label for in review and closes the issue for done. A board or project outside `outbound.code_host_orgs` makes every tracker write a draft. |
| `profile` | `"strict"` | Guard profile: `strict` or `standard`. Standard warns for outward text lint. |
| `guards.mode` | `"enforce"` | Retired. `init --upgrade` and `doctor --fix` rewrite `"shadow"` to `security.posture = "observe"` (keeping `guards.shadow_since` and `guards.shadow_days`) and remove `"enforce"`. Until then `"shadow"` still means `observe`, and `config check` and `doctor` show `posture: observe (from guards.mode = "shadow", deprecated; run doctor --fix)`. |
| `guards.shadow_days` | `7` | Days in the `observe` posture before one status nudge asks you to switch to `guarded` or raise this number. |
| `guards.shadow_since` | `""` | Day `observe` started, as `YYYY-MM-DD`. `init --posture observe` and the interview set it. Empty means no nudge. |
| `security.required` | `true` | When true, a missing `.wuwei/security.json` makes guards fail closed instead of treating security as disabled. |
| `security.posture` | `"guarded"` | What warns and what blocks: `observe`, `guarded` or `strict`. `setup --shadow` and `init --shadow` set `observe` for `guards.shadow_days` days from `guards.shadow_since`, then one nudge asks you to switch to `guarded`. `config check` and `doctor` print the effective posture and the key it comes from. See [security posture](security.md#security-posture) for the table and its floors. |
| `security.areas.<area>` | `""` | Override one area of the posture with `off`, `warn` or `block`; empty takes the posture's level. Areas: `integrity`, `mcp`, `publish`, `records`, `outward`, `seats`; for example `security.areas.mcp` = `"off"` skips the MCP registry check. `records` below `block` is a config finding. |
| `worktree.git_hooks` | `"chain"` | How `worktree add` installs the git hooks. `chain` runs WUWEI's pre-commit and pre-push checks, then the repository's hook of the same name, when the repository has its own `core.hooksPath` or real hooks in `.git/hooks`: the scripts go in a generated directory under the worktree's git directory and the repository's setting is never changed. Without its own hooks the worktree uses `.wuwei/git-hooks`. `skip` installs none, warns and records `worktree.hooks_skipped`. `replace` uses `.wuwei/git-hooks` and the repository's hooks do not run in the worktree, for a repository you own outright. When chaining is impossible (a hooks path that is not a directory, no permission, `core.bare` or `core.worktree` set), `worktree add` still creates the worktree, warns and records `worktree.hooks_skipped`, and refuses under `security.posture = "strict"`. The Claude Code PreToolUse guard checks `git commit` and `git push` either way. `doctor` shows a `git hooks` row per repository; `init --upgrade` rewrites the scripts. |
| `repos` | `[]` | Configured repositories. Each `[[repos]]` entry has the fields below. |
| `repos.name` | Required per entry | Code host name, such as `owner/repo`. |
| `repos.path` | Required per entry | Repository path from workspace root or absolute path. |
| `repos.default_branch` | Required per entry | Protected base branch. |
| `repos.identity` | `{name = "", email = ""}` | Expected git identity for this repository; the commit guards compare commits against it. Set both values. `wuwei worktree add` writes it to each item worktree's Git config. |
| `repos.merge_deploys` | `true` when omitted | Whether a merge deploys. Template example sets `false` only after explicit confirmation. |
| `repos.merge.auto` | `false` | Allow automatic merge only when the merge policy's review, check, soak, path and budget rules pass. |
| `repos.gates.floor` | `"standard"` | Lowest review tier for this repository: `light`, `standard` or `full`. `wuwei dispatch next` computes a tier from the item diff at its first gate; LIGHT runs the quality gate only, STANDARD and FULL run arch, quality and security. Keep `standard` until the escaped defects per tier in the retro support lowering it. |
| `repos.gates.light_max_lines` | `100` | A diff with more changed lines is at least STANDARD. Binary changes, any lead flag and track FULL also raise the tier. |
| `repos.gates.trust_paths` | `["guards/*", "state.py", "adapters/*", ".claude-plugin/*", ".github/*", "ci/*", "workflows/*", "deploy/*", "infra/*"]` | Path globs, matched on any path suffix, that force at least STANDARD. `repos.merge.never_auto_paths` and `brief.full_path_patterns` force it too. |
| `repos.shepherd.reviewers` | `[]` | Code host logins requested for this repository's PRs; when set it replaces `shepherd.reviewers` here. |
| `repos.fast_checks` | `[]` | Commands for `wuwei fast-checks` on this checkout. |
| `owner.name` | `""` | Name used by outward text checks. |
| `owner.pronouns` | `""` | Owner pronouns for outward text checks. |
| `owner.handles` | `[]` | Bare chat IDs and code host handles. |
| `owner.timezone` | `""` | IANA time zone, for example `"Europe/Amsterdam"`, for the quality hour bands and `sessions.rotate_after.clock`. Empty uses this machine's zone. |
| `owner.verbosity.default` | `"brief"` | How much the CLI tells you: `brief`, `standard` or `full`. At `brief` a decision is its question, one line per option with its score, and the recommendation with one reason; the report leads with up to three outcome numbers that changed. `standard` adds the context, confidence, reversibility, blast radius, pre-mortem and revisit lines to a decision and keeps the earlier report. `full` adds every field and the record paths. Seat briefs keep `brief.style.length`. |
| `owner.verbosity.decisions` | `""` | Level for `bin/wuwei decision show`. Empty uses `owner.verbosity.default`. |
| `owner.verbosity.digest` | `""` | Level for the two-way decision digest; `full` adds each record path. Empty uses the default. |
| `owner.verbosity.nudges` | `""` | Level for PR change messages in your owner DM; `full` adds the changed fields. Empty uses the default. |
| `owner.verbosity.dm` | `""` | Level for decisions sent to your owner DM. Empty uses the default. |
| `owner.verbosity.report` | `""` | Level for `bin/wuwei report`. Empty uses the default. |

A minimal repository entry after initialization looks like this. Replace the example values with your own:

```toml
[[repos]]
name = "owner/repo"
path = "repos/project"
default_branch = "main"
identity = {name = "Builder", email = "builder@example.test"}
merge_deploys = false
fast_checks = ["python3 -m pytest -q"]
```

Do not keep a `repos = []` line once you add `[[repos]]` tables: TOML rejects the two
together. `bin/wuwei config check` names the line to delete, and `bin/wuwei init --upgrade`
removes it. While `config.toml` does not load, every tool call in the workspace is refused
with that error except `ToolSearch` and `Read`, `Grep` and `Glob` of `.wuwei/config.toml`
and `.wuwei/charters`, so the session can show you the line; the Stop hook prints the error
and lets the turn end.

## Specification mode

| Key | Default | Meaning |
| --- | --- | --- |
| `spec.engine` | `"speckit"` | The spec engine every non-trivial item is specified with before it is built: `speckit`, `superpowers`, `openspec`, or `none`, which checks nothing. |
| `spec.mode` | `"strict"` | `strict` refuses source edits in an item worktree while a step before implementation is missing, keeps the item from the gates until every step is done (a failing check named `spec` in the build loop; `wuwei dispatch next` refuses too) and refuses a builder stop whose last message does not name its artifacts. `advisory` lets each call through and records the first gap per item and day as one `spec.warned` event, listed in the report. `off` checks nothing. Under `security.posture = "observe"`, `strict` runs as `advisory`. |
| `spec.skip_tiers` | `["light"]` | Lead tiers (`light`, `standard`, `full`) whose items need no spec. The skip holds only while the diff agrees: at the move to the gates, a computed tier outside this list needs the spec after all. |

Steps per engine, each run by the builder with the engine's own command, read from the artifacts in the item's worktree (the item id lowercased):

- spec-kit (`specs/<item>` or `specs/*-<item>`): `specify` (`spec.md`), `clarify` (a `## Clarifications` section), `plan` (`plan.md`), `tasks` (`tasks.md`), `analyze` (`analysis.md` with no CRITICAL or HIGH finding row), `checklist` (every item checked in `checklists/*.md`), `implement` (every task checked).
- superpowers: `brainstorming` (`docs/superpowers/specs/<date>-<item>-design.md`), `writing-plans` (`docs/superpowers/plans/<date>-<item>.md`), `executing-plans` (every step in that plan checked), `verification-before-completion` (the fast checks and the gates).
- OpenSpec (`openspec/changes/<item>`, later `openspec/changes/archive/*-<item>`): `proposal` (`proposal.md`), `specs` (`specs/<capability>/spec.md`), `tasks` (`tasks.md`), `validate` (`validation.json` from `openspec validate <item> --strict --json`, every entry valid), `apply` (every task checked), `archive` (before the gates).

You skip or require the spec for one item in a host terminal: `bin/wuwei plan set <item> spec=skipped --reason <why>` or `bin/wuwei plan set <item> spec=required`. `wuwei doctor` fails a repository where the engine is absent and prints its install line:

- spec-kit: `uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude`
- superpowers: `/plugin marketplace add obra/superpowers-marketplace`, then `/plugin install superpowers@superpowers-marketplace`
- OpenSpec: `npm install -g @fission-ai/openspec`, then `openspec init`

`wuwei setup` offers the engine it finds first (`.specify/`, `openspec/`, or a `superpowers@` entry in `scanner.mcp.plugins_file`), spec-kit when it finds none.

## Host, build and memory

| Key | Default | Meaning |
| --- | --- | --- |
| `host.free_memory_mb` | `1024` | Nonnegative free memory floor in MiB. |
| `host.seats` | `4` | Total seat ceiling: default cap plus three parallel gates. Increase with custom cap; refusals name `host.seats`. It also bounds calibrate's `cap` proposal and each turn of `wuwei dispatch next --all`. |
| `host.reservation_timeout_seconds` | `14400` | Age at which a reservation is reported stale. |
| `memory.max_notes` | `60` | Index note limit. |
| `memory.note_line_cap` | `80` | Maximum lines in a note. |
| `memory.probation_days` | `10` | Working days before a note or rule can be archived for nonuse. |
| `memory.state_entry_cap` | `3` | State entries included in memory payload. |
| `memory.digest` | `"week"` | `"week"` writes the week digest at close and consolidate writes week and month digests; `"off"` writes none. |
| `memory.budget_tokens` | `6000` | SessionStart memory payload budget in estimated tokens; over it today's lines are left out first. |
| `memory.export_to` | `"CLAUDE.md"` | Workspace-relative file that receives the generated rules block and the generated guide block (`init`, `init --upgrade`); never under `.wuwei/`. |
| `retro.repo` | `"."` | Repository used for retro evidence. |
| `retro.charter_paths` | `[".wuwei/charters"]` | Paths to charter procedures reviewed during retro. |
| `retro.changelog` | `".wuwei/memory/CHANGELOG.md"` | Retro change log path. |
| `metrics.transcripts` | `"~/.claude/projects"` | Claude Code project transcript directory for attended time. Sessions are filtered to the workspace and its repositories. |
| `metrics.band_margin` | `0.2` | The retro names a worst hour or session-age band only when its gate FIX rate over the last 7 days exceeds every other measured band by at least this much. |
| `consolidation.archive_after_days` | `30` | Pack older day directories into `archive/<year>/<date>.tar.gz`; read them with `wuwei memory show <date>`. |
| `consolidation.similarity_threshold` | `0.85` | Text similarity ratio for near-duplicate review. |
| `build.max_iterations` | `8` | Maximum build iterations. |
| `build.stuck_after` | `3` | Repeated progress limit. |
| `build.poll_interval_seconds` | `5` | Runtime job poll interval. |
| `build.poll_timeout_seconds` | `3600` | Runtime job poll timeout. |
| `codex.command` | `[]` | Companion command; fill in to use Codex runtime. |
| `codex.timeout_seconds` | `300` | Codex command timeout. |
| `gates.second_opinion` | `"off"` | `"<runtime>:<model>"`, for example `"codex:gpt-6-astra"`, runs one gate of every STANDARD and FULL item a second time on that runtime and model. Its verdict is one more gate record named `<role>@<runtime>`; a blocking finding from either model blocks. `claude` and `none` are refused. |
| `gates.second_opinion_role` | `"quality"` | The gate role the second opinion repeats: `arch`, `quality` or `security`. |
| `pr.poll_seconds` | `120` | Interval between full reads of raised and claimed PRs. With the listener running, conditional probes every 30 s trigger a full read at once on a change. |
| `pr.action_minutes` | `30` | Positive minutes to act on a measured PR finding. Nudge after this deadline, page at twice the interval. |
| `pr.review_window` | `120` | Positive minutes to await review before re-requesting it. Starts at first observation of the head; comments do not reset it. |
| `shepherd.lead_login` | `""` | Lead code host login. Counts as a reviewer when different from the author. |
| `shepherd.reviewers` | `[]` | Code host logins to request instead of the history ranking and the lead. No `min_reviewers` check; the PR author is dropped. |
| `shepherd.reviewers_exclude` | `[]` | Code host logins never picked from history; the lead too when listed. |
| `shepherd.review_channel` | `""` | Chat channel ID for review requests. |
| `shepherd.review_gate_check` | `"Review Gate"` | Check excluded during review requests. |
| `shepherd.min_reviewers` | `1` | Minimum eligible reviewers required to raise or request review. `0` is a solo owner: `wuwei pr raise` and `gh pr create` need no reviewer, you merge, and the reviewer and channel-post obligations are not applicable. When the history finds nobody but the author, `wuwei pr raise` raises with `reviewers: none (solo)` on any value; it refuses only when it found some reviewers but fewer than this, and names `bin/wuwei config set shepherd.min_reviewers 0` and `shepherd.reviewers` as the ways out. Above `0`, `gh pr create` still needs a `--reviewer`: `shepherd.reviewers` takes effect only through `wuwei pr raise`. |
| `shepherd.author_windows_days` | `[90, 180]` | Authorship lookback windows, then all history. |
| `shepherd.tie_commits` | `2` | Include a third author within this many commits of second place. |
| `shepherd.source_exclude` | `specs/*`, lock files and generated files | Changed paths excluded from reviewer selection. |
| `shepherd.autostart` | `false` | Start one headless shepherd seat per mechanical PR action (conflicted, red CI, review comments, stale review) when the listener sees it. The seat never merges and every post it makes is a draft. |
| `shepherd.authors` | `{}` | Map author email to verified `{login, mention}` reviewer identity; `mention` is optional (default `""`) and a review ping refuses a reviewer without one. `bin/wuwei setup` maps your repositories' git emails to your code-host login and each bot author seen on the last 50 merged pull requests to its `[bot]` login. An unmapped email is resolved to the code host login for that email and cached for the day; one the code host cannot resolve is skipped with a `reviewer.unresolved` event, never a refusal. |
| `watch.clock_seconds` | `600` | Interval between watch clock events. |
| `watch.dead_seconds` | `1200` | Clock age after which the watch is reported dead. |
| `watch.stale_seconds` | `900` | Inactivity age at which running work is reported stale. |
| `watch.sweep_seconds` | `7200` | Interval between supervision sweeps. |
| `watch.ping_url` | `""` | https check URL of a hosted cron monitor; each healthy watch heartbeat pings it (see the heartbeat reference). Keep it private. |
| `sessions.stale_seconds` | `3600` | Seconds without hook activity after which a registered session is stale: it stops counting in `status --line`, its item claims lapse, and a stale planner is nudged. |
| `sessions.rotate_after` | `{ turns = 0, compactions = 0, clock = "" }` | Scheduled planner rotation, off by default. `turns` (Stop hooks since the session started today), `compactions` (compactions seen) or `clock` (`"HH:MM"` in `owner.timezone`): when one is reached, the Stop hook asks the planner once, at a turn with no running seat and no unanswered owner decision, to end the session and run `wuwei plan session "$WUWEI_SESSION_ID" --take-over` in a fresh one. |
| `listen.poll_seconds` | `60` | Interval between listener polls of the inbound source. The listener ticks at least every 30 s to probe owned PRs. |
| `listen.dead_seconds` | `300` | Clock age after which the listener is reported dead at session start and in `status --line`. |
| `responder.enabled` | `true` | Kill switch: when `false` the listener still stores events but does not wake the planner or handle commands. |
| `steward.every_tool_calls` | `50` | Completed tool calls between steward reviews. |
| `steward.loop_window_hours` | `4` | Window, in hours, over which a steward review counts an item's exchanges for a negotiation loop. |
| `steward.loop_threshold` | `9` | Exchanges in the window above which an item raises one `negotiation.loop` nudge a day; a second fix round today raises it too. |

## Decisions

| Key | Default | Meaning |
| --- | --- | --- |
| `decisions.wait_hours` | `24` | Weekday hours in `owner.timezone` an external confirmation (`decision route D-n --external <item>`) waits for your answer before the sweep confirms it on a two-way door or parks the item. |
| `decisions.cruise.enabled` | `true` | When false, every decision class is listed as going to you in the seat mandate (cruise answering is not built). |
| `decisions.cruise.levels` | `{}` | Per-class level (0 to 3) that lowers a 5.8.1 class default in the seat mandate; a level above the class ceiling or an unknown class is refused. |
| `decisions.lenses` | `{}` | Lenses every engineering decision (`design`, `boundary`, `refactor`, `dependency-bump`) answers per option, as name = one-line question. The defaults are SOLID, twelve-factor, YAGNI and ponytail; a new name adds a lens and `""` drops one, for example `YAGNI = ""`. Names use letters, digits, dash or underscore. |

These keys feed the mandate block in every seat prompt. Cruise mode itself, where the CLI answers some classes at levels L0 to L3, is designed in design spec 5.8.1 and not built: every routed decision still goes to you.

## Telemetry

Weekly usage counts that say whether WUWEI itself works: how often guards refuse or cannot run, how long a hook takes, how often items loop, how many decisions reach you. The watch sweep aggregates them at most once a day into `.wuwei/metrics/<week>.json`, never in a hook; `bin/wuwei metrics --week [<week>]` prints a week on demand. A finalised week can propose a config change, asked once at the next morning gate; nothing applies on its own.

| Key | Default | Meaning |
| --- | --- | --- |
| `telemetry.enabled` | `true` | `false` stops the aggregate, the proposals, sharing and the OpenTelemetry export. |
| `telemetry.share` | `""` | `"anonymous"`, `"attributed"` or `"off"`. Empty means the interview question is not answered yet and sends nothing; `bin/wuwei doctor` lists it as pending. A calibration profile never carries it. |
| `telemetry.endpoint` | `""` | Where anonymous mode posts; empty or not `https://` keeps every week local. |
| `telemetry.repository` | `"taoq-ai/wuwei"` | Where attributed mode opens issues with `bin/wuwei telemetry send`. |
| `telemetry.otlp.endpoint` | `""` | An `https://` OTLP/HTTP base URL on your own platform; off when empty. |
| `telemetry.otlp.headers_env` | `""` | The name of the `.wuwei/env` variable holding the auth headers as `key=value,key=value`; the value never enters config, events or output. |

OpenTelemetry: with `telemetry.otlp.endpoint` set, each sweep posts the records appended since the last export to `<endpoint>/v1/traces` and each newly finalised week to `<endpoint>/v1/metrics`, as OTLP/HTTP JSON with the stdlib. A day is a trace; each refusal, warning and seat run is a span with the attributes `wuwei.event`, `wuwei.guard`, `wuwei.outcome`, `wuwei.reason_code`, `wuwei.posture` and `wuwei.item`; decisions, loops, gate rounds and owner actions are span events; the weekly metrics are counters and gauges. It never carries command text, reasons or record bodies, and it never goes to the project. The mark advances only on a 2xx answer; a failure records `telemetry.unsent` and the next sweep resends.

## Adapters and brief

| Key | Default | Meaning |
| --- | --- | --- |
| `adapters.tracker` | `"none"` | Tracker implementation: none, linear, jira or github. |
| `adapters.chat` | `"none"` | Chat implementation: none or slack. With none, the channel-post obligation is not applicable. |
| `adapters.review_bot` | `"none"` | Review bot: none or greptile. |
| `adapters.runtime` | `"claude"` | Seat runtime: claude, codex or none. |
| `adapters.scanner` | `"none"` | Scanner: none or ziran. S4 requires the compatible JSON CLI described below. `none` turns the MCP registry gate off. |
| `scanner.severity_threshold` | `"high"` | Blocking threshold: critical, high, medium or low. Trust-boundary findings always block. |
| `adapters.code_host` | `"github"` | Code host: github or none. |
| `adapters.vcs` | `"git"` | Version control: git. |
| `adapters.host` | `"local"` | Host measurement: local or none. |
| `adapters.checks` | `"local"` | Fast check execution: local or none. |
| `adapters.tts` | `"say"` on macOS, `"none"` elsewhere | Speech output for owner packs. `none` writes a text pack with an explicit no-audio note. |
| `adapters.calendar` | `"none"` | Meeting source: none or a private ICS feed. |
| `adapters.transcripts` | `"none"` | Meeting transcript source. |
| `adapters.inbound` | `"none"` | Inbound message source: none or slack. |
| `adapters.redactor` | `"builtin"` | Redacts inbound text before it is stored: built-in patterns for phone numbers, email addresses and secrets. |
| `calendar.url` | `""` | Private HTTPS ICS URL. `WUWEI_CALENDAR_URL` overrides this setting. Keep the URL secret. |
| `brief.lead_minutes` | `30` | Meeting pack window before an event with attendees. |
| `brief.style.length` | `"standard"` | `standard` or `concise` pack text. |
| `brief.style.speed` | `180` | Speech rate in words per minute for `say`. |
| `brief.remote` | `"origin"` | Git remote used for a brief. |
| `brief.prior_branch_pattern` | `"*{item}*"` | Branch match, with lowercased item substituted. |
| `brief.full_path_patterns` | `[]` | Owner supplied regexes for paths needing full context. |
| `chat.identity` | `"connector"` | Optional CLI default: connector or custom_app. This key is not in the template. |
| `control_plane.content` | `"summary"` | What a messaging transport sends about a pending decision. `summary` sends the decision at the `owner.verbosity.dm` level (at `brief`: the id, the question, each option with its score and the reason for the recommendation; at `standard` or `full`: more of the record, up to all of it, including context, blast radius and evidence paths) and the whole record on a `more D-n` reply; `none` sends only the id and option letters, and a fixed line in place of an update. The question widget in the planner session always shows the summary. |
| `control_plane.owner` | `""` | The pinned sender of commands from your owner DM, as `<team id>/<user id>` (such as `T0123ABC/U0123ABC`). Empty handles no command; `wuwei config check` reports it when `adapters.inbound` is set. |

Run `bin/wuwei brief pack` once for a daily text pack, or `bin/wuwei brief pack --meeting`
inside the lead window for the next attendee meeting. The returned path contains the
five fixed sections, a what-changed visual, a three-bullet card and a three-question
drill. The sections come from the day's items, decision records and owned PRs, never
from adapter or guard messages. Answer with `bin/wuwei brief answer 1 "your answer"`; the command prints feedback
and records the score and streak. The existing `bin/wuwei brief ROLE ITEM NAME --body TEXT` command
continues to write seat briefs.

When the approved item's `flags.agent_surface` is true, `bin/wuwei dispatch receive`
runs the scanner for the security sentinel's reviewed worktree, including delta reviews.
Every finding becomes a verdict row and a `scanner.finding` event. Findings change PASS
to FIX; PARK and ESCALATE remain unchanged. Findings at or above the threshold block.
Findings also block when marked as a trust boundary, when the item's `trust_surface` or
`boundary_relevant` flag is set, or for ZIRAN checks SA001, SA002, SA003, SA007, SA008,
SA009 and SA010 (secrets, input validation, execution and data exposure).

The adapter requires **ZIRAN 0.39.0 or newer**, verified with `ziran --version`.
It runs `ziran audit PATH --format json --severity low` to retain every finding.
Exit 1 means findings are present; the configured blocking threshold is applied locally.
Stdout is one JSON document with `files_analyzed` greater than zero and a `findings` list.
Each finding contains
`rule`, `severity`, `file`, `line` and `message`; matched source lines are never included.
The gate evaluates these validated findings locally. No `ziran ci` command is used.
Each external command has a 60-second timeout. Missing or incompatible tools, command
errors, malformed reports and timeouts report unmeasured (exit 2).

At each watch sweep, nonempty daily traces are scanned with
`ziran analyze-traces --source otel --input DAY/traces.jsonl --out OUTPUT --format json`.
The adapter reads `OUTPUT/trace_analysis.json` from a temporary directory and discards it
after validation. Exit 0 means measured with no critical chain, 1 means critical chains,
and 2 means unmeasured; errors take precedence over findings. Missing or blank trace
files report `no sessions` in the sweep line without invoking ZIRAN, including when the
scanner adapter is `none`.

Critical chains page through `scanner.finding` events containing only chain, risk level
and session identity. Subagents use `session_id:agent_id` identities and their own
transcript brief references to bind to seat reservations. Transcript lookup is best-effort;
affected active items park and valid pending owner decisions appear in the existing queue.
Unknown sessions still page and queue a decision. Repeated sweeps
remeasure without duplicating a session/chain decision. Commands and argument values
never enter finding events or decisions. A session identity changed by secret redaction
uses a stable digest to keep different sessions distinct.

## Docs

The [docs system](concepts.md#docs-system) and the [docs obligation](concepts.md#docs-obligation) per review tier. With `system = "none"` nothing here applies.

| Key | Default | Meaning |
| --- | --- | --- |
| `docs.system` | `"none"` | Where documentation lives: `notion`, `confluence`, `markdown` or `none`. Notion needs `NOTION_TOKEN` and Confluence needs `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN` in `.wuwei/env`. |
| `docs.required_tiers` | `["standard", "full"]` | Review tiers whose items need a docs value before the quality gate passes and before the day closes. A light item records one `docs.exempt` event instead. |
| `docs.space` | `""` | The Notion or Confluence page new pages go under, as a link. `bin/wuwei doctor` reads it. |
| `docs.root` | `"docs"` | Under markdown, the directory in each repository that holds the pages. |
| `docs.publish` | `["report", "retro"]` | Daily pages `wuwei report` and `wuwei retro` publish once per day under notion or confluence. No effect under markdown. |
| `docs.auto` | `[]` | Page kinds (`page`, `report`, `retro`) written at once; any other kind is stored as a draft for `bin/wuwei drafts approve <id>`. Sensitive text drafts anyway. |
| `docs.strict_close` | `true` | `wuwei close` refuses while a merged item's docs obligation is unmet; `false` lists those lines in the report's `## Docs` section instead. |

## Owner voice

| Key | Default | Meaning |
| --- | --- | --- |
| `voice.review_prs` | `[]` | PR references whose owner comments teach the review audience voice. |
| `voice.sources.internal` | Not set | Example internal audience mapped to sent chat channel IDs. |

## Boundaries and deployment

| Key | Default | Meaning |
| --- | --- | --- |
| `boundary.api` | Not set | Example named boundary; `[boundary]` accepts names and descriptions. |
| `environments.production` | Not set | Example environment; `[environments]` accepts names and descriptions. |
| `deploy.workflows` | `[]` | Workflow names, filenames, paths or IDs treated as deploy actions. |
| `deploy.deny` | `[]` | Literal executable plus argument globs to refuse. |
| `grants.standing` | `[]` | Standing grants, one per line: `{action = "deploy", target = "repo:<org>/<name>", scope = "always", decision = "D-n", date = "YYYY-MM-DD"}`. `action` is `deploy`, `release` or `publish`; `target` may use `*` and `?`. Your `Always allow` answer on a refusal card writes the line; `bin/wuwei grants revoke <n>` removes one. Ignored under `strict`, where `doctor` warns about each line. |

The template also shows a `"release/*"` environment example. Add any actual environment register entries before using rules that depend on them. WUWEI does not deploy on its own: a deploy runs from a session only under a grant you gave (see [grants](concepts.md#grants)).

## Calibration

`bin/wuwei setup` runs the calibration and your interview: it adds a `[[repos]]` table for each repository it finds, calibrates them, and applies everything after one digest in a host terminal. The sections below describe what it proposes.

Two host terminal commands change one value later, each with a diff and a digest, the same path as `config promote`. The value is parse-checked before you are asked; an invalid one is refused with the reason and nothing is written:

- `bin/wuwei config set <dotted.key> <toml-value>`, for example `bin/wuwei config set owner.verbosity.default '"standard"'` or `bin/wuwei config set repos.0.merge_deploys false` (repositories by index), and a list of tables such as `bin/wuwei config set outward.tool_patterns '[{pattern = "mcp__custom__send", channel = "customer"}]'`. A value that is not TOML is refused with the type the key takes and an example. A table such as `owner.verbosity` is set one key at a time, and a deploy list only grows. On a list key the value is added to the effective list, so the built-in items stay (`config set outbound.work_channels '["C1"]'` keeps the others); on a named-entry table such as `outbound.people` or `outward.servers` it adds or replaces the given entries. `--replace` writes the value as given. `bin/wuwei config show <key>` prints the effective value, one row per item or entry, each tagged `default` or `owner`.
- `bin/wuwei config add-repo --name acme/widget --path widget --branch main --identity "Pat Example <pat@example.test>"` appends one `[[repos]]` table; a duplicate name or path is refused.

Run `bin/wuwei calibrate [--repo <name>]` after `init` and the basic `[[repos]]` entry (`name`, `path`, `default_branch`), and before the first plan. It reads each checkout and writes `.wuwei/days/<date>/calibration.md`; it never changes `config.toml`, and without `--measure` it runs nothing in the checkout. It exits 0 clean, 1 when it flagged text and 2 when it could not run or a read was unmeasured.

| Detector | Reads | Proposes |
| --- | --- | --- |
| Toolchain | `pyproject.toml`, `pytest.ini`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile` | `repos.fast_checks` from a fixed command table, never a command copied from the repository |
| CI checks | `.github/workflows/*.yml` run on `pull_request` | `repos.review_required_checks`: job names, one per leg of a single inline matrix, without `continue-on-error: true` jobs |
| Conventions | `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.specify/memory/constitution.md`, `CODEOWNERS`, PR and issue templates | charter blocks for the builder and the quality sentinel; `[boundary]` candidates from `CODEOWNERS` |
| Deploy signals | workflows run on a push to the default branch, tags or a release that use an environment, a deploy or release action, or a deploy command; deploy `Makefile` targets and `package.json` scripts; infrastructure directories | `deploy.workflows`, `[environments]`, `deploy.deny`, `repos.merge_deploys = true`, `repos.merge.never_auto_paths` |

It also reads the last 100 commit subjects for the commit style and the last 30 merged pull requests for a size and cycle time baseline, which the steward gets as advisory input.

The proposal is additive. A key absent from `config.toml` is added, and `deploy.workflows`, `deploy.deny` or `repos.fast_checks` still at a one-line `[]` is replaced. A key you already set is never changed: the report lists it under "config differs; edit by hand". Calibration never proposes `merge_deploys = false` or `merge.auto`.

Only fast commands go into `repos.fast_checks` and the charter blocks. `ruff check .`, `black --check .`, `npm run lint` and `make lint` are fast. A test runner (`python3 -m pytest -q`, `npm test`, `cargo test`, `go test ./...`, `make test`, `make check`) is CI only unless measured. `bin/wuwei calibrate --measure` runs each detected test runner once in the configured checkout through the checks port, the same runner as `wuwei fast-checks` (`/bin/sh -c <command>`, capped at 300 seconds), and may leave tool caches there. It is fast when it exits 0 within `calibrate.fast_check_seconds` (default 60). The `## CI only (not proposed as fast checks)` section of `calibration.md` lists the rest with the measurement or "unmeasured", and the calibrate output and the promote digest print the same lines. `bin/wuwei config promote --measure` measures again before it applies.

Repository text is data. A file with instruction-like text, such as a line telling an agent to ignore its instructions, contributes nothing; the report names its file, line and rule without quoting it. Job, environment and owner names outside a safe character set are reported as unsafe and dropped.

`bin/wuwei config promote` is a host terminal action. It recomputes the proposal, prints the diff and the calibration it will record, asks y/N, then writes `config.toml` and `.wuwei/calibration.json`. Agent tools are refused both. The charter blocks land through `bin/wuwei promote`.

On each sweep the steward compares the fast checks, CI check names and deploy signals with `.wuwei/calibration.json` and records one `calibration.drift` nudge per change per day. Run `bin/wuwei calibrate` and `bin/wuwei config promote` again to approve the new state.

## Owner interview

The interview asks a short, fixed set of questions about your own preferences. Each answer maps to a config key, a line in a charter override or a voice rule that already exists; nothing applies until you promote it. The questions live in one table, `cli/wuwei/interview.py`.

| Question | Maps to |
| --- | --- |
| `merge` (per repository) | `repos.merge.auto` and `repos.merge.soak_minutes`; auto merge still needs `merge_deploys = false` declared |
| `gates` (per repository) | `repos.gates.floor` |
| `quiet` (per repository) | `repos.merge.quiet_hours` |
| `interrupt`, `decisions`, `hours` | a line in `.wuwei/charters/planner.md`: when decisions interrupt you, how they are presented, your working hours and time zone |
| `phone` | `control_plane.content` |
| `avoid` | `- never:` phrases under `## shared` in `.wuwei/memory/voice.md`, which the outward lint enforces |
| `formality`, `signature` | a line in `.wuwei/charters/shepherd.md` |
| `risk` | a line in `.wuwei/charters/lead.md`: what else sets `trust_surface` |
| `manual` | `deploy.deny` patterns for commands you always run yourself |
| `verbosity` | `owner.verbosity.default` |
| `posture` | `security.posture`; `Observe` also sets `guards.shadow_since` to today |
| `telemetry` | `telemetry.share`: `Anonymous`, `Attributed` or `Off` |
| `tracker` | `adapters.tracker`: `Linear`, `Jira`, `GitHub` or `None` (then set its credentials in `.wuwei/env`); typing `jira PROJ` or `github owner/repo` also sets `tracker.project` |
| `tickets` | `Every item` sets `tracker.required = true`; `All but light items` sets `tracker.skip_tiers = ["light"]`; `Optional` sets `tracker.required = false` |
| `updates` | `tracker.auto`: progress, pull request and close by default; `Plus new issues` adds the four classes; `Everything` adds decisions and verdicts; `Nothing` drafts every tracker write |
| `chat` | `adapters.chat`: `None` or `Slack`; typing a channel ID such as `C0123ABCD` sets `slack` and `shepherd.review_channel` |
| `review_bot` | `adapters.review_bot`: `None` or `Greptile` (then set `GREPTILE_API_KEY` in `.wuwei/env`) |
| `reviewers` | `shepherd.min_reviewers`: `Owner only` sets `0`, `Code authors` sets `1`; typing a teammate's code-host login sets `shepherd.lead_login` to it and `min_reviewers = 1` |

Run `bin/wuwei calibrate --interview` in a host terminal to answer every question, or `bin/wuwei calibrate --interview merge` to answer one again; `--repo <name>` limits the per-repository questions to one repository. Without a terminal it exits 2. On the first day the plan skill runs `bin/wuwei calibrate --questions`, which prints only the questions no recorded `interview.json` answers (`[]` after setup) as `Morning gate` widgets, and records each answer with `bin/wuwei calibrate --answer <id>=<choice or text>`. Free text is checked against the calibration character set and the instruction-like scan.

Answers are recorded in `.wuwei/days/<date>/interview.json`, which only the CLI writes; answers not promoted that day are asked again. The charter and voice changes are written as proposals (`proposals/interview-<target>.json`): one `## Owner preferences (interview)` block per override, patched in place when you answer again. `bin/wuwei config promote` folds the config answers into the calibration proposal and lists them in the digest you confirm: an absent key is added, a present one is replaced in place in any layout, and a table answered with a single value is listed as "config differs; edit by hand". `deploy.deny` only grows. `bin/wuwei promote` lands the charter and voice proposals.

When you merge three or more pull requests the merge policy routed to you within seven days and `merge.auto` is false for that repository, the steward retro proposes `repos.merge.auto = true` under `## Owner preferences` with the decisions as evidence and the command to ask again: `bin/wuwei calibrate --interview merge --repo <name>`. It never records an answer for you.

## Calibration profiles

A profile carries a promoted calibration to another workspace of the same kind. `bin/wuwei calibrate export <name>` writes `<name>.json` in the current directory and refuses to replace one. It holds the config keys that differ from the shipped template (the `repos` part comes from the first repository, or from `--repo <name>`, and applies to every repository on import), the lines your charter overrides add to the shipped charters, and the ledger reasons that landed them. Anything personal stays out: owner, people, channel and repository identity keys, workspace paths, `guards` and `security` (the posture says where this workspace runs), plus any key, value, charter line or reason that names one of those values, holds an absolute path or trips the redactor. The `dropped` list names each one and why, never the value. If the redactor cannot run, the export exits 2.

`bin/wuwei calibrate import <source>` reads a starter name, an `https` URL (30 seconds, 1 MiB) or a file. It is a proposal like any calibration:

- A profile that sets `repos.merge.auto = true` or `shepherd.autostart = true`, raises a `decisions.cruise` level above the level the class runs at, turns `decisions.cruise.enabled` on (cruise answering is not built; the levels still bound the mandate), lowers `repos.gates.floor`, turns on `gates.second_opinion`, sets any `adapters` key, `calendar.url`, `watch.ping_url` or `codex.command`, or carries a personal key is refused: exit 1, each key named, nothing written.
- Instruction-like text in a config value, a charter line or a reason is flagged by line and rule and that key or role block is not proposed; the rest is (exit 1).
- `--skip <key>` (a dotted config key or `charters.<role>`) leaves a change out; `--repo <name>` limits the `repos` part to one repository.

Import prints the `config.toml` diff, writes the accepted part to `.wuwei/days/<date>/profile.json` (only the CLI writes it) and one `proposals/profile-<role>.json` per role, without lines the charter already has. `bin/wuwei config promote` re-checks `profile.json`, lists each change as `Profile <name>: <key> = <value>` in the digest you confirm, and lets an interview answer for the same key win. `bin/wuwei promote` lands the charter blocks. Lists replace yours, except `deploy.deny`, which only grows.

Two starters ship in `templates/profiles/`, derived from WUWEI's own setup: `python-library` (pytest fast check, packaging and CI on the trust surface, package publishing denied, short builder and quality rules) and `cli-tool` (the same, plus `bin/*` and rules on exit codes and reference docs). Try one with `bin/wuwei calibrate import python-library`.

## Outward text and outbound tiers

| Key | Default | Meaning |
| --- | --- | --- |
| `outward.patterns` | Built-in internal-state patterns | Regexes; setting a list replaces defaults, `[]` disables them. |
| `outward.banned_characters` | `emoji`, U+2014, U+2015, U+2E3A, U+2E3B | Setting a list replaces defaults. |
| `outward.tool_patterns` | Built-in Slack, Linear, GitHub, Notion and Atlassian MCP matches | Tool regex plus policy channel. The built-in rules match the brand anywhere in the name, so `mcp__<uuid>__slack_send_message` is Slack. A list in `config.toml` replaces the defaults; `config set` adds to them. A tool nothing resolves is a read, a write or unknown by the words of its name (see security). |
| `outward.servers` | `{}` | MCP server id to channel (`slack`, `tracker`, `code_host`, `docs`, `mail` or `other`), checked before the rules; `bin/wuwei outbound learn` proposes entries. Reads still pass. |
| `outward.modes` | `{}` | MCP server id to its write mode, the first rows of the [tier table](concepts.md#outbound-tiers): `send` (every write goes out after the lint), `draft` (`ask`, every write drafts) or `refuse` (`block`, refused with exit 1). Under `strict` a `send` mode still never reaches a client or public audience. Without one, the rest of the table decides. The learn card offers each mode. |
| `outward.classes` | `{}` | MCP server id to the audience class (`owner`, `team`, `company`, `client` or `public`) of a channel or person it has not learned. Without one, chat, Slack, mail and the code host are `company`; a tracker, docs or `other` write with no destination is `team`. |
| `outward.max_length.slack` | Not set | Example positive maximum for one channel under `[outward.max_length]`. |
| `outward.humanize` | `true` | Lint outward text for AI tells before it is drafted or sent; `false` turns the lint off. |
| `outward.humanize_kinds` | `["dm", "tracker", "docs", "pr", "review"]` | Kinds the lint checks: DMs, tracker comments, docs pages, PR comments and PR bodies, and other chat posts such as review pings. |
| `outward.humanize_strict` | `false` | `true` refuses a text with a tell; `false` warns and records `outward.ai_tells`. |
| `outward.draft_ttl` | `3600` | Seconds an approved draft's tool call may repeat, once; at least 60. |
| `outbound.tiers` | `[]` | Your tier rows, before the defaults; the first match wins. Each row has any of `tool` (regex on the tool name or the channel kind), `person` (id or `slack:<id>`), `channel` (id or class), `audience` (class) and `topic` (`sensitive`, `commitment` or `disagreement`), and the `tier`: `send`, `ask` or `block`. An unknown key or a bad `tool` regex refuses the whole file in every posture. `bin/wuwei outbound tiers` prints the effective table. |
| `outbound.work_channels` | `[]` | Team channel IDs (class `team`), eligible for routine auto-send. |
| `outbound.external_channels` | `[]` | Shared or client channels (class `client`); these override work channels. |
| `outbound.channel_classes` | `{}` | Channel ID to any audience class, over both lists, for example `C4 = "public"`. |
| `outbound.company_domains` | `[]` | Exact internal domain names. |
| `outbound.code_host_orgs` | `[]` | Internal code host organizations. |
| `outbound.people` | `{}` | Optional identity map using `slack:`, `github:` or `email:` keys, each with `email`, `org` and `class` (`owner`, `team`, `company`, `client` or `public`); `bin/wuwei outbound learn` proposes `slack:` entries for the day's reviewers with `class = "team"`. Without a `class`, an internal person is `team` and anyone else takes the connector's default class; `doctor` warns. |
| `outbound.learn` | `"card"` | How `bin/wuwei outbound learn` records an unknown connector, work channel or person: `card` asks you on one decision card, `auto` writes reviewers and listed channels at once under observe and guarded (strict still asks), `off` never learns and every such send stays a draft. |
| `outbound.default_tier` | `"send"` | The umbrella: what no tier row narrows gets this (`send`, `ask` or `block`) for chat, code host, mail and other writes; docs and tracker writes keep `docs.auto` and `tracker.auto`. With `send` the broad commitment, disagreement and company rows drop out of the defaults; narrow with `outbound.tiers` rows per tool, person, channel, audience or topic. |
| `outbound.owner` | all empty | Your own identity: `slack.user` (U or W id), `slack.dm` (your own DM channel, D id, never the WUWEI app DM), `mail` and `code_host` (login). Setup proposes `mail`, `code_host` and `slack.user` from what it measures; `bin/wuwei outbound learn --owner` proposes `slack.user` and `slack.dm` on its card. A message only you receive (your Slack DM or user id, or a mail whose only recipient is you) is never a draft; it still passes the outward lint and records an `outward.to_owner` event. |
| `outbound.owner_channel` | `"session"` | `session` or `dm`. With `dm` the planner also posts the digest, nudges and day report to `outbound.owner.slack.dm` (or `slack.user` when `dm` is empty). |
| `outbound.sensitive_keywords` | Built-in sensitive topic words | Optional replacement list; see the template for the full list. |
| `outbound.sensitive_patterns` | `['\\bmental\\s+health\\b']` | Optional replacement regex list. |
| `outbound.commitment_patterns` | Built-in commitment regexes | Optional replacement list; see the template for exact regexes. |
| `outbound.disagreement_patterns` | Built-in disagreement regexes | Optional replacement list; see the template for exact regexes. |

Unknown destinations and direct messages to anyone but you draft by default. A channel allowlist is a ceiling; it does not bypass outward text checks. The shipped [template](https://github.com/taoq-ai/wuwei/blob/main/templates/workspace/config.toml) contains the exact regex defaults and examples.

## Goals and discovery

While `memory/goals.md` has no goals, the lead proposes goal objects in its JSON, `wuwei plan propose` shows them as provisional and writes `days/<date>/goals.md`, and after you approve them in the morning gate the planner records that file with `wuwei goals edit --file`. Under the strict posture the hook refuses the planner's call and prints the command for a host terminal. Later you can run `bin/wuwei goals edit` to open `$EDITOR`, or `bin/wuwei goals edit --file goals.md` to use a prepared file. The command validates and commits the change in `.wuwei` history with `Promoted-by: wuwei` and `Edited-by: owner`, so SessionStart does not flag it as an unpromoted edit. Seats cannot use this owner action. Each `## G-n` block needs `outcome`, `measure`, `target`, `date` in ISO format, and a positive integer `priority`. Priority 1 wins score ties. `wuwei rank candidates.json` reads JSON candidates with a goal or `unplanned` mark, a `score` object, and one `evidence_lines` entry per score component. `wuwei discover` reports unavailable sources as `unmeasured`.

You use `bin/wuwei voice edit` or `bin/wuwei voice edit --file voice.md` for the same validated history flow. Seat proposals still go through `wuwei promote`.

After the morning gate, sweeps and qualifying seat-free events save new discovery candidates. A builder seat stop only records the seat-free request; the watch runs that discovery on its next tick and records a failure once as `discovery.unmeasured`. Run `bin/wuwei plan add <item>` to apply the same admission gate to one saved candidate. A started item enters the existing `build next` path when a builder brief and worktree are logged; otherwise a build request remains visible for the planner. Owner proposals appear in the steward decision batch. The morning plan shows safe `off` mode candidates carried from the prior day.


### MCP registry checks (S3)

`wuwei init` and `wuwei init --upgrade` discover attached MCP configurations and
register them through `scanner.mcp`. Set `adapters.scanner = "ziran"` to use ZIRAN
0.39.0 or newer. `none`, the default, turns the registry gate off: every MCP
command and the launch gate exit 0, the first check of the day with attached servers
prints `mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)`, and doctor shows
the gate ok and WUWEI's own servers as covered by plugin integrity. Nothing checks
attached servers for tool drift or poisoning then. A configured scanner that is
missing or the wrong version is a check that could not run (exit 2) and blocks
launches under `guarded` and `strict`. No attached servers is a clean empty registry.
WUWEI declares its own read-only board server in the signed
`.claude-plugin/plugin.json`; the integrity check covers it, so the registry does
not scan it and `bin/wuwei mcp check` reports it as covered by plugin integrity.
A `.mcp.json` added to the install, one in a workspace or repo, and any other
plugin's servers, including one named like the cockpit, are discovered and
checked like any other. Coverage goes by install directory, so another plugin
whose plugin.json links to WUWEI's is still checked.

`scanner.mcp.project_file` defaults to `.mcp.json` in the workspace and each
configured repo. `scanner.mcp.plugins_file` defaults to
`~/.claude/plugins/installed_plugins.json`; registry v2 user installations and
project/local installations matching those repos contribute their `.mcp.json`
and the `mcpServers` object of their `.claude-plugin/plugin.json`.
`${CLAUDE_PLUGIN_ROOT}` in plugin.json servers is expanded to the install path.
`scanner.mcp.user_file` defaults to `~/.claude.json` with top-level `mcpServers`.
Relative overrides resolve against the workspace. Missing default user/plugin
files and absent project/plugin MCP files are optional; explicit user/plugin
file overrides must exist. Invalid or unreadable input is exit 2.

Only servers Claude Code would attach are scanned. User-scope and plugin servers
always attach. A project server (from a workspace or repo `project_file`) attaches
when, for the repo path or one of that repo's git worktrees under
`<workspace>/worktrees/`, it is not in `disabledMcpjsonServers` and is in
`enabledMcpjsonServers` or `enableAllProjectMcpServers` is true. Those keys are read
from `projects[<path>]` in `scanner.mcp.user_file`, `.claude/settings.json` next to
that file (`~/.claude/settings.json` by default), and the path's
`.claude/settings.json` and `.claude/settings.local.json`. An unapproved server is
reported as `<name>: not attached (unapproved)` and never started. Invalid approval
state is exit 2. Local-scope servers (`projects[<path>].mcpServers`) are not read.

Each attached server is measured on its own: the check writes a one-server config
under `.wuwei/ziran/servers` (owner-only, since it copies env and headers) and calls
the scanner once per server, with `scanner.mcp.timeout_seconds` (default 60) per call.
A server that cannot be measured, for example an OAuth remote server, is named in the
reason and does not hide the others' findings. A stdio server launched by `uvx`,
`npx` or `pipx run` without an exact package version (`pkg@1.2.3`, `pkg==1.2.3`) is
reported as `<name>: unpinned launcher` and never started; `@latest` and ranges are
unpinned.

The scanner keeps a snapshot per server under `.wuwei/ziran/snapshots` and untrusted
raw reports under `.wuwei/ziran/<server>/<digest>.json`, one file per server per
distinct result (the digest is taken over the report's canonical JSON). A repeat check
with the same result writes nothing and the `mcp.checked` event records the server as
`unchanged` (`new` for a new result, `unmeasured` when the run failed); a failed run
leaves no file. Servers named `servers`, `snapshots` or `snapshot-backup` collide with
this storage and stay unmeasured. `wuwei doctor` warns about `report-*` directories left
by v0.12.0, and `wuwei doctor --fix` removes the empty and clean ones and moves each
readable one into this layout, leaving any that a pending decision still lists. A server whose
measurement fails keeps its prior snapshot, and a check that could not run restores
all of them, so retries cannot silently accept drift. After upgrading from v0.11.0
the first check registers a fresh baseline per server, so drift between the last
v0.11.0 check and the upgrade is not reported. Events contain server name, drift
type, severity and tool name only.

Run `bin/wuwei mcp check` before the first morning seat. The plan skill does this
before the lead, and `bin/wuwei plan propose` checks again. The check exits 2 while
any server is unmeasured, else 1 while findings await an owner decision, else 0.
High/critical findings open an owner decision. Medium/low findings remain visible.

`scanner.mcp.block` is unset by default; the security posture decides: `observe` and
`guarded` block no finding, `strict` blocks `["critical", "high", "unmeasured"]`. Set
it to refuse agent and runtime launches and `plan propose` on top of that default: a
pending finding with a listed severity (exit 1), or any unmeasured server when the list
holds `"unmeasured"` (exit 2). Everything else is a nudge. Under `observe` the list has
no effect. The full v0.11.0 behaviour is `["high", "critical", "unmeasured"]`. A check
that could not run (invalid input, an interrupted check, a stale or missing record)
refuses with exit 2 under `guarded` and `strict`. A workspace created before #351
carries `block = ["critical"]` from the old template; `bin/wuwei config check` names it,
and deleting the line takes the posture default.

For a server that stays unmeasured, you may run
`bin/wuwei mcp decide proceed-unmeasured <server>...` from the host terminal and answer
y. It records an owner decision bound to each server's definition;
later checks report the server as proceeding unmeasured by owner decision until its
definition changes. Briefs list today's unmeasured servers in an `MCP unmeasured:`
header line.

A new result with a queued severity opens one decision; a recheck that finds the
same reports queues nothing more. Its `Context:` is a table with one row per finding
(Server, Tool, Flag, Severity, Snippet, Since) and one row per unmeasured server,
followed by `Reports:` with each report path. The snippet is redacted, limited to
plain characters and cut to 60. Since reads `first measurement`, or
`changed since <day>` when the server has an accepted baseline.

To answer it, run `bin/wuwei decide D-<n> proceed` (or `defer`), or
`bin/wuwei mcp decide D-<n> proceed`, from a host terminal and answer y. Under
`observe` and `guarded` the planner asks it in the session and records the answer with
the same command. The command writes `Outcome:`, `Decided-by: owner` and a
`Notes: Decided at <time> at the host terminal.` (or `in the planner session.`) line
into the record. From outside the workspace, set `WUWEI_WORKSPACE=<path>` or pass
`bin/wuwei --workspace <path> mcp decide ...`. On `proceed`
it stores the accepted `[server, digest]` reports as the baseline in an
`accepted-*.json` record and re-runs the check, so those findings do not queue again
while the report stays the same. `defer` keeps the gate as it is, and a later
`proceed` still works. Agent tools cannot invoke this owner command (its `--help` is
allowed). A decision file or forged event alone never clears a flag. Confirmation
cannot excuse exit 2. Pending findings and report references survive rechecks
and day rollover. The host terminal follows the local friction boundary in
threat model 9.1; remote authenticated decisions remain M5 work.

## Running the watch

Run `bin/wuwei watch install` inside an initialized workspace to install and start a
user service. On macOS this creates a launchd agent; on Linux it creates a systemd
user unit. The service uses the active workspace and current `PATH`. Run
`bin/wuwei watch uninstall` to stop and remove it. `bin/wuwei watch --once` runs
one due cycle without installing a service. The watch writes clock events at
`watch.clock_seconds` intervals, and the next sweep reports a dead watch when it
has no fresh clock line (see below). Each loop iteration also runs the heartbeat probes
and can ping an external monitor; see [Heartbeat](reference.md#heartbeat).

`bin/wuwei watch install --dry-run` prints the unit path, the rendered unit and the
service commands without writing or loading anything. If loading the service
fails, install removes the unit it wrote, so a retry after the fix works.
`bin/wuwei watch uninstall` always exits 0: it prints a failed stop command as a
warning and still removes the unit. A job that stays loaded after such a warning
keeps running until you stop it by hand. Uninstall is an owner action: the Bash
guard refuses `watch uninstall` from agent tools inside a workspace, so a seat
cannot turn a dead-watch page into `watch off`; run it from your own terminal.

`bin/wuwei status --line`, `bin/wuwei nudges`, the cockpit, session start and
sweeps all read watch health the same way, whatever the last sweep recorded:

- Installed with `watch install`, and no clock line today or today's latest
  clock older than `watch.dead_seconds`: `watch dead`, one `watch: health` page.
  This catches a watch that died overnight. It clears at the next clock line, or
  after `watch uninstall` when no clock line was written today.
- Not installed, and no clock line today: `watch off`, neither a page nor a
  nudge.
- Not installed, and today's clock went stale (a watch run by hand died):
  `watch dead`, one page.

`watch unmeasured` means watch health cannot be read; it is one nudge.

Run `bin/wuwei nudges` to list current nudges and pages, one line per cause with the
command to run next; identical causes are merged with a count. `bin/wuwei nudges --json`
lists every entry with its source, and its entry count matches the page and nudge counts
in `bin/wuwei status --line`.
Routine progress such as plan approval, build starts and checks, and a call to any
adapter set to `none` is silent. A nudge clears when its cause clears: a draft nudge when
the draft is sent or dropped, a merge policy nudge when the PR merges or closes.

## Running the listener

`bin/wuwei listen` polls the inbound source named by `adapters.inbound` every
`listen.poll_seconds` and appends new events, redacted, to `.wuwei/inbox/inbox.jsonl`.
Events are deduplicated by source and id, and the cursor per source is kept in
`.wuwei/inbox/cursor.json`, so a restart loses nothing and stores nothing twice. When
new events arrive the listener sets the planner wake, shown at session start as
`inbox to line N`; with `responder.enabled = false` it stores events and wakes nobody.

`bin/wuwei listen install [--dry-run]` and `bin/wuwei listen uninstall` work like the
watch's: one launchd agent or systemd user unit per workspace, labelled
`wuwei-listen-<hash>`. `bin/wuwei listen --once` runs one poll: exit 0 when it polled,
with or without new events, and exit 2 when it could not run, with the reason printed. With
`adapters.inbound = "none"`, `listen`, `listen --once` and `listen install` exit 2.
Uninstall is an owner action, refused from agent tools inside a workspace.

With `adapters.inbound = "slack"` the listener reads every message in
`SLACK_OWNER_DM_CHANNEL`, and messages in `outbound.work_channels` and
`outbound.external_channels` that mention a Slack user id from `owner.handles` (such as
`U0123ABC`). It reads top-level messages only, so answer in the DM as a new message, not
in a thread. Bot and app posts are skipped. The sender of each message is recorded as
`<team id>/<user id>`. Each poll re-reads five minutes behind the
previous successful poll, and the first poll starts five minutes back. A Slack rate limit fails that poll
and the next poll retries. The reading token needs the `channels:history`,
`groups:history` and `im:history` scopes and membership of the polled channels.

### Commands from your owner DM

Each new message in `SLACK_OWNER_DM_CHANNEL` is handled once, in order, by the
listener: `plan`, `status`, `report`, `ask <question>`, `stop <session>` (a unique prefix
of at least eight characters) and `stop all`. Decision replies use the control-plane
forms: `approve D-n`, `option X on D-n` or `drop it`. `run <routine>` and
`cloud <repo> <task>` answer "Not available in this version." with the command list, and
anything else gets the command list. Messages in other channels are never commands.

Only the sender pinned in `control_plane.owner` (`<team id>/<user id>`) can command.
With no pin, every message fails and the listener log names the pin and the sender.
A message from any other user is ignored: nothing is answered, and a `remote.ignored`
event records the sender once a day. A message from the pinned user id with a different or
missing team id is refused: the DM answers that the sender does not match the pinned
identity, and a `remote.refused` event pages on the host. Editing the pin in config.toml
on the host is the re-confirmation. `stop all` is still accepted from a changed identity.

`plan` and `ask` need a second factor. Put a base32 TOTP secret in `.wuwei/env` as
`WUWEI_TOTP_SECRET` (30 second codes, six digits, HMAC-SHA1, as authenticator apps use)
and end the message with the current code, such as `plan today 123456`. The code must
reach the listener within 2 minutes of the message and each code works once. Without a
valid code the command is recorded as `remote.pending` and the DM asks for `confirm`:
replying `confirm` within 2 minutes runs the latest pending `plan` or `ask`. Each
accepted factor is recorded as `remote.confirmed`. `status`, `report`, `stop <session>`,
`stop all` and decision replies need no second factor. A reply to a decision is recorded
as `decision.replied` evidence; with no remote session waiting on it, confirm it on the host.

`plan` and `ask` start one headless Claude Code session per command message
(`claude -p --output-format json --permission-mode dontAsk --strict-mcp-config`, with the
role's tools in `--allowedTools`, and no MCP server); a reply to one of its decisions
resumes it with `--resume`. No session starts or resumes while free memory on the host
is below `host.free_memory_mb`. The
session is listed in `wuwei sessions` with role `remote`. A tool outside the role's
tools is refused and arrives as a decision; granting it stays a host change.

Messages to your owner DM are sent, not drafted: they pass the security check and the
outward lint first, and a decision the lint refuses arrives as "D-n is waiting in the
workspace." Every other DM still becomes a draft. With `responder.enabled = false` no
command is handled; stored commands are handled once it is back on.

The listener writes a `listen: clock` line every two minutes. Session start reports
`listen dead` when today's latest clock line is older than `listen.dead_seconds`, or
when the listener is installed and wrote none today. A listener that is off or alive
adds nothing to session start. `wuwei status --line` shows `listen dead`,
`listen unmeasured` or `listen off` (nothing while alive, and nothing without an inbound
adapter), and `wuwei nudges` pages a dead listener as `listen: health`. A DM answer to a
two-way decision is recorded as your outcome by the listener. A DM answer to a
one-way or `unsure` decision shows in `wuwei nudges` and session start as "D-n answered
from the phone", and the status line counts them as `phone answers N`, until you
record the outcome.

## Private workspace environment

`.wuwei/env` stores adapter credentials outside tracked configuration. Init and
upgrade create it empty with mode `0600` and add its Git ignore rule. Existing
contents are preserved by upgrade. Use literal `KEY=value` lines; process
environment values take precedence. The CLI, scoped hooks and watch all load the
file before adapter calls. Restart a running watch after editing the file.

`wuwei config check` reports credential names and set/missing status per effective
adapter. It returns 1 for missing requirements and 2 when a check cannot run.
With an inbound adapter it adds a `Control plane:` section: `control_plane.owner` is
set, missing or invalid (the last two return 1; the pin is never printed), and
`WUWEI_TOTP_SECRET` is set or missing, which is information only.
See [adapter credentials](adapters.md#credentials) for every variable, syntax
rules and authentication requirements. No new config.toml keys are needed.

### Host protections and seat credentials

Hooks prevent mistakes; they are not the publishing guarantee. That guarantee lives
in the code host's branch rules and in which credentials seats can read (design 4.5
and 9.1). `wuwei config check` verifies both through the code_host adapter.

Host protections: for each `[[repos]]` entry it reads the protection of
`default_branch` and prints one line per setting.

| Line | `ok` when |
| --- | --- |
| protected ref | classic branch protection is readable |
| classic protection | printed instead of `protected ref` when the classic endpoint answers 404: `none visible (404: unprotected or no admin)`; information only, the other lines then come from rulesets |
| required checks | at least one required status check, including every `review_required_checks` name; the line lists the required names, and a `missing` line names the absent ones and the ones `required now` |
| required reviews | at least 1 approving review, or `shepherd.min_reviewers = 0` (solo owner); when the check named by `shepherd.review_gate_check` is required, a `missing` line says it may be satisfying it, and stays a finding |
| force pushes | force pushes are blocked |
| deletions | branch deletion is blocked |

When a line is `missing`, the next line links the branch settings page. When no classic
protection is visible it also prints one `gh api -X PUT .../protection` command for your own
terminal that sets the layout above; it is not printed over existing protection, which a PUT
would replace.

Seat credentials: `GH_TOKEN` and `GITHUB_TOKEN` in `.wuwei/env` or in the environment
that seats inherit are readable by any seat. Each line reports `not set`, `read-only`
(every classic OAuth scope starts with `read:`), a finding naming the variable, its
source and its write scopes, or `unmeasured`. Fine-grained and app tokens report no
scopes and are always `unmeasured`. Publish from your own `gh auth login`.

Every line is `ok`, `missing` with the exact setting to change, or `unmeasured`
(no permission to read, host unreachable, or `code_host = "none"`), with the reason
on stderr. The command returns exit 0 when everything is `ok`, exit 1 on any `missing`
line or write-scoped token, and exit 2 when anything is `unmeasured`; exit 2 wins
over exit 1. The check, review, force-push and deletion lines combine classic
protection with the branch's rulesets, so a branch protected only by rulesets measures
correctly.

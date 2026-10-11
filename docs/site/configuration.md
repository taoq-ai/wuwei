# Configuration

`bin/wuwei init .` creates `.wuwei/config.toml`. Change one value with `wuwei config set <key> <value>` and add a repository with `wuwei config add-repo` (see [calibration](#calibration)); each prints the diff and asks its Owner step card in the session, and writes only on your Yes. No host terminal is needed. `config set` writes strings, lists and tables in any layout, replaces a value that spans lines in place, and leaves every other line as it was; `wuwei config check` names a key set in two tables. Values below are the shipped template defaults. Omitted keys use CLI defaults. Unknown keys are a warning from `wuwei config check`, `wuwei doctor` and `wuwei init --upgrade`, with the line and the nearest documented key. `wuwei init --upgrade` removes an unknown key that has no near documented key and keeps a likely typo for you to fix, unless `template_version` is newer than the running plugin. The optional commented examples are inactive until uncommented. Paths in repository entries are relative to the workspace unless absolute.

## Sections

Every table `config.toml` accepts, and the heading below that documents its keys.

| Sections | Keys under |
| --- | --- |
| `[[repos]]`, `[repos.merge]`, `[repos.gates]`, `[repos.shepherd]`, `[prioritisation]`, `[discovery]`, `[tracker]`, `[tracker.states]`, `[owner]`, `[owner.verbosity]`, `[security]`, `[guards]`, `[worktree]`, `[checks]` | [Workspace and repositories](#workspace-and-repositories) |
| `[host]`, `[budget]`, `[memory]`, `[retro]`, `[metrics]`, `[build]`, `[codex]`, `[gates]`, `[pr]`, `[shepherd]`, `[shepherd.authors]`, `[watch]`, `[sessions]` | [Host, build and memory](#host-build-and-memory) |
| `[adapters]`, `[scanner]`, `[scanner.mcp]`, `[calendar]`, `[brief]`, `[chat]` | [Adapters and brief](#adapters-and-brief) |
| `[boundary]`, `[environments]`, `[deploy]`, `[merge]` | [Boundaries and deployment](#boundaries-and-deployment) |
| `[outward]`, `[outward.max_length]`, `[outward.servers]`, `[outbound]` | [Outward sends](#outward-sends) |
| `[calibrate]` | [Calibration](#calibration) |
| `[spec]` | [Specification mode](#specification-mode) |
| `[telemetry]`, `[telemetry.otlp]` | [Telemetry](#telemetry) |
| `[docs]` | [Docs](#docs) |

## Workspace and repositories

| Key | Default | Meaning |
| --- | --- | --- |
| `cap` | `0` | Maximum running build seats. `0` derives CAP at plan propose and at every sweep from the host and `budget.tokens_per_day`. Claude subagent seats take `host.seats`, or one per core, and free memory is not read; when a seat runtime launches its own process, CAP is the median of today's last five readings of the running seats plus the seats that fit above `host.free_memory_mb` at the measured seat cost, one per core, within `host.seats`; a positive number is your override, still bounded by the budget. The morning gate shows CAP with its measurement and seats per goal; the launch guard compares with the value derived at launch. |
| `template_version` | `""` | Plugin version that last wrote this file. `wuwei init` and `wuwei init --upgrade` raise it and never lower it. A plugin older than this value treats keys it does not know as unknown to it, records `config.newer_template` once per session, and `wuwei doctor` and the status line say to restart Claude Code. |
| `prioritisation.framework` | `"wsjf"` | Ranking formula: `wsjf` or `rice`. |
| `discovery.min_queue` | `2` | Discover again when a seat frees and the queue is below this count. |
| `discovery.autostart` | `"strict"` | Intraday start policy: `off` carries safe items to the next morning; `strict` admits confirmed-goal SLICE items above the approved queue cut; `goal` admits confirmed-goal SLICE items under CAP and budget. Unsafe or over-budget items come to you. |
| `tracker.backlog_filter` | `""` | Optional Linear team ID for backlog discovery. Empty reads accessible issues. |
| `tracker.states.in_review` | `"In Review"` | Linear workflow state name after a PR is raised. |
| `tracker.states.done` | `"Done"` | Linear workflow state name after a confirmed merge. |
| `tracker.required` | `true` | While `adapters.tracker` is not `none`, every approved item needs a ticket: `plan approve`, `plan add`, `build next`, `dispatch next` and the seat launch refuse without one. Below strict the reason names the item's card, where the planner proposes the ticket; under strict it names `bin/wuwei tracker create <item>` or `bin/wuwei plan set <item> ticket=<id>` for a host terminal. |
| `tracker.skip_tiers` | `[]` | Gate tiers that need no ticket, for example `["light"]`. The recorded gate tier decides, else the lead's tier. |
| `tracker.strict_close` | `true` | `wuwei close` refuses while an item merged today has a ticket with no successful done transition (`bin/wuwei tracker done <item>`). `false` prints the line and closes. |
| `tracker.create` | `["bugs", "triage", "follow-ups"]` | Ticket classes seats may open besides items with `bin/wuwei tracker create --bug, --triage or --follow-up`; a seat adds `--seat <role>`, which the retro shows. |
| `tracker.log` | `["decisions", "progress", "verdicts", "pr", "close"]` | Comment kinds `bin/wuwei tracker log` writes on each item's ticket. |
| `tracker.auto` | `["progress", "pr", "close"]` | Every class and kind goes out through the tracker port after the outward lint (#838). This list only picks the kind a folded comment is filed under. |
| `tracker.max_per_item_per_day` | `10` | Comments per ticket per day; the last allowed one folds the rest into one comment. |
| `tracker.project` | `""` | Where new tickets go: a Linear team ID (empty uses `backlog_filter`), a Jira project key (required for Jira) or a GitHub `owner/repo` (empty uses the first repository). |
| `tracker.board` | `""` | GitHub Projects board as `owner/number`; transitions set its Status field. Empty uses a label for in review and closes the issue for done. A board or project outside `outbound.code_host_orgs` makes every tracker write a draft. |
| `tracker.auth` | `"token"` | How `tracker.github` authenticates: `token` uses `GITHUB_TRACKER_TOKEN`; `gh` uses your gh login when that token is unset (the token is used first when set). The gh login is broad, so the tracker path gives up least privilege; seats still reach the tracker only through `bin/wuwei`. See [GitHub tracker through your gh login](adapters.md#github-tracker-through-your-gh-login). |
| `profile` | `"strict"` | Guard profile: `strict` or `standard`. Standard warns for outward text lint. |
| `guards.enforce` | `true` | `true` blocks a guard refusal. `false` records it as `guard.would_refuse` and lets the call through; records, merges, approvals, admin merges, deploys and held outward sends still refuse. `init --shadow` writes `false`, and `init --upgrade` maps `security.posture = "observe"` or `guards.mode = "shadow"` to `false`. The outward lint and unknown tool names, another item's scratch directory and the seat capacity and ticket checks at launch are logged either way. `config check` and `doctor` print the setting. |
| `security.required` | `true` | When true, a missing `.wuwei/security.json` makes guards fail closed instead of treating security as disabled. |
| `worktree.git_hooks` | `"chain"` | How `worktree add` installs the git hooks. `chain` runs WUWEI's pre-commit and pre-push checks, then the repository's hook of the same name, when the repository has its own `core.hooksPath` or real hooks in `.git/hooks`: the scripts go in a generated directory under the worktree's git directory and the repository's setting is never changed. Without its own hooks the worktree uses `.wuwei/git-hooks`. `skip` installs none, warns and records `worktree.hooks_skipped`. `replace` uses `.wuwei/git-hooks` and the repository's hooks do not run in the worktree, for a repository you own outright. When chaining is impossible (a hooks path that is not a directory, no permission, `core.bare` or `core.worktree` set), `worktree add` still creates the worktree, warns and records `worktree.hooks_skipped`. The Claude Code PreToolUse guard checks `git commit` and `git push` either way. `doctor` shows a `git hooks` row per repository; `init --upgrade` rewrites the scripts. |
| `repos` | `[]` | Configured repositories. Each `[[repos]]` entry has the fields below. |
| `repos.name` | Required per entry | Code host name, such as `owner/repo`. |
| `repos.path` | Required per entry | Repository path from workspace root or absolute path. |
| `repos.default_branch` | Required per entry | Protected base branch. |
| `repos.identity` | `{name = "", email = ""}` | Expected git identity for this repository; the commit guards compare commits against it. Set both values. `wuwei worktree add` writes it to each item worktree's Git config. |
| `repos.merge_deploys` | `true` when omitted | Whether a merge deploys. While it is not `false`, every merge in the repository is yours. Only you set `false`, with `config set repos.<n>.merge_deploys false` on its card. |
| `repos.merge_method` | `"auto"` when omitted | How WUWEI merges in the repository: `squash`, `rebase` or `merge`. `auto` uses the first of squash, rebase, merge that the repository and its rulesets allow. An explicit method the repository does not allow is yours to merge, and the reason names `repos.merge_method`. `wuwei merge check` names the method. |
| `repos.merge.auto` | `false` | Allow automatic merge only when the merge policy's review, check, soak, path and budget rules pass. |
| `repos.merge.size_exclude` | `[]` | Path globs, matched on any path suffix, for generated files such as `results/*.json`. A changed file whose every path matches one does not count toward `max_changed_lines` or the review tier; a rename counts when either path does not match. Lockfiles, `linguist-generated` globs in the repository's root `.gitattributes` (ignored when the diff changes that file) and data files never count either. Never-auto paths still apply to these files. |
| `repos.merge.soak_skip` | `"base_fix"` | `base_fix` skips the soak for a PR whose head turns a check that fails at its base commit green, so a fix to a broken base lands without waiting. `never` always waits `soak_minutes`. |
| `repos.merge.size_exclude` | `[]` | Path globs, matched on any path suffix, for generated files such as `results/*.json`. A changed file whose every path matches one does not count toward `max_changed_lines`; a rename counts when either path does not match. Never-auto paths still apply to these files. |
| `repos.gates.floor` | `"standard"` | Lowest review tier for this repository: `light`, `standard` or `full`. `wuwei dispatch next` computes a tier from the item diff at its first gate; LIGHT runs the quality gate only, STANDARD and FULL run arch, quality and security. A docs-only diff skips a floor below `full` and runs one reviewer, goal or quality ([review tiers](concepts.md#review-tiers)). Keep `standard` until the escaped defects per tier in the retro support lowering it. |
| `repos.gates.light_max_lines` | `100` | A diff with more changed lines is at least STANDARD, except a docs-only diff. Generated and data lines do not count, and the reason names both totals, for example `5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100`. Binary changes outside data files, any lead flag and track FULL also raise the tier. |
| `repos.gates.data_paths` | `[]` | Path globs, matched on any path suffix, for data such as `corpus/runs/` (a trailing `/` means the directory). Their lines never count toward the tier or `max_changed_lines`, and they count as documents for the docs-only reviewer. `.json`, `.jsonl`, `.csv` and `.parquet` files over 200 changed lines or with a binary change are data without being listed; such a `.json` still keeps every gate, since it may be config. |
| `repos.gates.trust_paths` | `["guards/*", "state.py", "adapters/*", ".claude-plugin/*", ".github/*", "ci/*", "workflows/*", "deploy/*", "infra/*"]` | Path globs, matched on any path suffix, that force at least STANDARD. `repos.merge.never_auto_paths` and `brief.full_path_patterns` force it too. |
| `repos.shepherd.reviewers` | `[]` | Code host logins requested for this repository's PRs; when set it replaces `shepherd.reviewers` here. |
| `repos.fast_checks` | `[]` | Commands for `wuwei fast-checks` on this checkout. A command whose first word starts with `.venv/`, `venv/` or `node_modules/.bin/` resolves that interpreter in the item worktree first, then in the repository's main worktree (its `path`); the check record names the interpreter it ran with. `worktree add` warns when a new worktree will use the main worktree's, `doctor` shows a `check interpreter` row, and the builder brief names it. |
| `repos.check_timeout_seconds` | `300` | Seconds one run of one check command may take in this repository: fast checks, `repos.tests`, `checks.bootstrap` and `config promote --measure`. Past it the check is exit 2 with ``fast check `<cmd>` exceeded <n> s (repos.<n>.check_timeout_seconds)``. |
| `checks.python` | `""` | Interpreter for fast checks whose first word is a relative Python such as `.venv/bin/python`; absolute or relative to the repository's path. It wins in every worktree. |
| `checks.bootstrap` | `""` | One command `worktree add` runs in each new worktree through the checks runner (capped at `repos.check_timeout_seconds`), for example `python3 -m venv .venv && .venv/bin/python -m pip install -q -e .`. A failure is one warning line and the worktree is still created. Use it when the package is installed editable in the main worktree's venv: that interpreter can import the main worktree's code instead of the item's. |
| `owner.name` | `""` | Name used by outward text checks. |
| `owner.pronouns` | `""` | Owner pronouns for outward text checks. |
| `owner.handles` | `[]` | Bare chat IDs and code host handles the outward lint treats as your name. |
| `owner.timezone` | `""` | IANA time zone, for example `"Europe/Amsterdam"`, for the quality hour bands and `sessions.rotate_after.clock`. Empty uses this machine's zone. |
| `owner.verbosity.default` | `"brief"` | How much the CLI tells you: `brief`, `standard` or `full`. At `brief` a card shows each option's first sentence and the report leads with up to three outcome numbers that changed. `standard` shows each option in full and keeps the earlier report. `full` adds every field. |
| `owner.verbosity.decisions` | `""` | Level for an MCP registry card. Empty uses `owner.verbosity.default`. |
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
| `spec.mode` | `"strict"` | `strict` refuses source edits in an item worktree while a step before implementation is missing, keeps the item from the gates until every step is done (a failing check named `spec` in the build loop; `wuwei dispatch next` refuses too) and refuses a builder stop whose last message does not name its artifacts. `advisory` lets each call through and records the first gap per item and day as one `spec.warned` event, listed in the report. `off` checks nothing. With `guards.enforce = false`, `strict` runs as `advisory`. |
| `spec.skip_tiers` | `["light"]` | Lead tiers (`light`, `standard`, `full`) whose items need no spec. The skip holds only while the diff agrees: at the move to the gates, a computed tier outside this list needs the spec after all. |

Steps per engine, each run by the builder with the engine's own command, read from the artifacts in the item's worktree (the item id lowercased):

- spec-kit (`specs/<item>` or `specs/*-<item>`): `specify` (`spec.md`), `clarify` (a `## Clarifications` section), `plan` (`plan.md`), `tasks` (`tasks.md`), `analyze` (`analysis.md` with no CRITICAL or HIGH finding row), `checklist` (every item checked in `checklists/*.md`), `implement` (every task checked).
- superpowers: `brainstorming` (`docs/superpowers/specs/<date>-<item>-design.md`), `writing-plans` (`docs/superpowers/plans/<date>-<item>.md`), `executing-plans` (every step in that plan checked), `verification-before-completion` (the fast checks and the gates).
- OpenSpec (`openspec/changes/<item>`, later `openspec/changes/archive/*-<item>`): `proposal` (`proposal.md`), `specs` (`specs/<capability>/spec.md`), `tasks` (`tasks.md`), `validate` (`validation.json` from `openspec validate <item> --strict --json`, every entry valid), `apply` (every task checked), `archive` (before the gates).

You skip or require the spec for one item in a host terminal: `bin/wuwei plan set <item> spec=skipped --reason <why>` or `bin/wuwei plan set <item> spec=required`. `wuwei doctor` fails a repository where the engine is absent and prints its install line:

- spec-kit: `uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude`
- superpowers: `/plugin marketplace add obra/superpowers-marketplace`, then `/plugin install superpowers@superpowers-marketplace`
- OpenSpec: `npm install -g @fission-ai/openspec`, then `openspec init`

A Claude Code subagent cannot write `analysis.md` itself: Claude Code refuses a subagent's Write of a Markdown file named like a report, in any directory. A builder seat saves the analyze report with `bin/wuwei spec analysis <item> < report` and gives a scratch file another name.
A Claude Code subagent cannot write `analysis.md` itself, so a builder seat saves the analyze report with `bin/wuwei spec analysis <item> < report`. An item can name a governing document: the lead's `governed_by`, or a `Governing: <path>#<heading>` line in `spec.md`. Its report must then end with a `## Governing` table, or the command refuses it. The table has one row per assumption: `agrees`, `conflicts` or `not covered`, and the cited `<path>:<line>`.


## Host, build and memory

| Key | Default | Meaning |
| --- | --- | --- |
| `host.free_memory_mb` | `1024` | Nonnegative free memory floor in MiB. |
| `host.seats` | `0` | Total seat ceiling, builders and gates. `0` means one per core for Claude subagent seats, and the free memory and cores fit like CAP when a seat runtime launches its own process; a positive number is your override. Refusals name `host.seats`; it bounds CAP and each turn of `wuwei dispatch next --all`. |
| `budget.tokens_per_day` | `0` | Input plus output tokens a day. With a per-seat token cost measured from `seat.usage` rows, CAP is at most the seats the remaining budget fits (at least 1) and says `(budget)`. `0` is no budget. |
| `host.reservation_timeout_seconds` | `14400` | Age at which a reservation is reported stale. |
| `host.rate_limit_wait_seconds` | `120` | Longest wait for a GitHub rate limit to reset before one retry; beyond it the reason names the reset time. `0` never waits. |
| `memory.budget_tokens` | `6000` | SessionStart memory payload budget in estimated tokens; over it today's lines are left out first. |
| `memory.export_to` | `"CLAUDE.md"` | Workspace-relative file that receives the generated rules block (`init`, `init --upgrade`; `init --upgrade` also removes the guide block an older version wrote); never under `.wuwei/`. |
| `retro.repo` | `"."` | Repository used for retro evidence. |
| `retro.charter_paths` | `[".wuwei/charters"]` | Paths to charter procedures reviewed during retro. |
| `retro.changelog` | `".wuwei/memory/CHANGELOG.md"` | Retro change log path. |
| `metrics.transcripts` | `"~/.claude/projects"` | Claude Code project transcript directory for attended time. Sessions are filtered to the workspace and its repositories. |
| `metrics.band_margin` | `0.2` | The retro names a worst hour or session-age band only when its gate FIX rate over the last 7 days exceeds every other measured band by at least this much. |
| `build.max_iterations` | `8` | Maximum build iterations. |
| `build.stuck_after` | `3` | Repeated progress limit. |
| `build.poll_interval_seconds` | `5` | Runtime job poll interval. |
| `build.poll_timeout_seconds` | `3600` | Runtime job poll timeout. |
| `codex.command` | `[]` | Companion command; fill in to use Codex runtime. |
| `codex.timeout_seconds` | `300` | Codex command timeout. |
| `gates.second_opinion` | `"off"` | `"<runtime>:<model>"`, for example `"codex:gpt-6-astra"`, runs one gate of every STANDARD and FULL item a second time on that runtime and model. Its verdict is one more gate record named `<role>@<runtime>`; a blocking finding from either model blocks. `claude` and `none` are refused. |
| `gates.second_opinion_role` | `"quality"` | The gate role the second opinion repeats: `arch`, `quality` or `security`. |
| `gates.max_rounds` | `2` | Fix rounds per item before it ships or parks, the same for code, spec and document items. A FIX verdict opens round one; after a delta only a blocking finding opens the next. At the cap the remaining non-blocking findings go into the PR body as review notes and the item ships. A blocking finding parks it with the finding as its reason; `wuwei plan resume <item>` asks you to resume it. Minimum 1. The report's `## Rounds` section counts them. |
| `gates.tier_max_rounds` | `{ light = 0, standard = 0, full = 0 }` | A round cap per review tier; `0` uses `gates.max_rounds`. |
| `gates.polish` | `"offer"` | After a round-one pass with review notes: `never` raises the PR at once, `offer` lets the planner take one polish round (`dispatch polish <item>`) or decline it (`dispatch skip-polish <item>`), `always` opens it. The builder fixes only the notes and one gate (the one that wrote them, else quality) re-checks the delta. It counts as a fix round. |
| `pr.poll_seconds` | `120` | Interval between full reads of raised and claimed PRs. |
| `pr.action_minutes` | `30` | Positive minutes to act on a measured PR finding. A warning in the event log after this deadline, a page at twice the interval. |
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
| `shepherd.authors` | `{}` | Map author email to verified `{login, mention}` reviewer identity; `mention` is optional (default `""`) and a review ping refuses a reviewer without one. An unmapped email is resolved to the code host login for that email and cached for the day; one the code host cannot resolve is skipped with a `reviewer.unresolved` event, never a refusal. |
| `watch.clock_seconds` | `600` | Interval between watch clock events. |
| `watch.dead_seconds` | `1200` | Clock age after which the watch is reported dead. |
| `watch.stale_seconds` | `900` | Inactivity age at which running work is reported stale. |
| `watch.sweep_seconds` | `7200` | Interval between supervision sweeps. |
| `watch.ping_url` | `""` | https check URL of a hosted cron monitor; each healthy watch heartbeat pings it (see the heartbeat reference). Keep it private. |
| `sessions.stale_seconds` | `3600` | Seconds without hook activity after which a registered session is stale: it stops counting in `wuwei status`, its item claims lapse, and a stale planner pages through the heartbeat. |
| `sessions.rotate_after` | `{ turns = 0, compactions = 0, clock = "" }` | Scheduled planner rotation, off by default. `turns` (Stop hooks since the session started today), `compactions` (compactions seen) or `clock` (`"HH:MM"` in `owner.timezone`): when one is reached, the Stop hook asks the planner once, at a turn with no running seat, to end the session and run `wuwei plan session "$WUWEI_SESSION_ID" --take-over` in a fresh one. |


## Telemetry

Weekly usage counts that say whether WUWEI itself works: how often guards refuse or cannot run, how long a hook takes, how often items loop, how many decisions reach you. The watch sweep aggregates them at most once a day into `.wuwei/metrics/<week>.json`, never in a hook; `bin/wuwei metrics --week [<week>]` prints a week on demand.

| Key | Default | Meaning |
| --- | --- | --- |
| `telemetry.enabled` | `true` | `false` stops the aggregate, sharing and the OpenTelemetry export. |
| `telemetry.share` | `""` | `"anonymous"`, `"attributed"` or `"off"`. Empty means you have not chosen yet and sends nothing; `bin/wuwei doctor` lists it as pending with the `config set telemetry.share` command. |
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
| `adapters.tts` | `"say"` on macOS, `"none"` elsewhere | Speech output port. No command calls it since #789 part 5. |
| `adapters.calendar` | `"none"` | Meeting source: none or a private ICS feed. |
| `adapters.transcripts` | `"none"` | Meeting transcript port. No command calls it since #789 part 5. |
| `adapters.redactor` | `"builtin"` | The redactor adapter: built-in patterns for phone numbers, email addresses and secrets. |
| `calendar.url` | `""` | Private HTTPS ICS URL. `WUWEI_CALENDAR_URL` overrides this setting. Keep the URL secret. |
| `brief.remote` | `"origin"` | Git remote used for a brief. |
| `brief.prior_branch_pattern` | `"*{item}*"` | Branch match, with lowercased item substituted. |
| `brief.full_path_patterns` | `[]` | Owner supplied regexes for paths needing full context. |
| `chat.identity` | `"connector"` | Optional CLI default: connector or custom_app. This key is not in the template. |

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
| `docs.auto` | `[]` | Kept for older workspaces. Every page kind is written through the docs port after the outward lint (#838). |
| `docs.strict_close` | `true` | `wuwei close` refuses while a merged item's docs obligation is unmet; `false` lists those lines in the report's `## Docs` section instead. |

## Boundaries and deployment

| Key | Default | Meaning |
| --- | --- | --- |
| `boundary.api` | Not set | Example named boundary; `[boundary]` accepts names and descriptions. |
| `environments.production` | Not set | Example environment; `[environments]` accepts names and descriptions. |
| `deploy.workflows` | `[]` | Workflow names, filenames, paths or IDs treated as deploy actions. |
| `deploy.deny` | `[]` | Literal executable plus argument globs to refuse. |
| `merge.owner_paths` | `[]` | Globs only you merge, for example guard files, workflows or the signing key path. Matched like `never_auto_paths`, on any path suffix of a changed or renamed path. A match is yours to decide: the reason names the path and the glob, and `bin/wuwei merge <pr>` merges only on your Yes on its Owner step card. |

The template also shows a `"release/*"` environment example. Add any actual environment register entries before using rules that depend on them. WUWEI does not deploy on its own: a deploy runs from a session only on your Yes on its Owner step card (see [owner-only actions](concepts.md#owner-only-actions)).

## Calibration

`wuwei config promote` runs the calibration: it surveys every configured repository and applies the proposal after you answer its Owner step card in the session. The section below describes what it proposes.

Two commands change one value, each with a diff and its Owner step card, the same path as `config promote`. The value is parse-checked before you are asked; an invalid one is refused with the reason and nothing is written:

- `bin/wuwei config set <dotted.key> <toml-value>`, for example `bin/wuwei config set owner.verbosity.default '"standard"'` or `bin/wuwei config set repos.0.merge_deploys false` (repositories by index), and a list of tables such as `bin/wuwei config set outward.tool_patterns '[{pattern = "mcp__custom__send", channel = "customer"}]'`. A value that is not TOML is refused with the type the key takes and an example. A table such as `owner.verbosity` is set one key at a time, and a deploy list only grows. The value is written as given, so a list key is replaced, built-in items included, and `'[]'` empties it (`config set docs.publish '[]'`; a deploy list still only grows). After the write it prints `replaced: <key> = <new> (was <old>)`. `--add` adds the items to the effective list instead, so the built-in items stay and an item already there is not added twice (`config set outward.allow '["mcp__slack__slack_send_message"]' --add`); on a named-entry table such as `outward.servers` it adds or replaces the given entries. It then prints `added: ...`, as does a deploy list. `--add` on any other key is refused. `--replace` is the default and may be passed for clarity. `bin/wuwei config show <key>` prints the effective value, one row per item or entry, each tagged `default` or `owner`.
- `bin/wuwei config add-repo --name acme/widget --path widget --branch main --identity "Pat Example <pat@example.test>"` appends one `[[repos]]` table; a duplicate name or path is refused.

Run `wuwei config promote` after `init` and the `[[repos]]` entries (`name`, `path`, `default_branch`), and before the first plan. It reads each checkout; without `--measure` it runs nothing there. It exits 0 when it applied or found nothing to change, 1 without your Yes, and 2 when it could not run.

| Detector | Reads | Proposes |
| --- | --- | --- |
| Toolchain | `pyproject.toml`, `pytest.ini`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`, a markdownlint config, `.latexmkrc`. With none of those, a single-line test, check or lint `run:` step of a workflow on `pull_request` or `push`, with no shell control or expansion character (`;&|<>$` or a backtick) | `repos.fast_checks` from a fixed command table; only the CI step is the repository's own command |
| CI checks | `.github/workflows/*.yml` run on `pull_request` | `repos.review_required_checks`: job names, one per leg of a single inline matrix, without `continue-on-error: true` jobs |
| Conventions | `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.specify/memory/constitution.md`, `CODEOWNERS`, PR and issue templates | `[boundary]` candidates from `CODEOWNERS` |
| Deploy signals | workflows run on a push to the default branch, tags or a release that use an environment, a deploy or release action, or a deploy command; deploy `Makefile` targets and `package.json` scripts; infrastructure directories | `deploy.workflows`, `[environments]`, `deploy.deny`, `repos.merge_deploys = true`, `repos.merge.never_auto_paths` |

It also reads the last 30 merged pull requests for a size and cycle time baseline, which the steward gets as advisory input.

The proposal is additive. A key absent from `config.toml` is added, and `deploy.workflows`, `deploy.deny` or `repos.fast_checks` still at a one-line `[]` is replaced. A key you already set is never changed: the digest lists it under "Config differs; edit by hand". Calibration never proposes `merge_deploys = false` or `merge.auto`; you set them with `config set`.

Only fast commands go into `repos.fast_checks` through `config promote`. `ruff check .`, `black --check .`, `npm run lint`, `make lint` and `markdownlint .` are fast. A test runner (`python3 -m pytest -q`, `npm test`, `cargo test`, `go test ./...`, `make test`, `make check`) is CI only unless measured. `wuwei config promote --measure` runs each detected test runner once in the configured checkout through the checks port, the same runner as `wuwei fast-checks` (`/bin/sh -c <command>`, capped at `repos.check_timeout_seconds`, default 300), and may leave tool caches there. A measured run at 80 % of that limit or more proposes `check_timeout_seconds` at twice the limit. It is fast when it exits 0 within `calibrate.fast_check_seconds` (default 60). The promote digest lists the rest as `CI only, not proposed as a fast check` lines with the measurement or "unmeasured".

`fast_checks = []` means none configured: items build, `wuwei pr raise` adds `checks: none configured` to the PR body, and CI and the gates are the evidence; `wuwei status` and `wuwei doctor` say so.

Repository text is data. A file with instruction-like text, such as a line telling an agent to ignore its instructions, contributes nothing; the digest names its file, line and rule as a `Flagged` line without quoting it. Job, environment and owner names outside a safe character set are reported as unsafe and dropped.

`wuwei config promote` recomputes the proposal, prints the diff and the calibration it will record, asks its Owner step card, then writes `config.toml` and `.wuwei/calibration.json`. Agent tools are refused both.

On each sweep the steward compares the fast checks, CI check names and deploy signals with `.wuwei/calibration.json` and records one `calibration.drift` event per change per day. Run `wuwei config promote` again to approve the new state; `bin/wuwei doctor` names it.

## Outward sends

| Key | Default | Meaning |
| --- | --- | --- |
| `outward.allow` | `[]` | Exact MCP tool names that may send to other people. A write through any other MCP tool is refused with exit 1, whatever `guards.enforce` says. So is a tool whose name is neither a read nor a write. The refusal names the line to add, `bin/wuwei config set outward.allow '["<tool>"]' --add`, which asks its Owner step card. The match is exact: no pattern, prefix or case folding. A local tool and a write to [your own surfaces](#your-own-surfaces) never need it. |
| `outward.banned_characters` | `emoji`, U+2014, U+2015, U+2E3A, U+2E3B | Setting a list replaces defaults. |
| `outward.tool_patterns` | Built-in Slack, Linear, GitHub, Notion and Atlassian MCP matches | Tool regex plus the lint channel. The built-in rules match the brand anywhere in the name, so `mcp__<uuid>__slack_send_message` is Slack. A list in `config.toml` or from `config set` replaces the defaults; `config set --add` adds to them. They decide no send. |
| `outward.servers` | `{}` | MCP server id to its lint channel (`slack`, `tracker`, `code_host`, `docs`, `mail` or `other`) or `local`, checked before the rules. A `local` server acts only on your machine and passes the outward guard. Built in: `terminal`, `Claude_Preview`, `Claude_Code_iOS_Simulator`, `computer-use` and the `Claude_Browser` preview tools. The Bash guards judge a `run_in_terminal` command. Reads still pass. |
| `outward.max_length.slack` | Not set | Example positive maximum for one channel under `[outward.max_length]`. |
| `outward.humanize` | `true` | Lint outward text for AI tells before it is sent; `false` turns the lint off. |
| `outward.humanize_kinds` | `["dm", "tracker", "docs", "pr", "review"]` | Kinds the lint checks: DMs, tracker comments, docs pages, PR comments and PR bodies, and other chat posts such as review pings. |
| `outward.humanize_strict` | `false` | `true` refuses a text with a tell; `false` warns and records `outward.ai_tells`. |
| `outbound.code_host_orgs` | `[]` | Internal code host organizations. A GitHub tracker outside them is external, so WUWEI creates no labels there. |
| `outbound.owner` | all empty | Your own identity per surface: `slack.user` (U or W id), `slack.dm` (your own DM channel, D id, never the WUWEI app DM), `mail`, `pages` (your own Slack canvas ids and Notion or Confluence page ids) and `code_host` (login). See [Your own surfaces](#your-own-surfaces). |
| `outbound.owner_channel` | `"session"` | `session` or `dm`. With `dm` the planner also posts the day report to `outbound.owner.slack.dm` (or `slack.user` when `dm` is empty). |

WUWEI's own outward duties go through its adapter ports, which you configure: a review ping, a tracker comment or ticket, a docs page, the day report and a PR thread reply. Each passes the canary check and the outward lint, and none needs `outward.allow`. A channel limit does not bypass the outward text checks. The shipped [template](https://github.com/taoq-ai/wuwei/blob/main/templates/workspace/config.toml) has the defaults and examples.

## Your own surfaces

A write whose every destination is yours is local, never an outward send. It passes without `outward.allow`, the lint skips its third-person rules, and it records an `outward.to_owner` event. The destinations are the values under `channel`, `channel_id`, `recipient`, `recipients`, `to`, `cc`, `bcc`, `page_id`, `database_id` and `canvas_id`, at any depth. So a Notion `parent.page_id` counts.

| Surface | Your config | Matches |
| --- | --- | --- |
| Slack self-DM | `outbound.owner.slack.dm` and `outbound.owner.slack.user` | a message whose channel or recipient is one of them |
| Slack canvas | `outbound.owner.pages` (canvas ids) | a canvas write whose `canvas_id` is yours |
| Notion or Confluence page | `outbound.owner.pages` (page ids) | a page update by `page_id`, or a create whose `parent.page_id` is yours |
| Mail to yourself | `outbound.owner.mail` | every recipient, cc, bcc and address in the text is yours |

A call with no destination is never yours. Your code-host login is never local: others read a code-host comment.

## Goals and discovery

While `memory/goals.md` has no goals, the lead proposes goal objects in its JSON, `wuwei plan propose` shows them as provisional and writes `days/<date>/goals.md`, and when you approve them in the morning gate, `wuwei plan approve` validates that file, writes it to `memory/goals.md` and commits it in `.wuwei` history with `Promoted-by: wuwei` and `Edited-by: owner`, so SessionStart does not flag it as an unpromoted edit. A later change to `.wuwei/memory/goals.md` is recorded the same way by the next gate approval; agent tools cannot write the file. Each `## G-n` block needs `outcome`, `measure`, `target`, `date` in ISO format, and a positive integer `priority`. Priority 1 wins score ties. `wuwei rank candidates.json` reads JSON candidates with a goal or `unplanned` mark, a `score` object, and one `evidence_lines` entry per score component. `wuwei discover` reports unavailable sources as `unmeasured`. It reads the tracker backlog of every configured repository, and `--repo <org>/<name>` narrows it to one.

After the morning gate, sweeps and qualifying seat-free events save new discovery candidates. A builder seat stop only records the seat-free request; the watch runs that discovery on its next tick and records a failure once as `discovery.unmeasured`. Run `bin/wuwei plan add <item>` to apply the same admission gate to one saved candidate. A started item enters the existing `build next` path when a builder brief and worktree are logged; otherwise a build request remains visible for the planner. Owner proposals appear in the steward decision batch. The morning plan shows safe `off` mode candidates carried from the prior day.


### MCP registry checks (S3)

`wuwei init` and `wuwei init --upgrade` discover attached MCP configurations and
register them through `scanner.mcp`. Set `adapters.scanner = "ziran"` to use ZIRAN
0.39.0 or newer. `none`, the default, turns the registry gate off: every MCP
command and the launch gate exit 0, the first check of the day with attached servers
prints `mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)`, and doctor shows
the gate ok. Nothing checks
attached servers for tool drift or poisoning then. A configured scanner that is
missing or the wrong version is a check that could not run (exit 2) and blocks
launches under `guarded` and `strict`. No attached servers is a clean empty registry.
WUWEI declares no MCP server of its own.
A `.mcp.json` added to the install, one in a workspace or repo, and any other
plugin's servers are discovered and checked like any other. Coverage goes by install directory, so another plugin
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

`scanner.mcp.block` is unset by default, so no finding blocks. Set it to refuse agent and
runtime launches and `plan propose`: a pending finding with a listed severity (exit 1), or
any unmeasured server when the list holds `"unmeasured"` (exit 2). Everything else is a
warning in the event log. With `guards.enforce = false` the list has no effect. The full
v0.11.0 behaviour is `["high", "critical", "unmeasured"]`. A check that could not run
(invalid input, an interrupted check, a stale or missing record) refuses with exit 2 while
`guards.enforce` is on. A workspace created before #351 carries `block = ["critical"]` from
the old template; `bin/wuwei config check` names it, and deleting the line takes the
default.

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

To answer it, run `bin/wuwei mcp decide D-<n> proceed` (or `defer`) from a host terminal
and answer y. Under
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

`bin/wuwei status --line`, `bin/wuwei doctor`, session start and
sweeps all read watch health the same way, whatever the last sweep recorded:

- Installed with `watch install`, and no clock line today or today's latest
  clock older than `watch.dead_seconds`: `watch dead`, one `watch: health` page.
  This catches a watch that died overnight. It clears at the next clock line, or
  after `watch uninstall` when no clock line was written today.
- Not installed, and no clock line today: `watch off`, neither a page nor a
  warning.
- Not installed, and today's clock went stale (a watch run by hand died):
  `watch dead`, one page.

`watch unmeasured` means watch health cannot be read; it is one warning in the event log.

`bin/wuwei doctor` lists each open page with its fix (`wuwei next` for a health page,
`wuwei why <item>` for an escalation), and the status line counts them. Warnings stay in the day's `events.jsonl`, where `bin/wuwei why` and the retro
read them. Routine progress such as plan approval, build starts and checks, and a call to any
adapter set to `none` is silent.

## Private workspace environment

`.wuwei/env` stores adapter credentials outside tracked configuration. Init and
upgrade create it empty with mode `0600` and add its Git ignore rule. Existing
contents are preserved by upgrade. Use literal `KEY=value` lines; process
environment values take precedence. The CLI, scoped hooks and watch all load the
file before adapter calls. Restart a running watch after editing the file.

`wuwei config check` reports credential names and set, missing or `malformed (<why>)`
status per effective adapter, never the value: a token with whitespace, a path-like value or
shell characters is malformed (a pasted command, for example). It returns 1 for missing or
malformed requirements and 2 when a check cannot run. An HTTP adapter the provider refuses
reports `HTTP <status>` and a one-line hint (`HTTP 401` credential rejected, `HTTP 403` no
access, `HTTP 404` not found or not visible to the credential), which doctor shows.
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

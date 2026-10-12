# Configuration

`bin/wuwei init .` creates `.wuwei/config.toml`. The values below are the shipped template defaults. An omitted key uses the CLI default. A commented example in the template stays inactive until you uncomment it. Repository paths are relative to the workspace unless absolute.

Change one value with `bin/wuwei config set <key> <value>`, and add a repository with `bin/wuwei config add-repo` (see [calibration](#calibration)). Each prints the diff and asks its Owner step card in the session. It writes only on your Yes. `bin/wuwei config show <key>` prints the effective value, each row tagged `default` or `owner`. `bin/wuwei config check` validates the file and names a key set in two tables.

## Init and upgrade

`bin/wuwei init <path>` creates `.wuwei/` with this config, the security material, the private `.wuwei/env` and the integrity pin. `init --shadow` writes `guards.enforce = false`.

`bin/wuwei init --upgrade` brings an existing workspace up to the running plugin. It adds new template keys and sections, raises `template_version` and rewrites the executable pointer. It also removes what no command reads any more:

- every config key retired by the deletion pass, printed as `Upgraded config.toml: remove <key> (no longer read)`;
- every obsolete file or directory under `.wuwei/`, printed as `Upgraded .wuwei/<path>: remove (no longer read)`;
- generated copies of skills and agents the plugin no longer ships.

It never removes through a symlink, never outside `.wuwei/` and never under `days/`, which is history. Such a path prints `left .wuwei/<path>: <reason>`. `--dry-run` prints the same lines as `Would upgrade ...` and changes nothing.

An unknown key is a warning from `config check`, `doctor` and `init --upgrade`, with its line and the nearest documented key. `init --upgrade` removes an unknown key with no near match. It keeps a likely typo for you to fix. When `template_version` is newer than the running plugin, it removes nothing.

Upgrade also maps old settings onto the ones that replaced them. `security.posture = "observe"` or `guards.mode = "shadow"` becomes `guards.enforce = false`. A `repos = []` line next to `[[repos]]` tables is removed, since TOML rejects the two together.

Recent removals include `adapters.redactor`, `adapters.calendar`, `adapters.tts`, `[calendar]`, `owner.verbosity.decisions`, `retro.repo`, the `[watch]`, `[sessions]`, `[worktree]`, `[docs]` and `[discovery]` tables, and the outward tier, posture and draft keys.

## Sections

Every table `config.toml` accepts, and the heading that documents its keys.

| Sections | Keys under |
| --- | --- |
| `[[repos]]`, `[repos.merge]`, `[repos.gates]`, `[repos.identity]`, `[repos.shepherd]`, `[checks]`, `[prioritisation]`, `[tracker]`, `[tracker.states]`, `[owner]`, `[owner.verbosity]`, `[security]`, `[guards]` | [Workspace and repositories](#workspace-and-repositories) |
| `[spec]` | [Specification mode](#specification-mode) |
| `[host]`, `[budget]` (`[budget.claude]`, `[budget.codex]`), `[memory]`, `[retro]`, `[metrics]`, `[build]`, `[codex]`, `[gates]`, `[pr]`, `[duties]`, `[shepherd]`, `[shepherd.authors]` | [Host, build and memory](#host-build-and-memory) |
| `[telemetry]`, `[telemetry.otlp]` | [Telemetry](#telemetry) |
| `[adapters]`, `[scanner]`, `[scanner.mcp]`, `[brief]`, `[chat]` | [Adapters and brief](#adapters-and-brief) |
| `[boundary]`, `[environments]`, `[deploy]`, `[merge]` | [Boundaries and deployment](#boundaries-and-deployment) |
| `[calibrate]` | [Calibration](#calibration) |
| `[outward]`, `[outward.max_length]`, `[outward.servers]`, `[outbound]` | [Outward sends](#outward-sends) |

## Workspace and repositories

| Key | Default | Meaning |
| --- | --- | --- |
| `cap` | `0` | Maximum running build seats. `0` derives CAP at `plan propose` and whenever `wuwei next` plans launches, from the host. A positive number is your override. Each runtime's CAP is CAP bounded by the room left in its usage windows (`budget.*`). The morning gate shows CAP and how it was measured. |
| `template_version` | `""` | Plugin version that last wrote this file. `init` and `init --upgrade` raise it and never lower it. An older plugin treats keys it does not know as unknown, and `doctor` says to restart Claude Code. |
| `profile` | `"strict"` | Outward lint profile: `strict` or `standard`. Standard warns where strict refuses. |
| `guards.enforce` | `true` | `false` records a guard refusal as `guard.would_refuse` and lets the call through. Records, merges, approvals, admin merges, deploys and outward sends outside `outward.allow` still refuse. `config check` and `doctor` print the setting. |
| `security.required` | `true` | A missing `.wuwei/security.json` makes the guards fail closed. |
| `prioritisation.framework` | `"wsjf"` | Ranking formula `plan propose` orders the queue by: `wsjf` or `rice`. |
| `tracker.backlog_filter` | `""` | Optional Linear team ID for backlog discovery. Empty reads accessible issues. |
| `tracker.states.in_review` | `"In Review"` | Workflow state after a PR is raised. |
| `tracker.states.done` | `"Done"` | Workflow state after a confirmed merge. |
| `tracker.create` | `["bugs", "triage", "follow-ups"]` | Ticket classes seats may open besides items, with `bin/wuwei tracker create --bug`, `--triage` or `--follow-up`. |
| `tracker.log` | `["decisions", "progress", "verdicts", "pr", "close"]` | Comment kinds `bin/wuwei tracker log` writes on an item's ticket. The PR link and the merged note are the tracker duty. |
| `tracker.max_per_item_per_day` | `10` | Comments per ticket per day. The last allowed one folds the rest. |
| `tracker.project` | `""` | Where new tickets go: a Linear team ID, a Jira project key (required for Jira) or a GitHub `owner/repo` (empty uses the first repository). |
| `tracker.board` | `""` | GitHub Projects board as `owner/number`. Empty uses a label for in review and closes the issue for done. |
| `tracker.auth` | `"token"` | GitHub tracker authentication: `token` uses `GITHUB_TRACKER_TOKEN`; `gh` uses your gh login when that token is unset. See [the gh login](adapters.md#github-tracker-through-your-gh-login). |
| `repos.name` | Required | Code host name, such as `owner/repo`. |
| `repos.path` | Required | Checkout path, relative to the workspace or absolute. |
| `repos.default_branch` | Required | Protected base branch. |
| `repos.identity` | `{name = "", email = ""}` | Expected git identity. The commit guards compare commits against it, and `worktree add` writes it to each item worktree. |
| `repos.merge_deploys` | `true` when omitted | Whether a merge deploys. While not `false`, every merge in the repository is yours. |
| `repos.merge_method` | `"auto"` | `squash`, `rebase` or `merge`. `auto` takes the first the repository allows. |
| `repos.fast_checks` | `[]` | Commands `bin/wuwei build check <item>` runs in the item worktree. A first word under `.venv/`, `venv/` or `node_modules/.bin/` resolves in the worktree first, then in the main checkout. |
| `repos.check_timeout_seconds` | `300` | Seconds one check command may take. Past it the check is exit 2. |
| `repos.review_required_checks` | `[]` | CI check names a merge needs. Calibration proposes them. |
| `repos.merge.auto` | `false` | Allow WUWEI to merge only when every merge rule passes. |
| `repos.merge.size_exclude` | `[]` | Globs for generated files. They do not count toward `max_changed_lines` or the review tier. Never-auto paths still apply. |
| `repos.merge.max_changed_lines` | `400` | A larger counted diff is yours to merge. |
| `repos.merge.max_per_day` | `5` | Automatic merges per repository per day. |
| `repos.merge.soak_minutes` | `30` | Wait after the last push or approval before an automatic merge. |
| `repos.merge.soak_skip` | `"base_fix"` | `base_fix` skips the soak for a PR that turns a check failing at its base green. `never` always waits. |
| `repos.merge.quiet_hours` | `[]` | `HH:MM-HH:MM` windows with no automatic merge. |
| `repos.merge.never_auto_paths` | CI, manifests, lockfiles, migrations, infrastructure | Globs that keep a merge yours and force at least STANDARD review. |
| `repos.merge.reset_epoch` | `0` | Raise it past a tripped circuit breaker's epoch to reset that breaker. |
| `repos.merge.bot_login`, `repos.merge.bot_min_score`, `repos.merge.bot_score_pattern` | `""`, `5`, Greptile pattern | The review bot's login, its minimum score and the regex that reads the score. |
| `repos.merge.fix_pattern` | fix, bugfix, hotfix, revert | Commit message regex the retro counts as an escaped defect. |
| `repos.gates.floor` | `"standard"` | Lowest review tier: `light`, `standard` or `full` ([review tiers](concepts.md#review-tiers)). |
| `repos.gates.light_max_lines` | `100` | A larger counted diff is at least STANDARD, unless it is docs only. |
| `repos.gates.data_paths` | `[]` | Globs for data. Their lines never count toward the tier or `max_changed_lines`. |
| `repos.gates.trust_paths` | guards, adapters, CI, deploy, infra | Globs that force at least STANDARD. |
| `repos.shepherd.reviewers` | `[]` | Replaces `shepherd.reviewers` for this repository. |
| `checks.python` | `""` | Interpreter for a fast check whose first word is a relative Python. It wins in every worktree. |
| `checks.bootstrap` | `""` | One command `worktree add` runs in each new worktree, such as creating a venv. A failure is a warning. |
| `owner.name`, `owner.pronouns` | `""` | Your name and pronouns for the outward lint. |
| `owner.handles` | `[]` | Bare chat IDs and code host handles the lint treats as your name. |
| `owner.timezone` | `""` | IANA zone for the retro's hour bands. Empty uses this machine's zone. |
| `owner.verbosity.default` | `"brief"` | How much cards and the report say: `brief`, `standard` or `full`. |
| `owner.verbosity.report` | `""` | Level for `bin/wuwei report`. Empty uses the default. |

A minimal repository entry looks like this:

```toml
[[repos]]
name = "owner/repo"
path = "repos/project"
default_branch = "main"
identity = {name = "Builder", email = "builder@example.test"}
merge_deploys = false
fast_checks = ["python3 -m pytest -q"]
```

While `config.toml` does not load, every tool call is refused with the error. The exceptions are `ToolSearch`, a `Read`, `Grep` or `Glob` of the config or charters, and `config set` with its card. The session can still show and fix the line.

## Specification mode

| Key | Default | Meaning |
| --- | --- | --- |
| `spec.engine` | `"speckit"` | Engine every non-trivial item is specified with: `speckit`, `superpowers`, `openspec` or `none`. |
| `spec.mode` | `"strict"` | `strict` keeps an item from the gates until every step is done. `advisory` records one `spec.warned` event per item and day. `off` checks nothing. |
| `spec.skip_tiers` | `["light"]` | Lead tiers whose items need no spec. A computed tier outside the list needs the spec after all. |

The builder runs each step with the engine's own command. WUWEI reads the artifacts in the item worktree:

- spec-kit (`specs/<item>`): `specify`, `clarify`, `plan`, `tasks`, `analyze` (no CRITICAL or HIGH finding), `checklist`, `implement`.
- superpowers: `brainstorming`, `writing-plans`, `executing-plans`, `verification-before-completion`.
- OpenSpec (`openspec/changes/<item>`): `proposal`, `specs`, `tasks`, `validate`, `apply`, `archive`.

`bin/wuwei plan set <item> spec=skipped --reason <why>` skips the spec for one item, and `spec=required` requires it. `doctor` fails a repository whose engine is missing and prints its install line.

A Claude Code subagent cannot write `analysis.md` itself. The builder saves the analyze report with `bin/wuwei build analysis <item>`, from stdin or `--file`. An item with a governing document needs a `## Governing` table at the end of that report.

## Host, build and memory

| Key | Default | Meaning |
| --- | --- | --- |
| `host.free_memory_mb` | `1024` | Free memory floor in MiB. |
| `host.seats` | `0` | Total seat ceiling, builders and gates. `0` means one per core. |
| `host.reservation_timeout_seconds` | `14400` | Age at which a seat reservation is reported stale. |
| `host.rate_limit_wait_seconds` | `120` | Longest wait for a GitHub rate limit before one retry. `0` never waits. Doctor never waits. |
| `budget.claude.five_hour`, `budget.claude.seven_day` | `0` | Input plus output tokens Claude Code may spend in its 5-hour and 7-day usage windows. With the measured per-seat cost they bound how many Claude seats start. `0` is no budget. |
| `budget.codex.five_hour`, `budget.codex.seven_day` | `0` | The same for Codex. |
| `memory.budget_tokens` | `6000` | SessionStart memory payload budget. Today's lines go first. |
| `memory.export_to` | `"CLAUDE.md"` | Workspace file that receives the generated rules block. Never under `.wuwei/`. |
| `retro.charter_paths` | `[".wuwei/charters"]` | Charter paths the retro reviews. |
| `retro.changelog` | `".wuwei/memory/CHANGELOG.md"` | Retro change log. |
| `metrics.transcripts` | `"~/.claude/projects"` | Claude Code transcripts, filtered to this workspace, for attended time. |
| `metrics.band_margin` | `0.2` | FIX-rate lead an hour band needs before the retro names it. |
| `build.max_iterations` | `8` | Maximum build iterations. |
| `build.stuck_after` | `3` | Repeated progress limit. |
| `build.poll_interval_seconds` | `5` | Runtime job poll interval. |
| `build.poll_timeout_seconds` | `3600` | Runtime job poll timeout. |
| `codex.command` | `[]` | Companion command for the Codex runtime. |
| `codex.timeout_seconds` | `300` | Codex command timeout. |
| `gates.second_opinion` | `"off"` | `"<runtime>:<model>"` runs one gate of every STANDARD and FULL item again on that model. A blocking finding from either blocks. |
| `gates.second_opinion_role` | `"quality"` | The gate it repeats: `arch`, `quality` or `security`. |
| `gates.max_rounds` | `2` | Fix rounds per item. At the cap, notes ship in the PR body and a blocking finding parks the item. |
| `gates.tier_max_rounds` | `{ light = 0, standard = 0, full = 0 }` | A round cap per tier. `0` uses `max_rounds`. |
| `gates.polish` | `"offer"` | After a pass with notes: `never`, `offer` one notes-only round, or `always`. |
| `pr.poll_seconds` | `120` | Age at which `wuwei next` refreshes its PR listing. |
| `pr.action_minutes` | `30` | Minutes to act on a measured PR finding before a warning. |
| `pr.review_window` | `120` | Minutes to await review before asking again. |
| `duties.on` | `["ping", "shepherd", "tracker", "summary"]` | Outward duties `wuwei next` lists until each is recorded, each while its channel is configured. Remove a name to turn it off. `wuwei close` waits on an open one. Record one with `bin/wuwei duty <item> <duty> --evidence <link>`, or `--skipped "<why>"`. |
| `shepherd.lead_login` | `""` | Lead's code host login, a reviewer when not the author. |
| `shepherd.reviewers` | `[]` | Logins requested instead of the history ranking and the lead. |
| `shepherd.reviewers_exclude` | `[]` | Logins never picked from history. |
| `shepherd.review_channel` | `""` | Chat channel ID for review requests. |
| `shepherd.review_gate_check` | `"Review Gate"` | Check left out while requesting review. |
| `shepherd.min_reviewers` | `1` | Minimum eligible reviewers. `0` is a solo owner who merges without one. |
| `shepherd.author_windows_days` | `[90, 180]` | Authorship lookback windows before all history. |
| `shepherd.tie_commits` | `2` | A third author within this many commits of second place is added. |
| `shepherd.source_exclude` | specs, lock and generated files | Paths left out of reviewer selection. |
| `shepherd.authors` | `{}` | Author email to `{login, mention}`. An unmapped email is resolved through the code host. |

Usage windows: a seat launch on a runtime whose window has no room for another seat waits for
the window's reset, and running seats finish. When every launch waits, `wuwei next` returns a
background `sleep` until just after the reset, then offers them again. A window counts the
runtime's measured `seat.usage` tokens, and the runtime's own reading when there is one: Claude
Code's status line input (`wuwei status --line`) and the Codex seat's session file. A reading of
100 percent holds launches even with no budget; below that a budget is needed. A budget holds
launches early only once seat tokens are measured: with no measured seats (Codex seats today)
it holds them only at a 100 percent reading. A builder seat
policy row may name an `alternate` runtime: a new build starts there when its own runtime's
window is spent and the alternate's is not.

## Telemetry

Weekly usage counts that say whether WUWEI itself works. `bin/wuwei report` aggregates them at most once a day into `.wuwei/metrics/<week>.json`. `bin/wuwei report --week [<week>]` prints a week.

| Key | Default | Meaning |
| --- | --- | --- |
| `telemetry.enabled` | `true` | `false` stops the aggregate, sharing and the OpenTelemetry export. |
| `telemetry.share` | `""` | `anonymous`, `attributed` or `off`. Empty sends nothing, and `doctor` lists it as pending. |
| `telemetry.endpoint` | `""` | Where anonymous mode posts. Empty or not `https://` keeps every week local. |
| `telemetry.repository` | `"taoq-ai/wuwei"` | Where attributed mode opens issues with `bin/wuwei telemetry send`. |
| `telemetry.otlp.endpoint` | `""` | An `https://` OTLP/HTTP base URL on your own platform. |
| `telemetry.otlp.headers_env` | `""` | Name of the `.wuwei/env` variable holding the auth headers. |

With `telemetry.otlp.endpoint` set, each report run posts the new records as traces and each finished week as metrics. It never carries command text, reasons or record bodies. A failure records `telemetry.unsent`, and the next run resends.

## Adapters and brief

| Key | Default | Meaning |
| --- | --- | --- |
| `adapters.tracker` | `"none"` | `none`, `linear`, `jira` or `github`. |
| `adapters.chat` | `"none"` | `none` or `slack`. |
| `adapters.review_bot` | `"none"` | `none` or `greptile`. |
| `adapters.runtime` | `"claude"` | Seat runtime: `claude`, `codex` or `none`. |
| `adapters.scanner` | `"none"` | `none` or `ziran`. |
| `adapters.code_host` | `"github"` | `github` or `none`. |
| `adapters.vcs` | `"git"` | Version control. |
| `adapters.host` | `"local"` | Host measurement: `local` or `none`. |
| `adapters.checks` | `"local"` | Fast check runner: `local` or `none`. |
| `adapters.transcripts` | `"none"` | Meeting transcript port. Only telemetry reads it. |
| `scanner.severity_threshold` | `"high"` | Blocking threshold: `critical`, `high`, `medium` or `low`. |
| `scanner.mcp.plugins_file` | `"~/.claude/plugins/installed_plugins.json"` | Claude Code's plugin registry, read to find WUWEI and the spec engine. |
| `brief.remote` | `"origin"` | Git remote a brief and `worktree add` fetch from. |
| `brief.prior_branch_pattern` | `"*{item}*"` | Branch match, with the item lowercased. |
| `brief.full_path_patterns` | `[]` | Your regexes for paths that need full context. |
| `chat.identity` | `"connector"` | Slack identity: `connector` or `custom_app`. Not in the template. |

The security sentinel runs the ZIRAN scanner on an item flagged `agent_surface`. ZIRAN 0.39.0 or newer is required. Each finding becomes a verdict row and a `scanner.finding` event. A finding at or above the threshold blocks, and so does a trust-boundary finding. A missing tool, a timeout or a malformed report is unmeasured (exit 2).

`.wuwei/env` holds adapter credentials as `KEY=value` lines, mode `0600` and Git-ignored. Process environment values win. `config check` reports each credential as set, missing or malformed, never its value. See [adapter credentials](adapters.md#credentials).

`config check` also reads each repository's branch protection and the seat-readable tokens. Each line is `ok`, `missing` with the setting to change, or `unmeasured`. It exits 0 when all are ok, 1 on a missing line or a write-scoped `GH_TOKEN` or `GITHUB_TOKEN`, and 2 when any is unmeasured.

## Boundaries and deployment

| Key | Default | Meaning |
| --- | --- | --- |
| `boundary.api` | Not set | Example boundary. `[boundary]` maps names to descriptions. |
| `environments.production` | Not set | Example environment. `[environments]` maps names to descriptions. |
| `deploy.workflows` | `[]` | Workflow names, files, paths or IDs that deploy. |
| `deploy.deny` | `[]` | Executable plus argument globs to refuse. |
| `merge.owner_paths` | `[]` | Globs only you merge. `bin/wuwei merge <pr>` merges a match only on your Yes on its card. |

WUWEI does not deploy on its own. A deploy runs only on your Yes on its Owner step card ([owner-only actions](concepts.md#owner-only-actions)).

## Calibration

`bin/wuwei config promote` surveys every configured repository and proposes config. It prints the diff, asks its Owner step card and writes `config.toml` and `.wuwei/calibration.json` on your Yes. Run it after `init` and the `[[repos]]` entries, before the first plan. It exits 0 when applied or nothing changed, 1 without your Yes, and 2 when it could not run.

| Detector | Reads | Proposes |
| --- | --- | --- |
| Toolchain | `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile` and similar, or a single-line CI step | `repos.fast_checks` |
| CI checks | `.github/workflows/*.yml` run on `pull_request` | `repos.review_required_checks` |
| Conventions | `CODEOWNERS` and contributor docs | `[boundary]` candidates |
| Deploy signals | deploying workflows, targets and infrastructure directories | `deploy.workflows`, `[environments]`, `deploy.deny`, `repos.merge_deploys = true`, `repos.merge.never_auto_paths` |

The proposal only adds. A key you already set is never changed; the digest lists it under "Config differs". Calibration never proposes `merge_deploys = false` or `merge.auto`.

A test runner is CI only unless measured. `config promote --measure` runs each detected test runner once in the checkout. It is a fast check when it exits 0 within `calibrate.fast_check_seconds` (default 60). An empty `fast_checks` is a state, not an error: CI and the gates are the evidence.

Repository text is data. A file with instruction-like text contributes nothing, and the digest flags it without quoting it. At close the steward compares the checkouts with `.wuwei/calibration.json` and records `calibration.drift`. Run `config promote` again to approve the new state.

Two commands change one value, each with a diff and its card:

- `bin/wuwei config set <dotted.key> <toml-value>`, for example `config set repos.0.merge_deploys false`. The value is parse-checked first. `--add` adds items to a list or entries to a table instead of replacing it.
- `bin/wuwei config add-repo --name <owner/repo> --path <dir> --branch <branch> --identity "<Name> <email>"` appends one `[[repos]]` table.

## Outward sends

| Key | Default | Meaning |
| --- | --- | --- |
| `outward.allow` | `[]` | Exact MCP tool names that may send to other people. A write through any other tool is refused, whatever `guards.enforce` says. The refusal names `bin/wuwei config set outward.allow '["<tool>"]' --add`. |
| `outward.banned_characters` | `emoji` and long dashes | Characters the lint refuses. A list replaces the defaults. |
| `outward.tool_patterns` | Slack, Linear, GitHub, Notion and Atlassian | Tool regex plus lint channel. They choose the lint, never allow a send. |
| `outward.servers` | `{}` | MCP server id to its lint channel, or `local` for a server that acts only on your machine. |
| `outward.max_length.slack` | Not set | Example length limit for one channel. |
| `outward.humanize` | `true` | Lint outward text for AI tells. |
| `outward.humanize_kinds` | `["dm", "tracker", "docs", "pr", "review"]` | Kinds the lint checks. |
| `outward.humanize_strict` | `false` | `true` refuses a text with a tell; `false` warns. |
| `outbound.code_host_orgs` | `[]` | Your code host organizations. A GitHub tracker outside them gets no labels. |
| `outbound.owner` | all empty | Your identity per surface: Slack user and DM, mail, page ids and code host login. |
| `outbound.owner_channel` | `"session"` | `session` or `dm`. With `dm` the planner also posts the day report to your Slack DM. |

WUWEI's own outward duties go through its adapter ports and need no `outward.allow` entry. Each still passes the outward lint.

## Your own surfaces

A write whose every destination is yours is local, never an outward send. It needs no `outward.allow`, and it records an `outward.to_owner` event. Destinations are values under `channel`, `recipient`, `to`, `cc`, `bcc`, `page_id`, `canvas_id` and similar keys, at any depth.

| Surface | Your config | Matches |
| --- | --- | --- |
| Slack self-DM | `outbound.owner.slack.dm`, `outbound.owner.slack.user` | a message to one of them |
| Slack canvas | `outbound.owner.pages` | a write to your canvas id |
| Notion or Confluence page | `outbound.owner.pages` | an update of your page, or a create under it |
| Mail to yourself | `outbound.owner.mail` | every recipient is you |

A call with no destination is never yours. A code host comment is never local, since others read it.

## Goals and discovery

`.wuwei/memory/goals.md` is protected; agent tools cannot write it. A goals change goes through the plan. The lead writes goal blocks in its JSON, each with `id`, `outcome`, `measure`, `target`, an ISO `date` and a positive `priority`. `plan propose` shows them on the morning gate card. The gate's Yes runs `plan approve --goals-confirmed`, which writes and commits them. Ids alone keep the recorded goals.

The lead brief carries the discovered candidates and their sources, and `plan propose` records the discovery. Each candidate names a goal or `unplanned` and a score, and the framework orders them. After the gate, add an item with `bin/wuwei plan add <item> --goal G-n`.

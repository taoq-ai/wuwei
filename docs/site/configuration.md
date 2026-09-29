---
layout: default
---

# Configuration

[Home](index.html)

`bin/wuwei init .` creates `.wuwei/config.toml`. Edit it in the workspace root. Values below are the shipped template defaults. Omitted keys use CLI defaults, and unknown keys are errors. The optional commented examples are inactive until uncommented. Paths in repository entries are relative to the workspace unless absolute.

## Workspace and repositories

| Key | Default | Meaning |
| --- | --- | --- |
| `cap` | `1` | Maximum running build seats. |
| `prioritisation.framework` | `"wsjf"` | Ranking formula: `wsjf` or `rice`. |
| `discovery.min_queue` | `2` | Discover again when a seat frees and the queue is below this count. |
| `discovery.autostart` | `"strict"` | Intraday start policy: `off` carries safe items to the next morning; `strict` admits confirmed-goal SLICE items above the approved queue cut; `goal` admits confirmed-goal SLICE items under CAP and budget. Unsafe or over-budget items go to the owner. |
| `tracker.backlog_filter` | `""` | Optional Linear team ID for backlog discovery. Empty reads accessible issues. |
| `tracker.states.in_review` | `"In Review"` | Linear workflow state name after a PR is raised. |
| `tracker.states.done` | `"Done"` | Linear workflow state name after a confirmed merge. |
| `profile` | `"strict"` | Guard profile: `strict` or `standard`. Standard warns for outward text lint. |
| `security.required` | `true` | When true, a missing `.wuwei/security.json` makes guards fail closed instead of treating security as disabled. |
| `repos` | `[]` | Configured repositories. Each `[[repos]]` entry has the fields below. |
| `repos.name` | Required per entry | Code host name, such as `owner/repo`. |
| `repos.path` | Required per entry | Repository path from workspace root or absolute path. |
| `repos.default_branch` | Required per entry | Protected base branch. |
| `repos.identity` | `{name = "", email = ""}` | Expected git identity for this repository. Set both values. |
| `repos.merge_deploys` | `true` when omitted | Whether a merge deploys. Template example sets `false` only after explicit confirmation. |
| `repos.merge.auto` | `false` | Allow automatic merge only when the merge policy's review, check, soak, path and budget rules pass. |
| `repos.fast_checks` | `[]` | Commands for `wuwei fast-checks` on this checkout. |
| `owner.name` | `""` | Name used by outward text checks. |
| `owner.pronouns` | `""` | Owner pronouns for outward text checks. |
| `owner.handles` | `[]` | Bare chat IDs and code host handles. |

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

## Host, build and memory

| Key | Default | Meaning |
| --- | --- | --- |
| `host.free_memory_mb` | `1024` | Nonnegative free memory floor in MiB. |
| `host.seats` | `4` | Total seat ceiling: default cap plus three parallel gates. Increase with custom cap; refusals name `host.seats`. |
| `host.reservation_timeout_seconds` | `14400` | Age at which a reservation is reported stale. |
| `memory.max_notes` | `60` | Index note limit. |
| `memory.note_line_cap` | `80` | Maximum lines in a note. |
| `memory.probation_days` | `10` | Working days before a note or rule can be archived for nonuse. |
| `memory.state_entry_cap` | `3` | State entries included in memory payload. |
| `retro.repo` | `"."` | Repository used for retro evidence. |
| `retro.charter_paths` | `[".wuwei/charters"]` | Paths to charter procedures reviewed during retro. |
| `retro.changelog` | `".wuwei/memory/CHANGELOG.md"` | Retro change log path. |
| `metrics.transcripts` | `"~/.claude/projects"` | Claude Code project transcript directory for attended time. Sessions are filtered to the workspace and its repositories. |
| `consolidation.archive_after_days` | `30` | Move older day directories into the archive. |
| `consolidation.similarity_threshold` | `0.85` | Text similarity ratio for near-duplicate review. |
| `build.max_iterations` | `8` | Maximum build iterations. |
| `build.stuck_after` | `3` | Repeated progress limit. |
| `build.poll_interval_seconds` | `5` | Runtime job poll interval. |
| `build.poll_timeout_seconds` | `3600` | Runtime job poll timeout. |
| `codex.command` | `[]` | Companion command; fill in to use Codex runtime. |
| `codex.timeout_seconds` | `300` | Codex command timeout. |
| `pr.poll_seconds` | `120` | Interval between polls of raised and claimed PRs. |
| `pr.action_minutes` | `30` | Positive minutes to act on a measured PR finding. Nudge after this deadline, page at twice the interval. |
| `pr.review_window` | `120` | Positive minutes to await review before re-requesting it. Starts at first observation of the head; comments do not reset it. |
| `shepherd.lead_login` | `""` | Lead code host login. Counts as a reviewer when different from the author. |
| `shepherd.review_channel` | `""` | Chat channel ID for review requests. |
| `shepherd.review_gate_check` | `"Review Gate"` | Check excluded during review requests. |
| `shepherd.min_reviewers` | `1` | Minimum eligible reviewers required to raise or request review. |
| `shepherd.author_windows_days` | `[90, 180]` | Authorship lookback windows, then all history. |
| `shepherd.tie_commits` | `2` | Include a third author within this many commits of second place. |
| `shepherd.source_exclude` | `specs/*`, lock files and generated files | Changed paths excluded from reviewer selection. |
| `shepherd.authors` | `{}` | Map author email to verified `{login, mention}` reviewer identity. |
| `watch.clock_seconds` | `600` | Interval between watch clock events. |
| `watch.dead_seconds` | `1200` | Clock age after which the watch is reported dead. |
| `watch.stale_seconds` | `900` | Inactivity age at which running work is reported stale. |
| `watch.sweep_seconds` | `7200` | Interval between supervision sweeps. |
| `steward.every_tool_calls` | `50` | Completed tool calls between steward reviews. |

## Adapters and brief

| Key | Default | Meaning |
| --- | --- | --- |
| `adapters.tracker` | `"none"` | Tracker implementation: none or linear. |
| `adapters.chat` | `"none"` | Chat implementation: none or slack. |
| `adapters.review_bot` | `"none"` | Review bot: none or greptile. |
| `adapters.runtime` | `"claude"` | Seat runtime: claude, codex or none. |
| `adapters.scanner` | `"none"` | Scanner: none or ziran. S4 requires the compatible JSON CLI described below. |
| `scanner.severity_threshold` | `"high"` | Blocking threshold: critical, high, medium or low. Trust-boundary findings always block. |
| `adapters.code_host` | `"github"` | Code host: github or none. |
| `adapters.vcs` | `"git"` | Version control: git. |
| `adapters.host` | `"local"` | Host measurement: local or none. |
| `adapters.checks` | `"local"` | Fast check execution: local or none. |
| `adapters.tts` | `"say"` on macOS, `"none"` elsewhere | Speech output for owner packs. `none` writes a text pack with an explicit no-audio note. |
| `adapters.calendar` | `"none"` | Meeting source: none or a private ICS feed. |
| `adapters.transcripts` | `"none"` | Meeting transcript source. |
| `calendar.url` | `""` | Private HTTPS ICS URL. `WUWEI_CALENDAR_URL` overrides this setting. Keep the URL secret. |
| `brief.lead_minutes` | `30` | Meeting pack window before an event with attendees. |
| `brief.style.length` | `"standard"` | `standard` or `concise` pack text. |
| `brief.style.speed` | `180` | Speech rate in words per minute for `say`. |
| `brief.remote` | `"origin"` | Git remote used for a brief. |
| `brief.prior_branch_pattern` | `"*{item}*"` | Branch match, with lowercased item substituted. |
| `brief.full_path_patterns` | `[]` | Owner supplied regexes for paths needing full context. |
| `chat.identity` | `"connector"` | Optional CLI default: connector or custom_app. This key is not in the template. |

Run `bin/wuwei brief pack` once for a daily text pack, or `bin/wuwei brief pack --meeting`
inside the lead window for the next attendee meeting. The returned path contains the
five fixed sections, a what-changed visual, a three-bullet card and a three-question
drill. Answer with `bin/wuwei brief answer 1 "your answer"`; the command prints feedback
and records the score and streak. The existing `bin/wuwei brief ROLE ITEM NAME` command
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
uses a stable digest to keep different sessions distinct. MCP scanning (#35) and role
audits (#36) remain deferred.

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

The template also shows a `"release/*"` environment example. Add any actual environment register entries before using rules that depend on them. WUWEI does not deploy.

## Outward text and outbound tiers

| Key | Default | Meaning |
| --- | --- | --- |
| `outward.patterns` | Built-in internal-state patterns | Regexes; setting a list replaces defaults, `[]` disables them. |
| `outward.banned_characters` | `emoji`, U+2014, U+2015, U+2E3A, U+2E3B | Setting a list replaces defaults. |
| `outward.tool_patterns` | Built-in Slack, Linear and GitHub MCP matches | Tool regex plus policy channel; setting a list replaces defaults. |
| `outward.max_length.slack` | Not set | Example positive maximum for one channel under `[outward.max_length]`. |
| `outbound.work_channels` | `[]` | Internal channel IDs eligible for routine auto-send. |
| `outbound.external_channels` | `[]` | Shared or client channels; these override work channels. |
| `outbound.company_domains` | `[]` | Exact internal domain names. |
| `outbound.code_host_orgs` | `[]` | Internal code host organizations. |
| `outbound.people` | `{}` | Optional identity map using `slack:`, `github:` or `email:` keys. |
| `outbound.sensitive_keywords` | Built-in sensitive topic words | Optional replacement list; see the template for the full list. |
| `outbound.sensitive_patterns` | `['\\bmental\\s+health\\b']` | Optional replacement regex list. |
| `outbound.commitment_patterns` | Built-in commitment regexes | Optional replacement list; see the template for exact regexes. |
| `outbound.disagreement_patterns` | Built-in disagreement regexes | Optional replacement list; see the template for exact regexes. |

Unknown destinations and direct messages draft by default. A channel allowlist is a ceiling; it does not bypass outward text checks. The shipped [template](https://github.com/taoq-ai/wuwei/blob/main/templates/workspace/config.toml) contains the exact regex defaults and examples.

## Goals and discovery

Before the morning plan, the owner runs `bin/wuwei goals edit` to open `$EDITOR`, or `bin/wuwei goals edit --file goals.md` to use a prepared file. The command validates and commits the change in `.wuwei` history with `Promoted-by: wuwei` and `Edited-by: owner`, so SessionStart does not flag it as an unpromoted edit. Seats cannot use this owner action. Each `## G-n` block needs `outcome`, `measure`, `target`, `date` in ISO format, and a positive integer `priority`. Priority 1 wins score ties. `wuwei rank candidates.json` reads JSON candidates with a goal or `unplanned` mark, a `score` object, and one `evidence_lines` entry per score component. `wuwei discover` reports unavailable sources as `unmeasured`.

The owner uses `bin/wuwei voice edit` or `bin/wuwei voice edit --file voice.md` for the same validated history flow. Seat proposals still go through `wuwei promote`.

After the morning gate, sweeps and qualifying seat-free events save new discovery candidates. Run `bin/wuwei plan add <item>` to apply the same admission gate to one saved candidate. A started item enters the existing `build next` path when a builder brief and worktree are logged; otherwise a build request remains visible for the planner. Owner proposals appear in the steward decision batch. The morning plan shows safe `off` mode candidates carried from the prior day.


### MCP registry checks (S3)

`wuwei init` and `wuwei init --upgrade` discover attached MCP configurations and
register them through `scanner.mcp`. Set `adapters.scanner = "ziran"` to use ZIRAN
0.39.0 or newer. Missing tools or the `none` adapter are unmeasured when servers
are attached. No attached servers is a clean empty registry.

`scanner.mcp.project_file` defaults to `.mcp.json` in the workspace and each
configured repo. `scanner.mcp.plugins_file` defaults to
`~/.claude/plugins/installed_plugins.json`; registry v2 user installations and
project/local installations matching those repos contribute their `.mcp.json`.
`scanner.mcp.user_file` defaults to `~/.claude.json` with top-level `mcpServers`.
Relative overrides resolve against the workspace. Missing default user/plugin
files and absent project/plugin MCP files are optional; explicit user/plugin
file overrides must exist. Invalid or unreadable input is exit 2.

The scanner receives file paths only, once per config. It keeps independent
snapshots under `.wuwei/ziran/snapshots` and untrusted raw reports under
`.wuwei/ziran/report-*/registry-watch-report.json`. An incomplete measurement
restores the prior snapshots so retries cannot silently accept drift. Events
contain server name, drift type, severity and tool name only.

Run `bin/wuwei mcp check` before the first morning seat. The plan skill does this
before the lead, and `bin/wuwei plan propose` checks again. High/critical findings
return 1 and open an owner decision. Exit 2 means unmeasured and blocks launches
until a successful recheck. Medium/low findings remain visible and return 0.
Agent and runtime launches refuse stale or missing measurements and open flags.

An owner reviews every linked report, sets `Decided-by: owner` and
`Outcome: proceed` in the queued decision and runs `bin/wuwei mcp decide` from a
host terminal, typing the displayed digest. Agent tools cannot invoke this owner
command. A decision file or forged event alone never clears a flag. Confirmation
cannot excuse exit 2. Pending findings and report references survive rechecks
and day rollover. The host terminal follows the local friction boundary in
threat model 9.1; remote authenticated decisions remain M5 work.

## Running the watch

Run `bin/wuwei watch install` inside an initialized workspace to install and start a
user service. On macOS this creates a launchd agent; on Linux it creates a systemd
user unit. The service uses the active workspace and current `PATH`. Run
`bin/wuwei watch uninstall` to stop and remove it. `bin/wuwei watch --once` runs
one due cycle without installing a service. The watch writes clock events at
`watch.clock_seconds` intervals, and the next sweep reports a dead watch when the
latest clock is older than `watch.dead_seconds`.

Run `bin/wuwei nudges` to list current nudges and pages with their sources. Its
entry count matches the page and nudge counts in `bin/wuwei status --line`.

## Private workspace environment

`.wuwei/env` stores adapter credentials outside tracked configuration. Init and
upgrade create it empty with mode `0600` and add its Git ignore rule. Existing
contents are preserved by upgrade. Use literal `KEY=value` lines; process
environment values take precedence. The CLI, scoped hooks and watch all load the
file before adapter calls. Restart a running watch after editing the file.

`wuwei config check` reports credential names and set/missing status per effective
adapter. It returns 1 for missing requirements and 2 when a check cannot run.
See [adapter credentials](adapters.html#credentials) for every variable, syntax
rules and authentication requirements. No new config.toml keys are needed.

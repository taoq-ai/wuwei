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
| `discovery.autostart` | `"strict"` | Intraday start policy: `off`, `strict` or `goal`. Safety and budget checks always send the item to the owner. |
| `profile` | `"strict"` | Guard profile: `strict` or `standard`. Standard warns for outward text lint. |
| `security.required` | `true` | When true, a missing `.wuwei/security.json` makes guards fail closed instead of treating security as disabled. |
| `repos` | `[]` | Configured repositories. Each `[[repos]]` entry has the fields below. |
| `repos.name` | Required per entry | Code host name, such as `owner/repo`. |
| `repos.path` | Required per entry | Repository path from workspace root or absolute path. |
| `repos.default_branch` | Required per entry | Protected base branch. |
| `repos.identity` | `{name = "", email = ""}` | Expected git identity for this repository. Set both values. |
| `repos.merge_deploys` | `true` when omitted | Whether a merge deploys. Template example sets `false` only after explicit confirmation. |
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
| `host.seats` | `1` | Host seat count. |
| `host.reservation_timeout_seconds` | `14400` | Age at which a reservation is reported stale. |
| `memory.max_notes` | `60` | Index note limit. |
| `memory.note_line_cap` | `80` | Maximum lines in a note. |
| `memory.probation_days` | `10` | Working days before a note or rule can be archived for nonuse. |
| `memory.state_entry_cap` | `3` | State entries included in memory payload. |
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
| `watch.clock_seconds` | `600` | Interval between watch clock events. |
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

The adapter requires `ziran audit PATH --format json` with an AnalysisReport body
(`files_analyzed` greater than zero and a `findings` list), followed by
`ziran ci REPORT --severity-threshold LEVEL --format json` with a boolean `passed` field.
Finding fields are `check_id`, `severity`, `file_path`, `line_number` and `message`;
`trust_boundary` is an optional boolean. Each command has a 60-second timeout.

The available upstream console-only audit and campaign CI interface do not yet meet
this contract. A compatible upstream release is required for live use. `none`, missing
or incompatible ZIRAN, command errors, invalid bodies and timeouts report unmeasured
(exit 2) and leave the gate unreceived. CI exit 1 counts as findings only when its body
and the validated audit agree. Trace scanning (#34) and MCP audit (#35) remain deferred.

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

The owner edits `.wuwei/memory/goals.md` before the morning plan. Each `## G-n` block needs `outcome`, `measure`, `target`, `date` in ISO format, and a positive integer `priority`. Priority 1 wins score ties. `wuwei rank candidates.json` reads JSON candidates with a goal or `unplanned` mark, a `score` object, and one `evidence_lines` entry per score component. `wuwei discover` reports unavailable sources as `unmeasured`.

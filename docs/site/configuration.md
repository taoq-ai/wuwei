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
| `profile` | `"strict"` | Guard profile: `strict` or `standard`. Standard warns for outward text lint. |
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
| `build.max_iterations` | `8` | Maximum build iterations. |
| `build.stuck_after` | `3` | Repeated progress limit. |
| `build.poll_interval_seconds` | `5` | Runtime job poll interval. |
| `build.poll_timeout_seconds` | `3600` | Runtime job poll timeout. |
| `codex.command` | `[]` | Companion command; fill in to use Codex runtime. |
| `codex.timeout_seconds` | `300` | Codex command timeout. |

## Adapters and brief

| Key | Default | Meaning |
| --- | --- | --- |
| `adapters.tracker` | `"none"` | Tracker implementation: none or linear. |
| `adapters.chat` | `"none"` | Chat implementation: none or slack. |
| `adapters.review_bot` | `"none"` | Review bot: none or greptile. |
| `adapters.runtime` | `"claude"` | Seat runtime: claude, codex or none. |
| `adapters.scanner` | `"none"` | Scanner: only none is shipped; ZIRAN is planned. |
| `adapters.code_host` | `"github"` | Code host: github or none. |
| `adapters.vcs` | `"git"` | Version control: git. |
| `adapters.host` | `"local"` | Host measurement: local or none. |
| `adapters.checks` | `"local"` | Fast check execution: local or none. |
| `brief.remote` | `"origin"` | Git remote used for a brief. |
| `brief.prior_branch_pattern` | `"*{item}*"` | Branch match, with lowercased item substituted. |
| `brief.full_path_patterns` | `[]` | Owner supplied regexes for paths needing full context. |
| `chat.identity` | `"connector"` | Optional CLI default: connector or custom_app. This key is not in the template. |

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

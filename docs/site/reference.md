# Reference

## Commands

| Command | What it does |
| --- | --- |
| `wuwei init [dir] [--cloud]` | Create `.wuwei/` and merge WUWEI's allow, deny and ask rules into `.claude/settings.json`; `--cloud` also copies the plugin into `.claude/` for cloud sessions; `--codex` writes the role agents and door rules into `.codex/` |
| `wuwei sent owner/repo#n <link>` | Record a review request posted outside the session |
| `wuwei sync` | Pull, then push `.wuwei/` on the `wuwei/state` branch |
| `wuwei doctor` | Install, workspace, ledger, harness rules, and each door's strength per repository |
| `wuwei plan [show] [<id>]` | The ranked plan; `--json` for machines; with an id, that item as JSON (promise and acceptance included) |
| `wuwei plan add <id> "<title>" --goal G-n --repo owner/name --tier light\|standard\|full` | Add an item with `--value --time --risk --size` (WSJF) or `--reach --impact --confidence --effort` (RICE) and `--why`, `--promise`, one `--accept` per scenario, and `--pr owner/repo#n` to link a PR whose body has no WUWEI footer (a taken-over PR; the board otherwise says `PR owner/repo#n not linked`); an id already in the plan is updated in place, and a changed promise or acceptance clears its approval |
| `wuwei plan add --from <file>` | Add the lead's candidates (`.wuwei/candidates.json`): a list, or `{"candidates": [...]}`, each with an `id` and a `title`; any other shape is refused and nothing is added |
| `wuwei plan restore <id>` | Reopen a parked or dropped item |
| `wuwei plan park\|drop\|done <id> --reason "..."` | Change an item's status |
| `wuwei plan run <id> --reason "<what ran, what it showed>"` | Record run evidence for an operations item; refused without `--reason` |
| `wuwei plan pass --reason "..."` | Record a plan pass; reopens a closed day |
| `wuwei plan view [--html]` | The plan as a view: writes `.wuwei/plan.html`, prints a summary and the question line (`--html` prints the page) |
| `wuwei status [--json]` | The board: what each open item lacks |
| `wuwei evidence owner/repo#n [--json] [--record DIR]` | One PR's gaps; exit 1 when there are gaps |
| `wuwei report [--day YYYY-MM-DD]` | The day report |
| `wuwei report --dora [--window 28]` | The DORA keys per repository |
| `wuwei close` | Checkpoint: write the report for the day so far |
| `wuwei andon owner/repo --reason "..."` / `--clear` | Pull or clear the cord on one repository |
| `wuwei owe <thread link> "<what>" --who <name> [--within 4h \| --due <ISO>]` | Record a reply someone is waiting for |
| `wuwei watch [--record "<summary>"]` | The last watch pass and replies owed; record a pass |
| `wuwei status --all` | The board with process fit too (for the watch) |
| `wuwei config [key value]` | Show, or set one of the six keys |
| `wuwei verify` | Check the ledger's hash chain |
| `wuwei agents [check\|build]` | Check or build the role agents from the charters |
| `wuwei --version` | The plugin version |
| `wuwei hook <event>` | Called by the harness only |

## Configuration

`.wuwei/config.toml` has six keys. Everything else is discovered or part of the process.

| Key | Default | Meaning |
| --- | --- | --- |
| `repos` | the origin of the init directory | the repositories in the workspace |
| `owner_paths` | `[]` | glob patterns you review yourself |
| `prioritisation` | `wsjf` | `wsjf` or `rice` |
| `tracker` | `github` | where issues live |
| `telemetry` | `true` | local tool-call traces |
| `models` | `{}` | your rows over the [model table](concepts/models.md): `"<role>[ <tier>]" = "<model> <effort>"`; set with `wuwei config models "builder light=opus medium"` |

## Files

| Path | Holds |
| --- | --- |
| `.wuwei/plan.json` | the running queue |
| `.wuwei/goals.md` | the goals, the direction |
| `.wuwei/plan.html` | the plan view you approve |
| `.wuwei/standards.md` | rules the retro promoted, per role; a `Review requests: <where>` line names where reviews are asked |
| `.wuwei/verdicts/<item>/` | the sentinels' verdict files |
| `.wuwei/ledger/<clone>.jsonl` | the hash-chained record, one file per clone |
| `.wuwei/.gitignore` | keeps the state out of working branches; it travels on `wuwei/state` |
| `.wuwei/traces.jsonl` | local telemetry |
| `.wuwei/days/<date>/report.md` | each checkpoint's report |
| `.wuwei/retro/<date>.md` | the steward's retro |
| `.wuwei/canary` | the workspace canary token |

## PR body lines

| Line | When |
| --- | --- |
| `` <sub>[WUWEI <version>](https://taoq-ai.github.io/wuwei/) · Item `<id>` · <title> · Goal <G-n> · Tier <tier></sub> `` | always, last line; the older `WUWEI-Item: <id>` still links, with a process-fit line naming the footer |
| `No test: <reason>` | a change no test can hold |
| `Size: <reason>` | over about 400 changed lines |
| `Rollback: <how to undo>` | full tier, or `owner_paths` touched |
| `BREAKING CHANGE: <what>` (and `!` in the title) | a major only: an incompatible change to the public API, as [Breaking changes](concepts/evidence.md#breaking-changes) declares it; a stricter check of a rule the docs already state is a `fix:` (a patch) with release notes in the body |
| `Announcement: <url>` | a breaking change: one http(s) URL alone on the line, without brackets, of a communication that already exists (a PR or issue comment, or a published release note or migration guide); a changelog entry written at release does not count |

## Verdict format

```
Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>   (or <owner/repo> alone before its draft PR exists)
Head: <the 40-character sha you reviewed>
Confidence: low | medium | high
Breaking: no | yes: <what breaks for which clients>   (arch only)

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes. Failure: <the concrete scenario>
- [low] <file>:<line> blocks: no. <a note>   (the <file>:<line> is optional on a note)
(or none)
```

A blocking finding names its `<file>:<line>`; a note without a place in the code leaves it out. The
reviewer ends its report with `Verdict file: <path>`. A written verdict file is never edited: a
corrected or second verdict for the same head goes to the next free `<gate>-<sha7>-2.md`.

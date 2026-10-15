# Reference

## Commands

| Command | What it does |
| --- | --- |
| `wuwei init [dir]` | Create `.wuwei/` and merge WUWEI's allow, deny and ask rules into `.claude/settings.json` |
| `wuwei doctor` | Install, workspace, ledger, harness rules, and each door's strength per repository |
| `wuwei plan [show]` | The ranked plan; `--json` for machines |
| `wuwei plan add <id> "<title>" --goal G-n --repo owner/name --tier light\|standard\|full` | Add an item with `--value --time --risk --size` (WSJF) or `--reach --impact --confidence --effort` (RICE) and `--why` |
| `wuwei plan park\|drop\|done <id> --reason "..."` | Change an item's status |
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
| `wuwei config [key value]` | Show, or set one of the five keys |
| `wuwei verify` | Check the ledger's hash chain |
| `wuwei agents [check\|build]` | Check or build the role agents from the charters |
| `wuwei --version` | The plugin version |
| `wuwei hook <event>` | Called by the harness only |

## Configuration

`.wuwei/config.toml` has five keys. Everything else is discovered or part of the process.

| Key | Default | Meaning |
| --- | --- | --- |
| `repos` | the origin of the init directory | the repositories in the workspace |
| `owner_paths` | `[]` | glob patterns you review yourself |
| `prioritisation` | `wsjf` | `wsjf` or `rice` |
| `tracker` | `github` | where issues live |
| `telemetry` | `true` | local tool-call traces |

## Files

| Path | Holds |
| --- | --- |
| `.wuwei/plan.json` | the running queue |
| `.wuwei/goals.md` | the goals, the direction |
| `.wuwei/plan.html` | the plan view you approve |
| `.wuwei/standards.md` | rules the retro promoted, per role |
| `.wuwei/verdicts/<item>/` | the sentinels' verdict files |
| `.wuwei/ledger.jsonl` | the hash-chained record |
| `.wuwei/traces.jsonl` | local telemetry |
| `.wuwei/days/<date>/report.md` | each checkpoint's report |
| `.wuwei/retro/<date>.md` | the steward's retro |
| `.wuwei/canary` | the workspace canary token |

## PR body lines

| Line | When |
| --- | --- |
| `WUWEI-Item: <id>` | always |
| `No test: <reason>` | a change no test can hold |
| `Size: <reason>` | over about 400 changed lines |
| `Rollback: <how to undo>` | full tier, or `owner_paths` touched |
| `BREAKING CHANGE: <what>` (and `!` in the title) | a change that breaks an outward contract |
| `Announcement: <link>` | a breaking change: the client communication, release note or migration guide |

## Verdict format

```
Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>
Head: <the 40-character sha you reviewed>
Confidence: low | medium | high
Breaking: no | yes: <what breaks for which clients>   (arch only)

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes|no. Failure: <the concrete scenario>
(or none)
```

The reviewer ends its report with `Verdict file: <path>`.

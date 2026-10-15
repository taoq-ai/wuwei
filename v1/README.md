<h1 align="center">WUWEI 无为</h1>

<p align="center"><strong>A process auditor for agent teams.</strong></p>

<p align="center">无为 (wuwei, said woo-way) means "effortless action": work gets done without forcing it.</p>

## What WUWEI is

WUWEI is a Claude Code plugin. A chartered team of agents (planner, lead, builder, four
sentinels, shepherd, steward) works your plan across your repositories. WUWEI teaches the way at
the moment it matters, reads the evidence the work leaves behind, and holds the few doors that do
not reopen. It never tells the model which command to run, never wraps git or gh, and never stops
the work to prevent bad behaviour: the work goes on, and the report shows everything it did.

## How a day runs

- `/wuwei-plan` adds, drops or re-ranks items (WSJF or RICE) against your goals. Run it as often
  as the day needs: in the morning, when the queue runs dry, when you add or change work.
- Builders work items test first in parallel; the sentinels review each at its head; the
  shepherd takes PRs to merge.
- `/wuwei-close` checkpoints the day with the report and the steward's retro. Planning again
  reopens it.

You are asked only for what is yours: goals, work outside them, one-way doors, trust-boundary
questions, owner reviews and infrastructure. Every other question goes back to the model, which
records its assumption and carries on.

## Done means evidence

`bin/wuwei status` lists what each open item still lacks; `bin/wuwei evidence owner/repo#n` does
it for one PR. A PR is ready when it names its plan item (`WUWEI-Item: <id>`), carries a test, has
the gates its tier needs passing at its head, green CI, every thread answered, a reviewer, and
your review on `owner_paths`.

## The doors

WUWEI refuses a merge with gaps, force pushes, pushes to or deletion of the default branch, admin
bypasses and protection writes, secrets or the workspace canary in an outward call, edits to its
ledger, and questions to you that the process answers. Infrastructure commands ask you through
Claude Code's own prompt. Tool access is Claude Code's permission rules: allow a Slack or Linear
tool there, as you always would.

## Commands

| Command | What it does |
| --- | --- |
| `init` | Create `.wuwei/` and merge WUWEI's rules into `.claude/settings.json` |
| `plan` | `show`, `add`, `park`, `drop`, `done`, `pass` |
| `status` | The board: what each open item lacks |
| `evidence` | The gaps of one PR |
| `report` | The day report; `--dora` for the DORA keys |
| `close` | Checkpoint the day |
| `config` | Show, or set one of five keys |
| `doctor` | Install, workspace and the strength of each door per repository |
| `verify` | Check the ledger's hash chain |
| `agents` | Check or build the role agents from the charters |

## Install

You need Claude Code, Python 3.11 or newer, Git and `gh`. Register the plugin, then from the
project directory that owns the workspace:

```sh
bin/wuwei init
bin/wuwei doctor
```

Then open Claude Code there and run `/wuwei-plan`.

## Development

```sh
python3 -m pytest -q
```

See the [design](docs/design.md) and the [constitution](docs/constitution.md).

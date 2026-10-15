<p align="center"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/site/assets/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/site/assets/hero-light.svg">
    <img src="docs/site/assets/hero-light.svg" alt="Plan passes fill a ranked queue against your goals, an agent team works three parallel lanes, the gates review each item at its head, the shepherd follows the pull requests, and each merges when its evidence has no gaps. Only a one-way question reaches you." width="100%">
</picture></p>

<h1 align="center">WUWEI 无为</h1>

<p align="center"><strong>Responsible autonomy for agent teams.</strong></p>

<p align="center">Your agents plan, build, review and ship. WUWEI audits the evidence, holds the few
doors that do not reopen, and asks you only what is yours.</p>

<p align="center">
<a href="https://github.com/taoq-ai/wuwei/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/taoq-ai/wuwei/actions/workflows/tests.yml/badge.svg"></a>
<a href="https://github.com/taoq-ai/wuwei/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/taoq-ai/wuwei"></a>
<a href="LICENSE"><img alt="Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-blue"></a>
<img alt="Stdlib Python" src="https://img.shields.io/badge/runtime-stdlib%20Python%203.11%2B-informational">
</p>

<p align="center"><a href="https://taoq-ai.github.io/wuwei/">Documentation</a> · <a href="https://taoq-ai.github.io/wuwei/concepts/">Concepts</a> · <a href="docs/design.md">Design</a></p>

无为 (wuwei, said woo-way) means "effortless action": work gets done without forcing it.

## Why WUWEI

Agents are fast and tireless, and they take the shortest path. Left alone they skip the test,
merge the unreviewed change and ask you a dozen questions you should never have to answer.
Bolted-on process makes it worse: agents route around rules they cannot see the point of.

WUWEI takes the other road. It never tells the model which command to run. It reads what the
work produced and says what is missing, it teaches the standard at the moment it matters, and it
holds a short, closed list of doors that do not reopen. Everything else flows, and everything is
on the record.

- **Evidence, not ceremony.** A pull request is done when its evidence is: a linked plan item, a
  test, independent reviews at the head it merges, green CI, answered threads, a way to undo it.
- **An auditor with narrow police powers.** It refuses only what cannot be taken back: a merge
  with gaps, a force push, a protection bypass, a secret leaving the machine.
- **You decide what is yours.** One-way doors, scope and goals, trust boundaries. Every other
  question goes back to the model, which records its assumption and carries on.
- **It learns.** Each checkpoint's retro turns escaped defects into standards, retires rules that
  never catch anything, and proposes memory and skills for your repositories.

## A day with WUWEI

1. `/wuwei-plan` ranks work against your goals (WSJF or RICE) and shows you the plan as one
   picture: goals, items by score, estimated hours. You approve or change it. Plan again whenever
   the day changes: the queue runs dry, you add something, priorities shift.
2. Builders work items test first, in parallel lanes. Sentinels (architecture, quality, security,
   goal) review each one independently at its head. The shepherd takes PRs to merge.
3. WUWEI watches through the harness's hooks: it teaches before a PR opens, says what a new PR
   still lacks, refuses a merge with gaps, and reminds the team once when it tries to stop with
   work it can still close.
4. `/wuwei-close` checkpoints the day: the report, the steward's retro, a short summary sent where
   you read it. Planning again reopens the day.

## Install

You need Claude Code, Python 3.11 or newer, Git and `gh`. Add the plugin, then from the project
directory that owns the workspace:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

```sh
bin/wuwei init      # .wuwei/ and the harness permission rules
bin/wuwei doctor    # install, workspace, and how strongly each door holds per repository
```

Open Claude Code there and run `/wuwei-plan`.

## Commands

| Command | What it does |
| --- | --- |
| `status` | The board: what each open item still lacks |
| `evidence` | The gaps of one PR; `--record` saves it as a replay case |
| `plan` | `show`, `add`, `park`, `drop`, `done`, `pass` |
| `report` | The day report; `--dora` for the DORA keys |
| `close` | Checkpoint the day |
| `andon` | Pull or clear the cord on one repository |
| `init`, `doctor`, `config`, `verify`, `agents` | Set up, check, five config keys, the ledger chain, the role agents |

## Learn more

- [Concepts](https://taoq-ai.github.io/wuwei/concepts/): every idea in WUWEI and why it is there.
- [Design](docs/design.md) and [constitution](.specify/memory/constitution.md).
- [Security](SECURITY.md).

## Development

```sh
python3 -m pytest -q
```

WUWEI audits its own changes: every PR names `WUWEI-Item: <issue>` and passes its gates.

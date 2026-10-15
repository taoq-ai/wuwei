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

## What it is, in plain words

WUWEI is a plugin for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (and
OpenAI Codex). Once installed in a project, your Claude session stops being one assistant and
becomes a small team: a lead that plans, builders that write code test first, reviewers that check
each change, and a shepherd that takes pull requests to merge. You set the goals and approve the
plan. The team does the rest and only interrupts you for decisions that are truly yours.

WUWEI itself does not write code. It watches what the team produces (commits, pull requests,
reviews, CI) and:

- says what is still missing before a change counts as done (a test, a review, green CI);
- refuses the few actions that cannot be undone (merging with gaps, force pushes, leaking secrets);
- keeps a tamper-evident record of everything, and a daily report.

You do not need to learn a new tool to use it. You talk to Claude as usual and run two slash
commands: `/wuwei-plan` to start or change the work, `/wuwei-close` to wrap up.

## Before you start

You need all of these. Each line says how to check.

| Need | Check | Get it |
| --- | --- | --- |
| Claude Code (or Codex) | `claude --version` | [Claude Code setup](https://docs.claude.com/en/docs/claude-code/setup) |
| Python 3.11 or newer | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| Git | `git --version` | [git-scm.com](https://git-scm.com/downloads) |
| GitHub CLI, signed in | `gh auth status` | [cli.github.com](https://cli.github.com/), then `gh auth login` |
| A project on GitHub | `git remote -v` shows a `github.com` URL | create a repository and push your project |

WUWEI installs no packages. Its runtime is the Python standard library.

## Quickstart (about ten minutes)

**1. Install the plugin.** Start Claude Code anywhere and type:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

Then quit Claude Code (`/exit`) so the plugin loads on the next start.

**2. Set up your project.** The `wuwei` command is not put on your PATH; it lives inside the
installed plugin. In a terminal, go to your project and run it by its full path:

```sh
cd path/to/your-project
WUWEI=$(find ~/.claude/plugins -type f -path '*/bin/wuwei' | sort | tail -n 1)
"$WUWEI" --version   # prints the plugin version, e.g. 1.1.0
"$WUWEI" init        # creates .wuwei/ and adds permission rules to .claude/settings.json
"$WUWEI" doctor      # checks the install
```

If `find` prints nothing, the plugin is not installed yet: go back to step 1. You can also skip
the terminal: open Claude Code in your project and say "find the WUWEI plugin's `bin/wuwei` under
`~/.claude/plugins` and run `init`, then `doctor`".

`init` is safe to re-run and keeps your existing settings. It creates:

- `.wuwei/`: the plan, your goals, the record and the reports. It ignores itself in git, so it
  never ends up in a pull request.
- rules in `.claude/settings.json`: everyday commands are allowed, the dangerous ones denied,
  infrastructure commands (terraform, kubectl, helm and similar) ask you first.

`doctor` prints one line per check. `ok` is fine. `fail` must be fixed (usually `gh auth login`).
`warn` on the door lines is normal: it means WUWEI's refusals are enforced on your machine but your
GitHub repository has no branch protection backing them up yet (see
[the doors](https://taoq-ai.github.io/wuwei/concepts/doors/)).

**3. Write your goals (optional).** Open `.wuwei/goals.md` and fill in what you want to achieve:

```text
## G-1
Outcome: Users can reset their password by email
Measure: reset flow covered by an end-to-end test
Target: shipped and passing in CI
Date: 2026-11-30
Priority: 1
```

Leave it empty and the first plan will propose up to three goals for you to approve.

**4. Plan your first day.** Open Claude Code in your project (`claude`) and type:

```text
/wuwei-plan
```

The lead reads your repository and issues, proposes work items ranked against your goals, and shows
you the plan (also saved as `.wuwei/plan.html`, open it in a browser). You answer once: **Approve**
or **Change**.

**5. Let it work.** After approval, builders start in parallel, reviewers check each change, and
pull requests open and merge once their evidence is complete. Ask "what is the status?" at any time,
or run `"$WUWEI" status` in a terminal.

**6. Close the day.** When you stop:

```text
/wuwei-close
```

You get a report in `.wuwei/days/<date>/report.md` and a short retro with at most three proposals
for doing better. Run `/wuwei-plan` again tomorrow, or whenever priorities change.

## What changes for you

- **Fewer questions.** Claude no longer asks "should I continue?" or "which name do you prefer?".
  It decides, writes down its assumption, and moves on. You are asked only about things that are
  hard to undo, scope, goals, trust, infrastructure, and exceptions. Each such question starts with
  its kind, for example `one-way:` or `scope:`, so you know why it reached you.
- **No pushing straight to `main`.** Every change goes through a branch and a pull request, and
  force pushes are refused. If you are used to committing directly to your default branch, this is
  the biggest habit change.
- **Pull requests carry evidence.** Each PR body names its plan item (`WUWEI-Item: <id>`) and
  includes a test, or says why none fits (`No test: <reason>`). Claude adds these for you; WUWEI
  explains what is missing when it is not there.
- **A refusal is not an error.** When WUWEI blocks something, it says why and what is missing. The
  team fixes the gap and tries again; you do nothing.

## Words you will see

| Word | Meaning |
| --- | --- |
| owner | you: the person who sets goals and answers the few questions that matter |
| item | one unit of planned work, usually one pull request |
| plan pass | one run of `/wuwei-plan`: adds, drops or re-ranks items; run it as often as you like |
| WSJF, RICE | the two ranking formulas; WSJF is the default |
| lead, builder | the agent that plans, and the agents that build items test first |
| sentinel, gate | an independent reviewer (architecture, quality, security, goal) and its verdict |
| shepherd | the agent that follows each pull request to merge |
| steward | the agent that writes the retro and proposes improvements |
| evidence, gap | what a PR must show before it can merge, and what it still lacks |
| door | one of the few actions WUWEI refuses because they cannot be undone |
| tier | how much review an item needs: `light`, `standard` or `full` |
| andon | a stop cord: `wuwei andon owner/repo --reason "..."` pauses new work in one repository |
| checkpoint | one run of `/wuwei-close`: the report and retro so far |

## For coding agents setting this up

If you are an agent asked to install or adopt WUWEI in a repository, do this in order and stop at
the first failure:

1. Confirm the prerequisites: `python3 --version` is 3.11 or newer, `git remote -v` names a
   GitHub repository, `gh auth status` succeeds.
2. Install the plugin with `/plugin marketplace add taoq-ai/wuwei` and
   `/plugin install wuwei@wuwei` (Codex: `codex plugin marketplace add taoq-ai/wuwei` and
   `codex plugin add wuwei@wuwei`). A plugin install needs the user's harness; if you cannot run
   slash commands, ask the user to run these two lines and restart the session.
3. Locate the CLI: `find ~/.claude/plugins -type f -path '*/bin/wuwei'`. It is never on PATH.
   Always call it by its absolute path. After setup, each session's start prints that path as
   `WUWEI CLI: <path>`.
4. From the repository root run `<path> init` (add `--codex` on Codex, `--cloud` for Claude Code on
   the web, then commit `.claude/`). Then `<path> doctor`: exit code 0 is all ok, 1 means warnings
   only, 2 means a `fail` line you must fix.
5. Do not edit `.wuwei/plan.json` or anything under `.wuwei/ledger/` by hand; use the CLI.
6. Tell the user to restart the session and run `/wuwei-plan`. The `wuwei` skill (loaded with the
   plugin) explains what done means, the doors, and when to ask the owner.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `wuwei: command not found` | It is not on PATH by design. Use the full path from step 2 of the quickstart. |
| `no .wuwei/ here or above; run wuwei init` | Run `init` from your project root first. |
| `fail gh` in `doctor` | Run `gh auth login`. |
| `repos: none configured` | Your project has no GitHub `origin`. Add one, or run `"$WUWEI" config repos owner/name`. |
| `/wuwei-plan` is not recognised | The plugin is not loaded: check `/plugin`, then restart Claude Code. |
| A merge or `gh pr create` is refused | Expected: the message lists the missing evidence. Let the team close the gaps, or run `"$WUWEI" evidence owner/repo#123` to see them. |

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

## Other setups

- **Keep work moving while you are away:** in a local session, `/loop 20m /wuwei-watch` runs a
  watch pass every 20 minutes (CI, review threads, stalled PRs, the next item).
- **Codex:** `codex plugin marketplace add taoq-ai/wuwei`, `codex plugin add wuwei@wuwei`, then run
  the plugin's `bin/wuwei init --codex` (search for it under `~/.codex`). See
  [running on Codex](https://taoq-ai.github.io/wuwei/concepts/codex/).
- **Claude Code on the web:** `init --cloud`, then commit `.claude/`. See
  [cloud sessions](https://taoq-ai.github.io/wuwei/concepts/cloud/).
- **Several repositories:** `"$WUWEI" config repos owner/a,owner/b`, or tell the session.

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

- [Getting started](https://taoq-ai.github.io/wuwei/getting-started/): the quickstart with more detail.
- [Concepts](https://taoq-ai.github.io/wuwei/concepts/): every idea in WUWEI and why it is there.
- [Design](docs/design.md) and [constitution](.specify/memory/constitution.md).
- [Security](SECURITY.md).

## Development

```sh
python3 -m pytest -q
```

WUWEI audits its own changes: every PR names `WUWEI-Item: <issue>` and passes its gates.

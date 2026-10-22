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
## What it is

A plugin for Claude Code (and Codex) that turns your session into a team: a lead plans, builders
write code test first, reviewers check each change, a shepherd takes pull requests to merge. You
set goals and approve the plan. WUWEI checks each PR's evidence (test, reviews, green CI), refuses
what cannot be undone (merging with gaps, force pushes, leaking secrets), and only asks you what is
yours.

## Quickstart

Needs Python 3.11+, Git, and the [GitHub CLI](https://cli.github.com/) signed in (`gh auth login`),
in a project hosted on GitHub.

**1. Install** in Claude Code, then restart it:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

**2. Set up your project.** The CLI lives inside the plugin, not on your PATH:

```sh
cd your-project
WUWEI=$(find ~/.claude/plugins -type f -path '*/bin/wuwei' | sort | tail -n 1)
"$WUWEI" init     # creates .wuwei/ and adds permission rules to .claude/settings.json
"$WUWEI" doctor   # fix any "fail"; "warn" on doors just means no branch protection on GitHub
```

**3. Work.** Open Claude Code in the project:

```text
/wuwei-run      # proposes goals and ranked work; you answer Approve or Change
/wuwei-close    # end of day: report and retro in .wuwei/
```

Between the two, the team builds, reviews and merges. Optional: `/loop 20m /wuwei-watch` keeps work
moving while you are away.

## What changes for you

- **Fewer questions.** Only hard-to-undo, scope, goal, trust and infrastructure decisions reach you,
  each tagged with its kind (`one-way:`, `scope:` ...).
- **No direct pushes to `main`.** Everything goes through a PR; force pushes are refused.
- **A refusal is not an error.** It lists what is missing, and the team closes the gap.

## For agents installing WUWEI

1. Check for Python 3.11+ (`python3 --version`; `WUWEI_PYTHON` names another), `gh auth status`, and a GitHub `origin`.
2. The plugin install is a slash command; if you cannot run it, ask the user to.
3. Locate the CLI with `find ~/.claude/plugins -type f -path '*/bin/wuwei'`. Never assume it is on
   PATH. Once set up, each session prints it as `WUWEI CLI: <path>`.
4. Run `<path> init` then `<path> doctor` from the repository root (exit 0 ok, 1 warnings, 2 fail; a `note` row never changes it).
5. Never edit `.wuwei/plan.json` or `.wuwei/ledger/` by hand. The `wuwei-rules` skill explains the rules.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `wuwei: command not found` | Use the full path from step 2. |
| `no .wuwei/ here or above` | Run `init` from the project root. |
| `fail gh` in `doctor` | `gh auth login` |
| `warn hooks` in `doctor` | No hook has fired, so nothing is enforced or recorded. Locally, check `/plugin` and restart; in the cloud, open a session that holds only this repository. |
| `/wuwei-run` not recognised | Check `/plugin`, then restart Claude Code. |

Codex, cloud sessions and several repositories: see [getting started](https://taoq-ai.github.io/wuwei/getting-started/).

## Commands

| Command | What it does |
| --- | --- |
| `status` | The board: what each open item still lacks |
| `evidence` | The gaps of one PR; `--record` saves it as a replay case |
| `plan` | `show`, `add`, `park`, `drop`, `done`, `pass` |
| `report` | The day report; `--dora` for the DORA keys |
| `close` | Checkpoint the day |
| `andon` | Pull or clear the cord on one repository |
| `init`, `doctor`, `config`, `verify`, `agents` | Set up, check, six config keys, the ledger chain, the role agents |

## Learn more

[Concepts](https://taoq-ai.github.io/wuwei/concepts/) (every idea and why it is there),
[design](docs/design.md), [constitution](.specify/memory/constitution.md), [security](SECURITY.md).

## Development

```sh
python3 -m pytest -q
```

WUWEI audits its own changes: every PR ends with the WUWEI footer naming its issue and passes its gates.

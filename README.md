<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/hero-light.svg">
    <img src="docs/assets/hero-light.svg" alt="WUWEI day loop: Plan, Build, Review and Close, with a build and check loop, three parallel review gates, one FIX round, a pull request shepherd, owner touchpoints, guards at action time and memory that carries each day into the next." width="100%">
  </picture>
</p>

<h1 align="center">WUWEI 无为</h1>

<p align="center"><strong>Autonomous delivery where the safe path is the default one.</strong></p>

<p align="center">无为 (wuwei) means "effortless action": work gets done without forcing it.</p>

<p align="center"><a href="docs/site/index.md">Documentation</a> · <a href="docs/site/concepts.md">Concepts</a> · <a href="docs/site/configuration.md">Configuration</a> · <a href="LICENSE">Apache 2.0</a></p>

## What WUWEI is and is not

WUWEI is a Claude Code plugin for a chartered team of agents. It gives each role a bounded job, keeps workspace memory, and checks actions through guards. The brand accent is `#00C9A7`.

WUWEI is not a hosted service, a tracker, a chat system, or a replacement for repository rules. It does not deploy, approve pull requests, or bypass branch protection. The current release includes the CLI, role charters and interactive day planner.

## How WUWEI compares

As of September 2026. Each row describes the tool from its own README or docs; these
projects move fast, so follow the links. WUWEI's design choice is that process written as
prompts or skills is guidance a model can skip, so it anchors its process in hooks that
refuse at the moment of action. It does not replace the tools below and can run alongside
them.

| Tool | What it does | Layer | Unit of work | Enforcement | State |
|---|---|---|---|---|---|
| [Spec Kit](https://github.com/github/spec-kit) | Constitution once per project, then specify, plan, tasks and implement per feature; many agents through integrations | Method and prompts | One feature | The agent follows the commands and templates | Markdown in the repository |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | A folder per change (proposal, specs with added requirements, design, tasks); propose, apply, then archive updates the specs; 30+ tools | Method and prompts | One change | The agent follows the commands | `openspec/` in the repository |
| [superpowers](https://github.com/obra/superpowers) | Composable skills (brainstorming, plans, TDD, debugging, subagent-driven development) loaded by a session-start hook; Claude Code, Codex, Cursor and others | Method and prompts | One task or branch | The agent checks for a relevant skill before each task | Plans and code in the repository |
| [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) | Agent personas (analyst, product manager, architect, developer, UX designer) and documents (brief, PRD, architecture, epics and stories) | Method and prompts | One change or project, sized to scope | The agent follows the skills | Documents in the repository |
| [Kiro](https://kiro.dev) | AWS agentic IDE, CLI and web; specs as requirements, design and tasks; hooks on file, tool and agent events | Its own agent runtime | One spec | Hooks, including PreToolUse hooks that can block a tool call | Spec files in the project |
| [Claude Code](https://code.claude.com/docs/en/overview) plan mode, subagents, hooks, memory | Plan before edits, subagents in their own context, hooks that can deny a tool call, `CLAUDE.md` and auto memory | Runtime | One session | The hooks you write | `CLAUDE.md` and auto memory |
| WUWEI | Chartered roles run a working day | Runtime (Claude Code hooks and a CLI) | A day across repositories: plan, seats, gates, PR, decisions, retro | Shipped hooks refuse at the moment of action and give the reason | Producer-only state and events under `.wuwei/`, written only by the CLI |

WUWEI ships the roles and the day loop: planner, lead, builder, shepherd, steward and four
sentinels, with three parallel review gates and one fix round ([concepts](docs/site/concepts.md)).
It works through `gh` for the code host, with tracker and chat as optional adapters. Releases
carry a signed manifest and an integrity check, and ZIRAN audits the role tool grants
([security](docs/site/security.md)). Retros feed the charters: seats propose changes,
`wuwei promote` lands them and a ledger records each outcome.

### How they compose

WUWEI is the loop and the enforcement, not a spec format. An item's spec can be written with
Spec Kit or OpenSpec; this repository builds WUWEI itself with Spec Kit (see `specs/`). A seat
can run superpowers' skills inside its worktree. Claude Code's hooks, subagents, skills and
plugins are what WUWEI is made of.

### Where WUWEI is worse

- Heavier to set up: a signed release asset, `init`, config and owner actions in a host
  terminal.
- Runs only in Claude Code (Codex is an optional seat runtime).
- It supports one owner per workspace.
- Hooks add 40 to 100 ms per tool call depending on hardware
  ([hook latency budget](docs/site/reference.md#hook-latency-budget)).
- The guards are cooperative mistake prevention, not an isolation boundary
  ([security](docs/site/security.md)).
- It is proven only by its author's own use so far; the live rehearsal is the release
  criterion ([rehearsal](docs/site/rehearsal.md)).

## Install

You need Claude Code, Python 3.11 or newer, Git and `ssh-keygen`. Install the signed
`wuwei.tar.gz` release asset. From the project directory that will own the workspace:

```sh
curl -fL https://github.com/taoq-ai/wuwei/releases/latest/download/wuwei.tar.gz -o ../wuwei.tar.gz
mkdir -p ../wuwei-plugin
tar -xzf ../wuwei.tar.gz -C ../wuwei-plugin --strip-components=1
```

Use a fresh extraction directory. The archive includes `MANIFEST.sha256` and its
signature; GitHub's automatic source archives do not. In Claude Code, register the
extracted plugin:

```text
/plugin marketplace add ../wuwei-plugin
/plugin install wuwei@wuwei
```

The second command installs `wuwei` from the local `wuwei` marketplace. The plugin does not need a Python package install. Optional adapters need their own tools or credentials. See [integrity](docs/integrity.md) for signature verification and key pinning.

## Quick start

From the same project directory, initialize the workspace:

```sh
../wuwei-plugin/bin/wuwei init .
```

`init` ends by checking the installation. An intact signed release prints `plugin integrity: clean` and needs no reconfirmation.

`init` creates `.wuwei/` and adds workspace guard denials to `.claude/settings.json`. From another project, use the installed plugin's `bin/wuwei` path. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls; plain `python3 -m wuwei` can import a same-named directory in the current working directory.

Edit `.wuwei/config.toml` to name repositories and choose adapters. See [configuration](docs/site/configuration.md) for every setting and default. To update an existing workspace after a plugin upgrade, run `bin/wuwei init --upgrade --dry-run` and then `bin/wuwei init --upgrade`.

Run `/wuwei plan` to start the planner and morning gate. See [concepts](docs/site/concepts.md) for roles, guards and the day flow.

## Development installs

`/plugin marketplace add taoq-ai/wuwei` followed by `/plugin install wuwei@wuwei`
uses the marketplace's `./` development source. A source checkout is also a
development install. From the workspace, use that installed checkout's `bin/wuwei`
to run `init .`, then run `bin/wuwei integrity reconfirm` in a host terminal and type
the displayed digest after reviewing the checkout. Agent tools cannot reconfirm.

The checkout must have a clean tree. Reconfirmation pins its content, HEAD commit
and clean state once per commit. Repeated tool calls pass while HEAD and the tree
remain unchanged. After a pull moves HEAD, reconfirm the new clean commit; an
uncommitted edit blocks tools until the checkout is clean again. Missing VCS
evidence fails closed. Prefer the signed release for normal installation.

## Development

Run the test suite with Python 3.11 or newer and pytest:

```sh
python3 -m pytest -q
```

Skill routing cases under `evals/` are checked for structure by pytest without network
access. To measure the live triggering rate, install Claude Code, set
`ANTHROPIC_API_KEY` in your environment, then run:

```sh
claude plugin eval . --trust-plugin --ablation none --threshold 0.9 --json skill-evals.json
```

The runner exits 1 if any case scores below 0.9 (default 3 runs per case, so
each case must pass every run), and 2 if authentication or a cost limit prevents
a complete run. The `skill-evals` CI job runs on pushes to
main when the key is configured. The repository owner must add
`ANTHROPIC_API_KEY` as a GitHub Actions secret; until then the job prints a
skip message.

See the [design](docs/specs/2026-09-24-wuwei-design.md) and [NOTICE](NOTICE).

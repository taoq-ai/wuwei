<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/site/assets/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/site/assets/hero-light.svg">
    <img src="docs/site/assets/hero-light.svg" alt="WUWEI day loop. Calibration and the owner interview come before the first Plan. Each day is planned and ranked, and each item is built and checked, then reviewed by one gate or three by tier, with one fix round. A shepherd takes each pull request to merge under the merge policy, and Close runs a retro that carries the lessons into the next day. Guards with a heartbeat check every action, and the owner answers decisions from the phone through the DM. Tools, outlined when planned. Plan tracker: Linear; planned Jira, GitHub Projects. Plan spec engine: planned spec-kit, superpowers, OpenSpec. Build runtime: Claude Code, Codex. Review gate tools: ZIRAN, pytest. Close code host: GitHub; planned GitLab. Close docs: planned Notion, Confluence, Markdown. Phone and DM: Slack, Claude mobile; planned Teams, Discord. On-call: planned PagerDuty, Grafana, Sentry, Datadog." width="100%">
  </picture>
</p>

<h1 align="center">WUWEI 无为</h1>

<p align="center"><strong>Autonomous delivery where the safe path is the default one.</strong></p>

<p align="center">无为 (wuwei, said woo-way) means "effortless action": work gets done without forcing it.</p>

<p align="center"><a href="docs/site/index.md">Documentation</a> · <a href="docs/site/concepts.md">Concepts</a> · <a href="docs/site/configuration.md">Configuration</a> · <a href="LICENSE">Apache 2.0</a></p>

WUWEI runs your coding agents the way a careful engineering team works. The day is planned
and ranked, and you approve the plan each morning. Every change is reviewed by an agent that
did not write it, merges follow your merge policy, and the day ends with a retro that
proposes changes to the rules.

## What WUWEI is and is not

WUWEI is a Claude Code plugin for a chartered team of agents. It gives each role a bounded job, keeps workspace memory, and checks actions through guards. The brand accent is `#00C9A7`.

WUWEI is not a hosted service, a tracker, a chat system, or a replacement for repository rules. It does not deploy, approve pull requests, or bypass branch protection.

## What ships today

- The day loop: `/wuwei plan`, the morning [gate](docs/site/concepts.md#gate), builders, gates, PR and close ([daily path](docs/site/daily.md)).
- Guards at action time, a signed release and integrity checks ([security](docs/site/security.md)).
- Review [tiers](docs/site/concepts.md#tier): one quality gate for a small change, three gates otherwise ([review tiers](docs/site/concepts.md#review-tiers)).
- Remote operation from the phone through Remote Control and a Slack owner DM ([remote operation](docs/site/remote.md)).
- The cockpit: a day board on loopback and inline in Claude Code ([cockpit and board](docs/site/concepts.md#cockpit-and-board)).
- Calibration and the owner interview ([calibration](docs/site/configuration.md#calibration)).
- Setup in one command: it finds the repositories, calibrates them, asks the owner interview and applies one proposal after its [digest](docs/site/concepts.md#digest) ([setup](docs/site/daily.md#2-configure)).
- Doctor: install, host, workspace, gate, day and guard problems, each with its fix ([doctor](docs/site/reference.md#doctor)).
- Security posture: observe, guarded or strict per area, with floors no setting lowers. The MCP registry gate warns by default and blocks on a critical finding or a check that could not run ([security posture](docs/site/security.md#security-posture)).
- The heartbeat: probes that prove the system behaves, with a dead-man ping ([heartbeat](docs/site/reference.md#heartbeat)).

Designed, not built: cruise mode, graduated autonomy per decision class
([design spec](docs/specs/2026-09-24-wuwei-design.md), section 5.8.1).

## How WUWEI compares

As of October 2026. Each other tool is described from its own README or docs. These
projects change often, so follow the links. WUWEI keeps its process in hooks that refuse at
the moment of action, since a model can skip a process written only as prompts. It runs
alongside the tools below.

| Tool | Who plans the day | Who reviews the work | What stops a bad merge | What is learned afterwards | Where it runs |
|---|---|---|---|---|---|
| **WUWEI**, chartered roles that run a working day | A planner [seat](docs/site/concepts.md#seat) ranks the work and you approve it at the morning gate | One or three gates that did not write the change, then one fix round | Shipped hooks refuse at the moment of action; the merge policy and your branch protection decide | A daily retro: seats propose rule changes and you promote them | Claude Code, across your repositories, through `gh` |
| [Spec Kit](https://github.com/github/spec-kit), a spec-driven development toolkit | You run specify, plan and tasks per feature, after a project constitution | Converge adds checklists and consistency analysis when you want them | Your repository rules | Specs and the constitution in the repository | Many coding agents through integrations |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec), spec-driven development for AI coding assistants | You propose a change and the agent writes its specs, design and tasks | An optional verify step | Your repository rules | Archiving a change updates the specs | 30+ coding tools |
| [superpowers](https://github.com/obra/superpowers), composable skills loaded by a session-start hook | Brainstorming, then a plan of small tasks | Each task is reviewed for spec compliance, then code quality | Finishing a branch verifies tests, then you choose merge or PR | Plans and code in the repository | Claude Code, Codex, Cursor, Gemini CLI and others |
| [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD), agile AI-driven development with agent personas | Analyst, product manager and architect agents write the brief, PRD and architecture | A code review skill with several independent reviewers | Your repository rules | A retrospective reviews each finished epic, and the loop goes back to planning | Coding tools that support skills; Claude Code and Codex plugins |
| [Kiro](https://kiro.dev), an agentic IDE, CLI and web app by AWS | Specs with requirements, design and tasks | Your own review | Hooks you write; a PreToolUse hook can block a tool call | Steering files you write | Kiro IDE, CLI and web |
| [Claude Code](https://code.claude.com/docs/en/overview) plan mode, subagents, hooks, memory | Plan mode proposes a plan before any edit | Subagents you define; automatic review on pull requests | Hooks you write; a PreToolUse hook can deny a tool call | `CLAUDE.md` and auto memory | Terminal, IDE, desktop app and web |

WUWEI's roles are the planner, lead, builder, [shepherd](docs/site/concepts.md#shepherd), [steward](docs/site/concepts.md#steward) and four
[sentinels](docs/site/concepts.md#sentinel) ([concepts](docs/site/concepts.md)). It works through `gh` for the code host, with tracker
and chat as optional adapters. Releases include a signed manifest and an integrity check, and
ZIRAN audits the role tool grants ([security](docs/site/security.md)).

### How they compose

An item's spec can be written with Spec Kit or OpenSpec (this repository builds WUWEI with
Spec Kit, see `specs/`), and a seat can run superpowers' skills inside its worktree. Claude
Code's hooks, subagents, skills and plugins are what WUWEI is made of.

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

The second command installs `wuwei` from the local `wuwei` marketplace. The plugin does not need a Python package install. Optional adapters need their own tools or credentials. See [integrity](docs/site/integrity.md) for signature verification and key pinning.

## Quick start

From the same project directory, in a [host terminal](docs/site/concepts.md#host-terminal), set up the workspace:

```sh
../wuwei-plugin/bin/wuwei setup --shadow
```

`setup` runs `init` when there is no workspace, finds the git repositories in the project
directory (their GitHub names, default branches through `gh`, and commit identities), checks
the host, calibrates the repositories and asks the owner interview. It shows the whole
`config.toml` proposal once and applies it after you answer y. Then it runs
`doctor` and `mcp check` and ends with one line: `Ready: run /wuwei:wuwei-plan`, or `Next:`
with the one command still required. Optional items, such as branch protections, are listed
before it and do not block. A second run proposes nothing new
([calibration](docs/site/configuration.md#calibration)).

`--shadow` starts the guards in the observe posture for your first week: they record what they would refuse and let the call through, and `bin/wuwei shadow report` lists it. See [security posture](docs/site/concepts.md#security-posture).

Then check the install:

```sh
../wuwei-plugin/bin/wuwei doctor
```

It prints one row per check, with the fix for anything that is not ok.
`bin/wuwei doctor --fix` applies the deterministic fixes after one confirmation
([doctor](docs/site/reference.md#doctor)).

`init` ends by checking the installation. An intact signed release prints `plugin integrity: clean` and needs no reconfirmation. It creates `.wuwei/` and adds workspace guard denials to `.claude/settings.json`. From another project, use the installed plugin's `bin/wuwei` path. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls; plain `python3 -m wuwei` can import a same-named directory in the current working directory.

To change one value later, run `bin/wuwei config set owner.verbosity.default '"standard"'` or
`bin/wuwei config add-repo --name acme/widget --path widget --branch main` in a host terminal;
each shows a diff and applies it after its digest. See [configuration](docs/site/configuration.md) for every setting and default. To update an existing workspace after a plugin upgrade, run `bin/wuwei init --upgrade --dry-run` and then `bin/wuwei init --upgrade`.

Run `/wuwei plan` to start the planner and morning gate. See [concepts](docs/site/concepts.md) for roles, guards and the day flow.

Every Claude Code session in the workspace orients itself on start: what WUWEI is, where the day stands and the next step from `bin/wuwei next` ([what the session knows](docs/site/agent.md)).

## Limits

- WUWEI needs Claude Code. Codex can run seats as an optional runtime.
- One owner per workspace.
- Hooks add about 40 to 100 ms to each tool call, depending on the machine
  ([hook latency budget](docs/site/reference.md#hook-latency-budget)).
- It is early: so far only its author has used it day to day, and the
  [live rehearsal](docs/site/rehearsal.md) is the check before each release.
- Start a new project with `setup --shadow`: a first week in the observe posture, where the
  guards record what they would refuse before they refuse it
  ([security posture](docs/site/security.md#security-posture)).

What the guards cover, and what they leave to the code host, is in
[security](docs/site/security.md).

## Development installs

`/plugin marketplace add taoq-ai/wuwei` followed by `/plugin install wuwei@wuwei`
uses the marketplace's `./` development source. A source checkout is also a
development install. From the workspace, use that installed checkout's `bin/wuwei`
to run `init .`, then run `bin/wuwei integrity reconfirm` in a host terminal and answer
y after reviewing the checkout. Agent tools cannot reconfirm.

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

See the [design](docs/specs/2026-09-24-wuwei-design.md) and [NOTICE](NOTICE). The
[contributing guide](https://github.com/taoq-ai/wuwei/blob/main/CONTRIBUTING.md) covers
how changes are made; report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## Acknowledgements

WUWEI builds on the work below. [NOTICE](NOTICE) has the licence of each.

- [GitHub Spec Kit](https://github.com/github/spec-kit): the vendored `.specify/` files and
  `speckit-*` skills behind this repository's workflow (MIT).
- [Simple Icons](https://github.com/simple-icons/simple-icons): the tool glyphs in the hero
  (CC0).
- [autoharness](https://github.com/tigerless-labs/autoharness): propose then promote, the
  ledger and the adherence lifecycle (MIT, ideas only).
- [ralph-starter](https://github.com/rubenmarcus/ralph-starter): the builder loop with
  backpressure and stuck detection (MIT, ideas only).
- [humanizer](docs/site/concepts.md#humanizer) ([source](https://github.com/blader/humanizer)): the writing checklist in the charters
  (MIT, paraphrased).
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing):
  the source humanizer is based on.
- [Model Context Protocol](https://modelcontextprotocol.io): the protocol the board server
  implements (Apache-2.0, MIT and CC-BY-4.0).
- [MCP Apps](https://github.com/modelcontextprotocol/ext-apps): the `ui://` resource
  convention the board serves (Apache-2.0, MIT and CC-BY-4.0).
- [release-please](https://github.com/googleapis/release-please): release automation in CI
  (Apache-2.0).
- [ZIRAN](https://github.com/taoq-ai/ziran): the role grant audit in CI (Apache-2.0).
- [WSJF](https://framework.scaledagile.com/wsjf): Donald Reinertsen, as popularised by
  SAFe; the `wsjf` ranking.
- [RICE](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/):
  Sean McBride, Intercom; the `rice` ranking.
- [One-way and two-way doors](https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF):
  Jeff Bezos, Amazon 2015 letter to shareholders; the decision framework.

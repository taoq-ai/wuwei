<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/hero-light.svg">
    <img src="docs/assets/hero-light.svg" alt="WUWEI day flow: Plan, Build, Review, Close. Guards and memory support each step." width="100%">
  </picture>
</p>

<h1 align="center">WUWEI 无为</h1>

<p align="center"><strong>Autonomous delivery where the safe path is the default one.</strong></p>

<p align="center">无为 (wuwei) means "effortless action": work gets done without forcing it.</p>

<p align="center"><a href="docs/site/index.md">Documentation</a> · <a href="docs/site/concepts.md">Concepts</a> · <a href="docs/site/configuration.md">Configuration</a> · <a href="LICENSE">Apache 2.0</a></p>

## What WUWEI is and is not

WUWEI is a Claude Code plugin for a chartered team of agents. It gives each role a bounded job, keeps workspace memory, and checks actions through guards. The brand accent is `#00C9A7`.

WUWEI is not a hosted service, a tracker, a chat system, or a replacement for repository rules. It does not deploy, approve pull requests, or bypass branch protection. The current release contains the CLI and role charters; the interactive day planner is planned.

## Install

You need Claude Code and Python 3.11 or newer. In Claude Code, run:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

The second command installs `wuwei` from the `wuwei` marketplace. The plugin does not need a Python package install. Optional adapters need their own tools or credentials; the default workspace can be created without them.

## Quick start

From a local checkout of WUWEI, use its CLI in the project directory that will own the workspace:

```sh
../wuwei-plugin/bin/wuwei init .
```

For this example, clone the repository as a sibling first with `git clone https://github.com/taoq-ai/wuwei.git ../wuwei-plugin`. If you know the installed plugin checkout path, use its `bin/wuwei` instead.

`init` creates `.wuwei/` and adds workspace guard denials to `.claude/settings.json`. From another project, use the installed plugin's `bin/wuwei` path. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls; plain `python3 -m wuwei` can import a same-named directory in the current working directory.

Edit `.wuwei/config.toml` to name repositories and choose adapters. See [configuration](docs/site/configuration.md) for every setting and default. To update an existing workspace after a plugin upgrade, run `bin/wuwei init --upgrade --dry-run` and then `bin/wuwei init --upgrade`.

The designed next step is `/wuwei plan`, which will start the planner and morning gate. **Planned:** that Claude Code skill is not shipped in this version, so it cannot yet be run. See [concepts](docs/site/concepts.md) for the planned day flow and the CLI functions available today.

## Development

Run the test suite with Python 3.11 or newer and pytest:

```sh
python3 -m pytest -q
```

See the [design](docs/specs/2026-09-24-wuwei-design.md) and [NOTICE](NOTICE).

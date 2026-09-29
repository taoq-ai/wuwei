---
layout: default
---

# WUWEI documentation

WUWEI 无为 means "effortless action." It is a Claude Code plugin for a chartered team, workspace memory and action-time guards.

- [Concepts](concepts.html): roles, guards, memory and the day flow
- [Configuration](configuration.html): every shipped workspace setting
- [Operator reference](reference.html): JSON, decisions, retro and companion protocol
- [Adapters and ports](adapters.html): integrations and three-state results
- [Charter overrides](charter-overrides.html): local rules and promote
- [Security integration](security.html): scanner status and threat model 9.1

## Start here

Install the signed `wuwei.tar.gz` release asset with Claude Code, Python 3.11 or newer,
Git and `ssh-keygen` available. From your project directory, download and extract it
into a fresh sibling directory:

```sh
curl -fL https://github.com/taoq-ai/wuwei/releases/latest/download/wuwei.tar.gz -o ../wuwei.tar.gz
mkdir -p ../wuwei-plugin
tar -xzf ../wuwei.tar.gz -C ../wuwei-plugin --strip-components=1
```

The asset contains `MANIFEST.sha256` and its signature. GitHub's automatic source
archives are unsigned. In Claude Code, run:

```text
/plugin marketplace add ../wuwei-plugin
/plugin install wuwei@wuwei
```

In your project directory, initialize the workspace and verify the installation:

```sh
../wuwei-plugin/bin/wuwei init .
../wuwei-plugin/bin/wuwei integrity check
```

An intact signed release needs no reconfirmation. Edit `.wuwei/config.toml` for your
repositories and adapters. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls.
Run `/wuwei plan` to start the planner and owner morning gate, followed by builders,
review and close. The linked pages describe the CLI and configuration.

## Development checkouts

`/plugin marketplace add taoq-ai/wuwei` and `/plugin install wuwei@wuwei` install
the marketplace's `./` development source. For that installation or a source
checkout, use the installed checkout's `bin/wuwei` to initialize the workspace.
Then, from the workspace in a host terminal, run `bin/wuwei integrity reconfirm`
using that executable and type the displayed digest after reviewing its contents.

Reconfirmation records the content fingerprint, HEAD commit and clean tree state.
One confirmation permits repeated tool calls while HEAD and the tree are unchanged.
A pull that moves HEAD requires reconfirming the new clean commit. Uncommitted
edits block tools and cannot be reconfirmed until the checkout is clean. Missing
VCS evidence also fails closed. Agent tools cannot run host reconfirmation.

---
layout: default
---

# WUWEI documentation

WUWEI 无为 means "effortless action." It is a Claude Code plugin that runs your coding agents the way a careful engineering team works: the day is planned and ranked, each change is reviewed by an agent that did not write it, merges follow a policy, and a retro at the end of the day proposes changes to the rules.

- [Daily path](daily.html): one solo-owner path from install to close
- [Remote operation](remote.html): run a day from the phone with Remote Control and the Slack owner DM
- [Recovery](recovery.html): low-level commands for when evidence and state disagree
- [Concepts](concepts.html): roles, guards, memory, the day flow, review tiers, sessions, the listener, the heartbeat and the board
- [Configuration](configuration.html): every section and key of the workspace config
- [Operator reference](reference.html): every CLI command, JSON, decisions, heartbeat, sessions and hook latency budget
- [Adapters and ports](adapters.html): integrations and three-state results
- [Charter overrides](charter-overrides.html): local rules and promote
- [Security integration](security.html): scanner status and threat model 9.1
- [Release rehearsal](rehearsal.html): the live journey to run before a release

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

In your project directory, initialize the workspace:

```sh
../wuwei-plugin/bin/wuwei init .
```

`init` ends by checking the installation. An intact signed release prints
`plugin integrity: clean` and needs no reconfirmation. Edit `.wuwei/config.toml` for your
repositories and adapters. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls.
Calibrate once with `bin/wuwei calibrate`, read its report, then run
`bin/wuwei config promote` and `bin/wuwei promote` in a host terminal. Answer the owner
interview with `bin/wuwei calibrate --interview` in a host terminal and promote the answers
the same way ([daily path](daily.html)).
Run `/wuwei plan` to start the planner and owner morning gate, followed by builders,
review and close. The [daily path](daily.html) walks through the whole day; the linked pages describe the CLI and configuration.

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

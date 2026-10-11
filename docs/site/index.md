# WUWEI documentation

WUWEI 无为 (said woo-way) means "effortless action." It is a Claude Code plugin that runs your coding agents the way a careful engineering team works: the day is planned and ranked, each change is reviewed by an agent that did not write it, merges follow a policy, and a retro at the end of the day proposes changes to the rules.

<img src="assets/hero-light.svg#only-light" alt="A ranked queue you approve feeds an agent team working three parallel lanes that loop build and check, every candidate passes the gates within the round cap, pull requests wait in a stack the shepherd sweeps until they merge, and you answer the odd card from the phone while guards, heartbeat, lead and steward work under the hood and each day's retro feeds tomorrow's plan." width="100%">
<img src="assets/hero-dark.svg#only-dark" alt="A ranked queue you approve feeds an agent team working three parallel lanes that loop build and check, every candidate passes the gates within the round cap, pull requests wait in a stack the shepherd sweeps until they merge, and you answer the odd card from the phone while guards, heartbeat, lead and steward work under the hood and each day's retro feeds tomorrow's plan." width="100%">

- [Daily path](daily.md): one solo-owner path from install to close
- [What the session knows](agent.md): the guide every session in the workspace is pointed at on start
- [Concepts](concepts.md): roles, guards, memory, the day flow, review [tiers](concepts.md#tier), sessions and the heartbeat
- [Recovery](recovery.md): doctor first, troubleshooting for first-day failures, and low-level commands for when evidence and state disagree
- [Adapters and ports](adapters.md): integrations and three-state results
- [Charter overrides](charter-overrides.md): local rules and promote
- [Security integration](security.md): scanner status and threat model 9.1
- [Integrity](integrity.md): the signed release, its manifest and host reconfirmation
- [Configuration](configuration.md): every section and key of the workspace config
- [Operator reference](reference.md): every CLI command, JSON, decisions, heartbeat, sessions and hook latency budget

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

In your project directory, create the workspace:

```sh
../wuwei-plugin/bin/wuwei init --shadow
```

`--shadow` starts the guards in the observe posture for a first week. `init` checks the
installation: an intact signed release prints `plugin integrity: clean` and needs no
reconfirmation. Then, in the session, the planner adds each repository with
`wuwei config add-repo` and applies the repository survey with `wuwei config promote`; each asks
its Owner step card. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls. To change one value
later, run `bin/wuwei config set <key> <value>`; it asks on a card too ([daily path](daily.md)).

Then run `../wuwei-plugin/bin/wuwei doctor`. It prints one row per check, with the fix for
anything that is not ok; `bin/wuwei doctor --fix` applies the deterministic fixes after one
confirmation ([doctor](reference.md#doctor)).

Run `/wuwei plan` to start the planner and owner morning [gate](concepts.md#gate), followed by builders,
review and close. The [daily path](daily.md) walks through the whole day; the other links describe the CLI and configuration.

## Development checkouts

`/plugin marketplace add taoq-ai/wuwei` and `/plugin install wuwei@wuwei` install
the marketplace's `./` development source. For that installation or a source
checkout, use the installed checkout's `bin/wuwei` to initialize the workspace.
Then, from the workspace in a host terminal, run `bin/wuwei integrity reconfirm`
using that executable and answer y after reviewing its contents.

Reconfirmation records the content fingerprint, HEAD commit and clean tree state.
One confirmation permits repeated tool calls while HEAD and the tree are unchanged.
A pull that moves HEAD requires reconfirming the new clean commit. Uncommitted
edits block tools and cannot be reconfirmed until the checkout is clean. Missing
VCS evidence also fails closed. Agent tools cannot run host reconfirmation.

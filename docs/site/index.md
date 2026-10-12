# WUWEI documentation

WUWEI 无为 (said woo-way) means "effortless action." It is a Claude Code plugin that runs your coding agents the way a careful engineering team works. The day is planned and ranked, and an agent that did not write a change reviews it. Merges follow a policy, and a retro at the end of the day proposes changes to the rules.

<img src="assets/hero-light.svg#only-light" alt="A ranked queue you approve feeds an agent team working three parallel lanes that loop build and check, every candidate passes the gates within the round cap, pull requests wait in a stack the shepherd follows until they merge, and you answer the odd card in the session while guards, lead and steward work under the hood and each day's retro feeds tomorrow's plan." width="100%">
<img src="assets/hero-dark.svg#only-dark" alt="A ranked queue you approve feeds an agent team working three parallel lanes that loop build and check, every candidate passes the gates within the round cap, pull requests wait in a stack the shepherd follows until they merge, and you answer the odd card in the session while guards, lead and steward work under the hood and each day's retro feeds tomorrow's plan." width="100%">

- [Daily path](daily.md): one solo-owner path from install to close
- [What the session knows](agent.md): the guide every session in the workspace reads on start
- [Concepts](concepts.md): roles, guards, memory, the day flow and review tiers
- [Security](security.md): the guards, scanner findings, the irreversible edges and threat model 9.1
- [Operator reference](reference.md): every CLI command and its JSON
- [Configuration](configuration.md): every section and key of the workspace config
- [Adapters and ports](adapters.md): integrations, credentials and three-state results
- [Charter overrides](charter-overrides.md): local rules and how a retro proposal lands
- [Recovery](recovery.md): doctor first, then what to do when evidence and state disagree
- [Release rehearsal](rehearsal.md): the live journey to run before a release
- [Integrity](integrity.md): the signed release, its manifest and reconfirmation

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

`--shadow` sets `guards.enforce = false` for a first week: the guards log what they
would refuse and let the call through. `init` checks the installation. An intact
signed release prints `plugin integrity: clean` and needs no reconfirmation.

Then open Claude Code. The planner adds each repository with `wuwei config add-repo`
and applies the repository survey with `wuwei config promote`. Each asks its Owner
step card in the session. To change one value later, run
`bin/wuwei config set <key> <value>`; it asks on a card too.

`bin/wuwei doctor` prints one row per check, with the fix for anything that is not ok.
`bin/wuwei doctor --fix` applies the deterministic fixes after your answer on one card.

Run `/wuwei plan` to start the planner and the morning gate. The [daily path](daily.md)
walks through the whole day.

## Upgrade

After a plugin upgrade, run `bin/wuwei init --upgrade --dry-run`, then
`bin/wuwei init --upgrade`. It removes config keys and files no code reads any more,
one `Upgraded ...: remove ... (no longer read)` line each. It never removes anything
through a symlink or under `days/`, which is history.

## Development checkouts

`/plugin marketplace add taoq-ai/wuwei` and `/plugin install wuwei@wuwei` install
the marketplace's `./` development source. For that installation or a source
checkout, use the installed checkout's `bin/wuwei` to initialize the workspace.
Then run `bin/wuwei doctor --fix --apply integrity-reconfirm` and answer its Owner
step card after reviewing the checkout.

Reconfirmation records the content fingerprint, HEAD commit and clean tree state.
One confirmation holds while HEAD and the tree are unchanged. A pull that moves HEAD
requires reconfirming the new clean commit. Uncommitted edits show as an integrity
warning and cannot be reconfirmed until the checkout is clean; integrity never blocks a
tool call. Missing VCS evidence reads as a finding, never as clean.

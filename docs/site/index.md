# WUWEI documentation

WUWEI 无为 means "effortless action." It is a Claude Code plugin that runs your coding agents the way a careful engineering team works: the day is planned and ranked, each change is reviewed by an agent that did not write it, merges follow a policy, and a retro at the end of the day proposes changes to the rules.

<img src="assets/hero-light.svg#only-light" alt="WUWEI day loop. Calibration and the owner interview come before the first Plan. Each day is planned and ranked, and each item is built and checked, then reviewed by one gate or three by tier, with one fix round. A shepherd takes each pull request to merge under the merge policy, and Close runs a retro that carries the lessons into the next day. Guards with a heartbeat check every action, and the owner answers decisions from the phone through the DM." width="100%">
<img src="assets/hero-dark.svg#only-dark" alt="WUWEI day loop. Calibration and the owner interview come before the first Plan. Each day is planned and ranked, and each item is built and checked, then reviewed by one gate or three by tier, with one fix round. A shepherd takes each pull request to merge under the merge policy, and Close runs a retro that carries the lessons into the next day. Guards with a heartbeat check every action, and the owner answers decisions from the phone through the DM." width="100%">

- [Daily path](daily.md): one solo-owner path from install to close
- [What the session knows](agent.md): the guide every session in the workspace is pointed at on start
- [Remote operation](remote.md): run a day from the phone with Remote Control and the Slack owner DM
- [Recovery](recovery.md): doctor first, troubleshooting for first-day failures, and low-level commands for when evidence and state disagree
- [Concepts](concepts.md): roles, guards, memory, the day flow, review [tiers](concepts.md#tier), sessions, the listener, the heartbeat and the board
- [Configuration](configuration.md): every section and key of the workspace config
- [Operator reference](reference.md): every CLI command, JSON, decisions, heartbeat, sessions and hook latency budget
- [Adapters and ports](adapters.md): integrations and three-state results
- [Charter overrides](charter-overrides.md): local rules and promote
- [Security integration](security.md): scanner status and threat model 9.1
- [Integrity](integrity.md): the signed release, its manifest and host reconfirmation
- [Release rehearsal](rehearsal.md): the live journey to run before a release

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

In your project directory, in a [host terminal](concepts.md#host-terminal), set up the workspace:

```sh
../wuwei-plugin/bin/wuwei setup --shadow
```

`setup` runs `bin/wuwei init` when there is no workspace, finds the git repositories in the
project directory, calibrates them and asks the owner interview, then applies the whole
`config.toml` proposal after one [digest](concepts.md#digest), runs `doctor` and ends with
`Ready: run /wuwei:wuwei-plan` or the one `Next:` command still required. `--shadow` starts the
guards in the observe posture for a first week. `init` checks the installation: an intact signed
release prints `plugin integrity: clean` and needs no reconfirmation. Use `bin/wuwei` or
`python3 -P -m wuwei` for CLI calls. To change one value later, use `bin/wuwei config set` or
`bin/wuwei config add-repo` in a host terminal ([daily path](daily.md)).

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

---
layout: default
---

# WUWEI documentation

WUWEI 无为 means "effortless action." It is a Claude Code plugin for a chartered team, workspace memory and action-time guards.

- [Concepts](concepts.html): roles, guards, memory and the day flow
- [Configuration](configuration.html): every shipped workspace setting
- [Adapters and ports](adapters.html): integrations and three-state results
- [Charter overrides](charter-overrides.html): local rules and promote
- [Security integration](security.html): scanner status and threat model 9.1

## Start here

In Claude Code, run `/plugin marketplace add taoq-ai/wuwei`, then `/plugin install wuwei@wuwei`. In your project directory, clone the repository with `git clone https://github.com/taoq-ai/wuwei.git ../wuwei-plugin`, then run `../wuwei-plugin/bin/wuwei init .`. You can use an existing installed plugin checkout instead. This creates `.wuwei/config.toml`; edit it for your repositories and adapters. Use `bin/wuwei` or `python3 -P -m wuwei` for CLI calls.

**Planned:** `/wuwei plan` is the designed next step, but the skill is not present in this version. The planned flow is planner, lead, owner morning gate, builders, review and close. The available CLI is described in the linked pages.

---
layout: default
---

# Adapters and ports

[Home](index.html)

The CLI core asks named ports for plain data. Modules under `adapters/` implement those ports; external tools run there, not in core. Configure them in `.wuwei/config.toml` under `[adapters]`. An adapter result uses 0 clean, 1 findings, 2 could not run. A `none` adapter reports unmeasured when a measurement is required.

| Port | Shipped implementations | Default |
| --- | --- | --- |
| tracker | none, linear | none |
| chat | none, slack | none |
| review_bot | none, greptile | none |
| runtime | none, claude, codex | claude |
| scanner | none, ziran | none |
| code_host | none, github | github |
| vcs | git | git |
| host | none, local | local |
| checks | none, local | local |

The `vcs` port calls git; `code_host.github` calls `gh`. Tracker and chat integrations require their external access and credentials. The Codex runtime uses the configured companion command and timeout. The ZIRAN scanner requires **ZIRAN 0.39.0 or newer** and checks `ziran --version` before each measurement. Older or unavailable versions report unmeasured (exit 2). It supports S4 audit and S2 live traces through the [JSON CLI contract](configuration.html). S3 MCP registry checks run at init, upgrade and morning planning; they preserve snapshots and block launches on findings or incomplete measurement. Other ports in the design, including inbound messaging and control planes, are **planned** and have no config keys in the shipped template.

The read-only VCS operation `pushed_branches(repo)` returns unique branch names
from all local remote-tracking refs, excluding remote HEAD aliases. Close compares
these with the item's current branch. It does not fetch or write repository state;
missing tools, malformed output and timeouts return exit 2.

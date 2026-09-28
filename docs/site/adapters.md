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
| scanner | none | none |
| code_host | none, github | github |
| vcs | git | git |
| host | none, local | local |
| checks | none, local | local |

The `vcs` port calls git; `code_host.github` calls `gh`. Tracker and chat integrations require their external access and credentials. The Codex runtime uses the configured companion command and timeout. The current scanner port has only `none`; a ZIRAN scanner implementation is **planned**. Other ports in the design, including inbound messaging and control planes, are **planned** and have no config keys in the shipped template.

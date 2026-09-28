---
layout: default
---

# Charter overrides and promote

[Home](index.html)

Shipped role rules live in the plugin's `charters/`. Workspace-specific overrides live in `.wuwei/charters/` with matching role filenames such as `builder.md`. Keep the plugin charter as the common baseline; local overrides add rules for this workspace.

A seat or steward writes a JSON proposal in today's `.wuwei/days/YYYY-MM-DD/proposals/`. The proposal names `target`, `action`, `reason`, `evidence`, and for an add or patch, `text` or `delta`. Targets must be a local charter override or a memory note. Actions are `add`, `patch`, `fold` and `archive`. A patch also names the exact `old_text` to replace. Evidence points to an existing path inside `.wuwei/`.

Run the installed CLI's `bin/wuwei promote` from the workspace. It validates proposals, writes accepted changes atomically and records landed or rejected outcomes in `.wuwei/memory/ledger.jsonl` and the changelog. Rejections return exit 1. `bin/wuwei init --upgrade --dry-run` previews template changes and flags overrides whose charter versions need review; `bin/wuwei init --upgrade` applies config additions.

**Planned:** the full steward-led daily proposal cycle through `/wuwei plan`.

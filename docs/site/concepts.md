---
layout: default
---

# Concepts

[Home](index.html)

## Roles

The shipped charters define planner, lead, builder, shepherd, steward, and four sentinels: goal, architecture, quality and security. Generated agent files in `agents/` carry the charters and tool allowlists. The planner owns the day, the lead shapes work, builders implement, sentinels check, the shepherd follows pull requests and the steward maintains procedure. **Planned:** `/wuwei plan` orchestration and its morning gate.

## Guards

Claude Code hooks call the WUWEI CLI. Guards act when a tool is used and refuse relevant unsafe actions inside a WUWEI workspace or configured repository. Outside that scope they return clean. The three outcomes are 0 clean, 1 findings and 2 could not run. A relevant parse or measurement failure returns 2 with a reason. The CLI also records traces and events. See [security](security.html) for the trust boundary.

## Memory

`wuwei init` creates `.wuwei/memory/` with a spine, index and changelog. Day records live under `.wuwei/days/`. Settled facts belong in notes; procedure belongs in charters. The CLI provides `note`, `index`, `consolidate`, `payload` and `promote` commands. The owner edits goals and voice; seats propose changes for promotion. The index is generated and notes are bounded by configuration defaults.

## Day flow

Plan, Build, Review, Close is the intended flow. Today's CLI supports individual guard, state and memory operations. **Planned:** the skill that runs the full day from `/wuwei plan`.

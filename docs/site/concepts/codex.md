# Running on Codex

WUWEI runs on OpenAI Codex from the same repository, with the same CLI, hooks, charters, skills and
evidence. Codex reads Claude-style plugins (`.claude-plugin/plugin.json`, `skills/`,
`hooks/hooks.json`) and runs Claude-style lifecycle hooks with the same events and output shapes, so
there is no second plugin to keep in step.

## Install

```sh
codex plugin marketplace add taoq-ai/wuwei
codex plugin add wuwei@wuwei
```

Then, in the directory that owns the workspace:

```sh
bin/wuwei init --codex
```

That writes what a Codex plugin cannot carry:

- the eight role agents as `.codex/agents/<role>.toml`, with the charters as their instructions;
- WUWEI's doors as exec-policy rules in `.codex/rules/wuwei.rules` (force pushes, admin merges and
  repository deletion forbidden; infrastructure applies and destroys prompted).

Codex asks you to trust a new or changed hook before it runs: trust WUWEI's five hooks once, and again
after an upgrade changes them. Run `wuwei init --codex` again after an upgrade too; `wuwei doctor`
warns while the role files differ from the charters.

## What maps to what

| Claude Code | Codex | How WUWEI reads it |
| --- | --- | --- |
| `Bash` | `Bash` (shell and exec) | the same command guards |
| `Write`, `Edit` | `apply_patch` | the files the patch adds, updates, deletes or moves to; the ledger stays protected |
| `Agent` with `subagent_type` | `spawn_agent` with `agent_type` | a running seat; the Stop hook stays quiet while it runs |
| `AskUserQuestion` | `request_user_input` | the same owner classes; answers recorded by question |
| `mcp__server__tool` | `mcp__server__tool` | the same leak and merge doors |
| SubagentStop | SubagentStop | verdicts attested the same way |
| `.claude/settings.json` rules | `.codex/rules/*.rules` | written by `wuwei init` and `wuwei init --codex` |

The quality gate runs on a different model than the session's on Claude Code (`MODELS` in
`cli/wuwei/agents.py`). On Codex the role files name no model: Codex chooses its own, and a Claude
model name would not resolve there.

## Gates on Codex

A gate counts only when WUWEI attests its verdict from the seat's own hand-back or SubagentStop. A
`codex-companion` task job started from a Claude session is not a seat: it has no SubagentStop, so
its verdict file sits unattested and `wuwei evidence` names it as not counted (#1078). A Codex-native
seat (`spawn_agent` with `agent_type` `sentinel-<gate>`) goes through the same hooks; whether it is
attested is what the codex-attest-probe item checks. Until that probe records an attested seat, run
gates as Claude seats.

**Why:** the process is the product, not the harness. The same evidence, doors and questions hold
whichever agent does the work, and a team can run both without two rule books.

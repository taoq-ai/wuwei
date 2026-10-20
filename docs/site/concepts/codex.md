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
| `AskUserQuestion` | `request_user_input` | the same owner classes; answers recorded as `answer.unconfirmed` until WUWEI reads Codex's transcript |
| `mcp__server__tool` | `mcp__server__tool` | the same leak and merge doors |
| SubagentStop | SubagentStop | recorded as `seat.unconfirmed`, with no attestation, until WUWEI reads Codex's transcript |
| `.claude/settings.json` rules | `.codex/rules/*.rules` | written by `wuwei init` and `wuwei init --codex` |

On Claude Code each seat's model and effort come from the [model table](models.md). On Codex the
role files name no model: Codex chooses its own, and a Claude model name would not resolve there.
The models page maps each step of the table to a Codex model. That column is the planner's reading
of the Codex catalog, not OpenAI guidance on seats. It is unmeasured, and writing it into the role
files is later work.

## Gates on Codex

A gate counts only when WUWEI attests its verdict from the seat's own hand-back or SubagentStop. A
`codex-companion` task job started from a Claude session is not a seat: it has no SubagentStop, so
its verdict file sits unattested and `wuwei evidence` names it as not counted (#1078, #1181). Its job
id does not change that: a job id is not a hand-back the harness recorded. A Codex-native
seat (`spawn_agent` with `agent_type` `sentinel-<gate>`) goes through the same hooks, but its stop counts only
once WUWEI reads Codex's own transcript (hook-transcript records it as `seat.unconfirmed` until then). Run
gates as Claude seats.

A brief for a seat on Codex tells it not to use MCP tools. Codex can deny an MCP call without
asking, and a seat treats any denied call as a blocker, so one denial can stop a sound review.

**Breaking change (hook-transcript, #1172):** before it, a Codex `request_user_input` answer was
recorded as a ruling by its question and a Codex seat's stop was attested. Now both are recorded as
`answer.unconfirmed` and `seat.unconfirmed`, because WUWEI cannot yet read Codex's transcript to
confirm them. Ask owner questions (`owner review:`, `breaking:`, `exception:`, `plan:`, `goal:`) and
run gates from a Claude Code session, or approve on the code host. The rows name why, so nothing is
lost silently.

**Why:** the process is the product, not the harness. The same evidence, doors and questions hold
whichever agent does the work, and a team can run both without two rule books.

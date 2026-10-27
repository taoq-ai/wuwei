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
after an upgrade changes them. Codex runs hooks through your login shell (`$SHELL -lc`) on macOS and
Linux, and through `cmd.exe` on Windows, where it reads each hook's `commandWindows` entry:
`bin/wuwei.cmd`. That entry tries `WUWEI_PYTHON`, then `py -3`, then `python`, and needs Python
3.11 or newer, as `bin/wuwei` does. The login shell may put an older `python3` first, so if every
call is refused with "WUWEI needs Python 3.11 or later", set `WUWEI_PYTHON` to a 3.11 or later
interpreter where Codex starts, or install one as `python3.12` or `python3.13`. Run `wuwei init --codex` again after an upgrade too; `wuwei doctor`
warns while the role files differ from the charters.

## What maps to what

| Claude Code | Codex | How WUWEI reads it |
| --- | --- | --- |
| `Bash` | `Bash` (shell and exec) | the same command guards |
| `Write`, `Edit` | `apply_patch` | the files the patch adds, updates, deletes or moves to; the ledger stays protected |
| `Agent` with `subagent_type` | `spawn_agent` with a known `agent_type` and successful `agent_id` or `task_name` | a running seat; the Stop hook stays quiet while it runs |
| `AskUserQuestion` | `request_user_input` | the same owner classes; answers recorded as `answer.unconfirmed` until WUWEI reads Codex's transcript |
| `mcp__server__tool` | `mcp__server__tool` | the same leak and merge doors |
| SubagentStop | SubagentStop | recorded as `seat.unconfirmed`, with no attestation, until WUWEI reads Codex's transcript |
| `.claude/settings.json` rules | `.codex/rules/*.rules` | written by `wuwei init` and `wuwei init --codex` |

Inspect the active `spawn_agent` schema before dispatch. Supply `agent_type` only when supported;
a task name or role words in the message cannot supply a role. A successful identity without a
known explicit role is recorded as `seat.unconfirmed`, with a role-capability diagnostic.
Malformed or missing identities produce `hook.error` and no running seat. The adapter reads
object results and JSON object strings, preserving legacy `agent_id` and native `task_name`.
Native task paths keep the harness value; stops match them within their session.

The requested message, model and reasoning effort survive normalization. `asked` and `effort`
record the request; a brief's `Model:` line can name it when the schema has no override fields.
`model` records only a supplied provider-resolved child model, else `unmeasured`. The report shows
those settings separately from the launching parent's turn metadata and the requested fork policy.
A parent's model cannot measure a child's model. This telemetry does not attest a launch, stop or
verdict.

`wuwei init --codex` writes native role `model` and `model_reasoning_effort` defaults from the
[model table](models.md). Role files use the standard tier. Existing owner `models` rows override
the mapped table: role-and-standard before role alone. Regenerate after changing rows; doctor
uses the same configured comparison. The owner session keeps its settings.

Inspect the active tool schema before selecting an item's tier per call. Some surfaces omit
model overrides, and full-history forks can require inheritance. State the requested policy in the
brief when an override is unavailable. Explicit `fork_turns=all` records `fork policy: inherit`,
which describes the request; actual child resolution stays unmeasured without provider metadata.
The models page documents the deterministic catalog mapping and owner precedence. The mapping is
WUWEI policy, with delivery outcomes still unmeasured.

## Gates on Codex

A gate counts only when WUWEI attests its verdict from the seat's own hand-back or SubagentStop.
Gates never go to Codex: a gate run as a `codex-companion` task or a Codex seat never counts. A
`codex-companion` task job started from a Claude session is not a seat: it has no SubagentStop, so
its verdict file sits unattested and `wuwei evidence` names it as not counted (#1078, #1181). Its job
id does not change that: a job id is not a hand-back the harness recorded. A Codex-native seat
(`spawn_agent` with `agent_type` `sentinel-<gate>`) goes through the same hooks, but its stop is
recorded as `seat.unconfirmed` (#1172), so a Codex seat never counts either. Run gates as Claude
seats; builders and fix rounds may run on Codex.

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

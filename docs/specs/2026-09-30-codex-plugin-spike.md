# Spike: WUWEI as a Codex plugin

Issue #261, owner question of 2026-09-30: what would it take to install and run WUWEI as
a plugin for the OpenAI Codex CLI? Answered from Codex documentation and the installed CLI.

## Sources

Fetched or run on 2026-09-30. `developers.openai.com/codex/*` redirects (308) to
`learn.chatgpt.com/docs/*`; the target is cited.

| Id | Source |
|---|---|
| H | learn.chatgpt.com/docs/hooks |
| P | learn.chatgpt.com/docs/plugins; developers.openai.com/plugins/build/plugins |
| SA | learn.chatgpt.com/docs/agent-configuration/subagents |
| R | learn.chatgpt.com/docs/agent-configuration/rules |
| SK | learn.chatgpt.com/docs/build-skills |
| SEC | learn.chatgpt.com/docs/agent-approvals-security |
| CFG | learn.chatgpt.com/docs/config-file/config-reference |
| CLI | codex-cli 0.156.1: `--version`, `--help`, `exec --help`, `exec resume --help`, `plugin --help`, `features list` |
| I1 | github.com/openai/codex/issues/32491 (open): `codex exec` skips trusted hooks without `--dangerously-bypass-hook-trust` |
| I2 | github.com/openai/codex/issues/48715 (open): same, silently, on 0.157.1 |
| I3 | github.com/openai/codex/issues/23411 (open): Code Mode `exec` fires no PreToolUse |
| I4 | github.com/openai/codex/issues/26363 (closed): `spawn_agent` lost custom agent selection in 0.137.0 |
| AP | github.com/openai/codex `codex-rs/apply-patch/apply_patch_tool_instructions.md`: search index only, direct fetch 404 |

**Unverified** marks a claim no source above establishes, or one resting on AP.

## Hook contract (H)

Events: `SessionStart`, `SessionEnd`, `SubagentStart`, `SubagentStop`, `PreToolUse`,
`PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`,
`Stop`, `Interrupt`. Payloads carry `session_id`, `transcript_path` (string or null),
`cwd`, `hook_event_name`, `model`; PreToolUse adds `tool_name`, `tool_use_id`,
`tool_input`. PreToolUse blocks before the tool runs by exit 2 with the reason on stderr,
or by `hookSpecificOutput.permissionDecision: "deny"`, the shape WUWEI already prints.
Plugin hooks get `PLUGIN_ROOT` and `CLAUDE_PLUGIN_ROOT`. Hooks are on by default
(`hooks` stable in CLI). H calls tool hooks "a useful guardrail, not a complete
enforcement boundary", as spec 9.1 does.

Trust: a hook runs only after the owner trusts its exact definition in `/hooks`; project
hooks need a trusted `.codex/` layer (H). `codex exec` skips trusted project hooks unless
`--dangerously-bypass-hook-trust` is passed (CLI, I1, I2); trusted plugin hooks there:
**unverified**.

## Gap table

Size: S is one file with its table tests; M is several guards or one adapter with
contract tests (SLICE); L changes the seat launch contract (FULL).

| WUWEI feature | Claude Code | Codex | Consequence | Size | Source |
|---|---|---|---|---|---|
| Bash guards (commit, push, PR, deploy, state, outward) | PreToolUse `Bash`, `tool_input.command` | Same; covers shell and unified exec; `write_stdin` does not rerun PreToolUse; Code Mode: H says nested calls get hook decisions, I3 (open) reports they do not: **unverified** | Guards reuse unchanged; `write_stdin` is unguarded | S | H, I3 |
| Payload validation | `validate()` requires non-empty `transcript_path` (`cli/wuwei/commands/hook.py:96`) | `transcript_path` may be null | Null fails closed: every Codex PreToolUse in a workspace is denied | S | H |
| Refusal output | exit 2 plus deny JSON (`hook.py:103`) | Same | None | none | H |
| File guards (`protect_state.check_file`, decision, verdict) | `Write`, `Edit`, `MultiEdit`, `NotebookEdit` with `file_path` | `tool_name: "apply_patch"`, patch body in `tool_input.command` | One shared extractor reads targets from `*** Add File:`, `*** Update File:`, `*** Delete File:`, `*** Move to:` (relative to `cwd`); grammar **unverified** | M | H, AP |
| Seat launch guard (`agent_launch`) | PreToolUse `Agent`: `subagent_type`, `prompt`, `resume` | `spawn_agent` (H: also matches `Agent`); input `fork_context`, `items`, `message`, with `agent_type` dropped in 0.137.0 (I4) | **Unverified** that brief and role are checkable; until then no equivalent, seats use `wuwei build <item> <brief> <worktree>` | L | H, SA, I4 |
| Retro and verdict at seat stop | SubagentStop `agent_id`, `agent_type`, `last_assistant_message` | Same fields | Reusable if agents are named by role | S | H |
| Memory payload | SessionStart `additionalContext` | Same | None | none | H |
| Stop anchor (4.2.1) | Stop `decision: "block"` | Same; reason becomes a continuation prompt | Same effect | none | H |
| PreCompact flush | Exit 1 must not block compaction | Exits other than 0 and 2 undocumented | **Unverified** whether exit 1 blocks | S | H |
| Morning gate decisions | PreToolUse `AskUserQuestion` | None; `default_mode_request_user_input` under development | Questions become chat turns; decision guard never runs | M | CLI |
| Traces | PostToolUse, every tool | Not for hosted tools such as web search | Web search untraced | S | H |
| Outward lint on MCP | `mcp__<server>__<tool>` | Same format | Reusable | none | H |
| Hook trust | Plugin install enables hooks | Owner trusts in `/hooks`; `exec` needs the bypass flag (project hooks) | A `codex exec` seat may be unguarded unless the adapter passes the flag, which enables every untrusted hook too | M | H, CLI, I1, I2 |
| Plugin manifest | `.claude-plugin/plugin.json`, `hooks/hooks.json` | Root `plugin.json` or `.codex-plugin/plugin.json`; hooks from `hooks/hooks.json` | Second manifest; Codex reading our `args` array is **unverified**; `plugin_hooks` shows `removed` in `features list` | S | P, CLI |
| Marketplace | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json`, legacy `.claude-plugin/` accepted; `codex plugin marketplace add owner/repo` | One repository serves both | S | P, CLI |
| Role agents and allowlists | `agents/*.md` in the plugin | `.codex/agents/*.toml`; plugin bundling of agents undocumented (P, SA): **unverified** | `wuwei init` writes them; no allowlist key among SA's listed fields, so the ZIRAN role-grant audit has nothing to read | M | SA, P |
| Skills | `skills/*/SKILL.md` | Same format, invoked with `$` | Text ports; `${CLAUDE_SESSION_ID}` (`skills/wuwei-plan/SKILL.md:10`) has no documented equivalent | S | SK |
| `permissions.deny` | `.claude/settings.json` | `prefix_rule(decision="forbidden")` in `rules/*.rules`, experimental, for commands outside the sandbox | **Unverified** inside the sandbox | S | R |
| Status line | `statusLine` command | `tui.status_line`, built-in items only | None; cockpit and menu bar remain | none | CFG |
| `CLAUDE.md` | Project memory | `AGENTS.md` | Same text, other file | S | CFG |
| Seat isolation | Claude seats unsandboxed (9.1) | `workspace-write` keeps `.git`, `.agents`, `.codex` read-only; network off | A seat cannot commit, push or edit its hooks; stronger than hooks | none | SEC |
| Signed manifest | Plugin root beside `bin/wuwei` | Cache `$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/`; no signing | Integrity verifies `MANIFEST.sha256` from there; Codex adds nothing | S | P |

## Planner without the Agent tool

`adapters/runtime/codex.py` drives the companion in `codex.command`: `task --fresh
--background [--write]` (line 49), `status` with a workspace-root check that cancels on
mismatch (line 67), `result` with retro and verdict lint (line 107), continuation by
`task --resume-last` (line 154). `wuwei build <item> <brief> <worktree>` polls it
(`run_loop`, `cli/wuwei/commands/build.py`). The companion ships with a Claude Code plugin;
a Codex-only host may lack it, but `codex exec --json`, `-o`, `--sandbox workspace-write`
and `codex exec resume <SESSION_ID>` offer the same primitives (CLI).

The daily path loses:

- parallel gate seats in one planner turn: the planner polls jobs through its shell
  instead of three `Agent` calls received on SubagentStop;
- SubagentStop-recorded fast checks: reuse lives in `build.stopped()`, called only from
  the SubagentStop hook (`guards/agent_launch.py:229`), so each Codex iteration runs a
  separate `check`;
- resume by identity: gate seats share the item's worktree, so `--resume-last` may resume
  the wrong sentinel (**unverified** against the companion); `exec resume <SESSION_ID>`
  removes that.

`spawn_agent` could restore parallel seats if its input carries brief and role
(unverified; I4 shows that surface changing within one minor release).

## Recommendation: partial port, not the planner

Port the guard layer so Codex sessions and seats in a WUWEI workspace get the Bash, file
and MCP guards; keep the planner on Claude Code. The hook contract matches Claude Code's
(event names, deny JSON, `CLAUDE_PLUGIN_ROOT`), so guards need two payload changes. The
planner does not port: its launch contract keys on undocumented `Agent` input, its morning
gate on `AskUserQuestion`, and headless hooks need a flag the CLI calls dangerous.

Where a Codex hook cannot block before the tool runs (`codex exec` without the flag,
`write_stdin`, Code Mode per I3, hosted tools), enforcement loses the refusal at the moment of
action for: commit and push identity, force-push, push before fast checks, PR raise
without gates, merge outside the policy, approve and `--admin`, deploy verbs, direct
writes to `state.json` and `events.jsonl`, seat launch without a brief, and the
outward-text lint. What holds, per 9.1: protected refs and required checks on the code
host, credentials kept out of seats, the `pre-push` hook in WUWEI worktrees, and the Codex
sandbox keeping `.git` read-only for seats. Traces and the Stop anchor still record where
hooks run.

## Follow-up issues if the port goes ahead

1. fix(hook): accept Codex payloads: null `transcript_path`; `apply_patch` targets through
   one extractor shared by `protect_state`, `decision` and `verdict`; recorded Codex
   payloads under `tests/payloads`. M.
2. feat(packaging): Codex manifest and hooks entry beside `.claude-plugin/`; `AGENTS.md`
   and execpolicy rules from `wuwei init`; trust steps in the install docs. S.
3. feat(runtime): Codex adapter on `codex exec --json`, resume by session id, hooks
   enabled only after `wuwei integrity` is clean. M.
4. docs(spike): Codex-hosted planner once `spawn_agent` input and a user-question tool are
   documented. L.

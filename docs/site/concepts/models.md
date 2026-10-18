# Models and effort

Each seat runs on the model and effort its work needs. The planner charter holds one table for
every repository running WUWEI (`charters/planner.md`, "Model and effort"). The planner follows it,
departs from it with a recorded reason, and is never refused. WUWEI advises; you decide.

**Why:** a seat on too weak a model costs fix rounds and escaped defects; a seat on too strong a
setting costs tokens for nothing. One written table makes the choice the same each time, and the
retro can measure it.

## The inputs

The table reads only signals WUWEI already computes for every item:

- the item's tier (`light`, `standard`, `full`), after the change failure rate rule raises it a
  step;
- risky, owner or contract paths: the risky paths, the owner paths and the contract files the diff
  touches (a wider set than the trust paths that raise a light item to standard);
- the item's history: failed fix rounds, gate blockers the builder missed, a park for a design
  problem, a one-way decision.

## Why each row

| Seat | Setting | Why |
| --- | --- | --- |
| lead | Opus 5.5 xhigh | ranking and red-teaming the plan is long-horizon reasoning, and a wrong plan wastes every seat after it |
| builder | Sonnet 5.5 medium at light, Opus 5.5 medium at standard, Opus 5.5 high at full or on risky, owner or contract paths | Sonnet 5.5 is Anthropic's choice for everyday coding; Opus 5.5 for complex agentic coding; those paths are intelligence-sensitive |
| sentinel-security | Opus 5.5 high, xhigh at full or on risky, owner or contract paths | a missed trust defect is the costliest escape |
| sentinel-arch | Opus 5.5 high | coupling and contracts need reasoning across the whole design |
| sentinel-quality | Sonnet 5.5 high, Opus 5.5 high at full or on risky, owner or contract paths | a second model family on routine heads; the stronger model where a missed test costs most |
| sentinel-goal | Sonnet 5.5 high | reads the promise against the diff; a different model than the builder at full |
| shepherd | Sonnet 5.5 medium, Opus 5.5 high for a conflict where both sides changed logic | most PR work is routine; a logic conflict is not |
| steward | Opus 5.5 high | the retro weighs evidence across the day |
| lookups and searches | Haiku 5.5 low | Anthropic names Haiku 5.5 for simple, speed-critical work and low effort for simple subagent tasks |

Where two settings in a row apply, the later one holds. The session's own model is yours. The table
never names it.

## Escalation and diversity

The ladder runs Haiku 5.5, Sonnet 5.5, Opus 5.5 at medium, high and xhigh, then Fable 5.1. A seat
moves up one step after a failed fix round or after a gate finds a blocker the builder missed.
Fable 5.1, Anthropic's most capable model, is the step for an item parked as a design problem (two
failed fix rounds) and for a one-way decision. Under zero data retention Fable may be unavailable;
there the top step is Opus 5.5 at max. A step never lowers effort: Sonnet 5.5 at high steps to Opus
5.5 at high.

A seat class steps down only on retro evidence: 10 merged items on the lower setting with no
escaped defect. The count makes the rule testable.

At least one gate per head runs on a different model than the builder, so the reviews do not share
every blind spot. When the table would put every gate on the builder's model (a light item, or a
standard item on risky, owner or contract paths), the quality gate takes the other of Opus 5.5 and
Sonnet 5.5, at high.

After a fix, a delta is re-read by one gate, and the passes from the earlier head carry to it. Those
carried passes count toward diversity, so the gate that re-reads keeps its own model. The limit: if
the gate on the other model passed the earlier head and the fix changed what it read, the delta has
no fresh review from another model.

Haiku 5.5, the weakest tier, never runs a gate on risky, owner or contract paths. That floor is not a
departure the planner can record with a reason: breaking it is an `exception:` for you.

## Effort

- Set effort on every call. Opus 5.5 defaults to medium, and defaults differ between models and
  between the API and Claude Code (Sonnet 5.5 is high on the API, medium in Claude Code).
- Use at least high for intelligence-sensitive work, max when correctness matters more than cost,
  and low for simple subagent tasks.
- Before moving a seat to a cheaper model, measure the stronger model at a lower effort. Anthropic
  reports that tuning effort is often a better lever than switching models.
- Judge cost per completed item, not per request: a cheap seat that needs a second round costs
  more.

## How Claude Code applies it

- The planner passes `model` and `effort` on each Agent call, with full model IDs
  (`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1`). A family alias
  such as `opus` can resolve to the session's own model when it is in that family, and `sonnet`
  resolves to an older version on some providers. The per-call `effort` parameter needs Claude
  Code v2.1.292 or later.
- On Amazon Bedrock, Google Cloud's Agent Platform and Microsoft Foundry, model IDs are the
  provider's own, so `claude-sonnet-5-5` may not resolve and the seat can fall back to the session's
  model without notice. There, set your `models` rows to the provider's IDs, or pass the aliases
  with `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL` and
  `ANTHROPIC_DEFAULT_HAIKU_MODEL` pinned.
- The brief's first line is `Model: <model> <effort> (<row>)`. A departure adds
  `Model reason: <one line>`.
- Model precedence: the call's `model` parameter, then the agent file's `model` frontmatter, then
  `CLAUDE_CODE_SUBAGENT_MODEL`, then the session model. Four cases change that order:
  - setting `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` puts the variable first;
  - before Claude Code v2.1.251, the variable came first anyway;
  - an installed mod that sets a model in its `agent.spawn` hook replaces the per-call parameter;
  - a value your organization's `availableModels` blocks is substituted: a family alias takes the
    newest permitted version of that family, and a full ID runs on the session's model.
- Effort precedence: `CLAUDE_CODE_EFFORT_LEVEL` beats every other effort setting, the per-call
  parameter included. A workspace that sets it turns WUWEI's effort advice off. A managed
  `maxEffortLevel`, or an organization effort cap, still limits the level a seat runs at.
- What a hook can see: the Agent call's `tool_input` carries `model` but not `effort`, so the brief's
  first line records the effort asked for. What ran is visible too: the PostToolUse response
  carries `resolvedModel`, the model the seat started on, and PreToolUse, PostToolUse, Stop and
  SubagentStop inputs carry `effort.level`, the level in effect (also `$CLAUDE_EFFORT` in Bash).
- Your own `models` rows in `.wuwei/config.toml` override any table row.
- `/wuwei-watch` may run on Sonnet 5.5 at medium effort through its own frontmatter. The skill offers
  that as an option, not a default.

## On Codex

The same table holds on Codex. The Codex column is the planner's reading of the Codex catalog:

| Claude | Codex |
| --- | --- |
| Fable 5.1 | gpt-6-astra |
| Opus 5.5 | gpt-6.1-sol |
| Sonnet 5.5 | gpt-6.1-sol at a lower effort, or gpt-6-luna for checklist seats |
| Haiku 5.5 | gpt-6-luna low |

It reads the descriptions in Codex's model catalog ("frontier intelligence for
the most demanding work", "latest workhorse model for coding and everyday work", "fast and
affordable model for easier tasks"). It is not OpenAI guidance on seats, and it is unmeasured: no
outcome on Codex has been recorded against it.

- Effort keeps the same names. gpt-6-astra and gpt-6.1-sol add `ultra` above `max` ("maximum
  reasoning with automatic task delegation"), the Codex top step; gpt-6-luna stops at `max`. The
  catalog's default is `low` on gpt-6-astra and gpt-6.1-sol and `medium` on gpt-6-luna, so set
  effort here too.
- A role file (`.codex/agents/<role>.toml`) accepts `model` and `model_reasoning_effort`, and the
  `[agents]` config sets `default_subagent_model` and `default_subagent_reasoning_effort` for
  spawned agents.
- `spawn_agent` takes `model` and `reasoning_effort` only when the workspace turns on
  `expose_spawn_agent_model_overrides` (off by default). Its own guidance tells the model that
  spawned agents inherit the current model and not to set `model` unless the user asks.
- The role files `wuwei init --codex` writes still name no model; writing the table into them is
  later work.

## Learning from it

At each close the steward reads outcomes by seat, model and effort: fix rounds, blocking findings,
escapes and tokens per merged item. Where the numbers back it, the retro proposes a change to a row,
with those numbers, as advice. See [the learning loop](learning.md).

## Sources

The model ids and effort values above are the ones these pages name.

- [Choosing the right model](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model), Anthropic, read 2026-10-18: the selection matrix (Fable 5.1 for the highest capability, Opus 5.5 for complex agentic coding, Sonnet 5.5 for everyday coding and agent work, Haiku 5.5 for the lowest latency and sub-agent tasks), and effort as often a better lever than switching models.
- [Models overview](https://platform.claude.com/docs/en/models/overview), Anthropic, read 2026-10-18: start with Opus 5.5 for most workloads, Fable 5.1 for demanding reasoning and long-horizon agentic work, and the API model ids.
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort), Anthropic, read 2026-10-18: Opus 5.5 and Haiku 5.5 default to medium, set effort explicitly, low for simple subagent tasks, Sonnet 5.5 starts at medium for agentic coding.
- [Optimizing for cost and intelligence](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence), Anthropic, read 2026-10-18: compare models on cost per completed task, and sweep effort on the current model, then price the stronger model at low effort, before adding a second model.
- [Subagents](https://code.claude.com/docs/en/sub-agents), Claude Code, read 2026-10-18: the model order and the cases that change it (`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, v2.1.251, a mod's `agent.spawn`, `availableModels`), the `effort` frontmatter field and per-call parameter, and family alias resolution.
- [Model configuration](https://code.claude.com/docs/en/model-config), Claude Code, read 2026-10-18: aliases and the `ANTHROPIC_DEFAULT_*_MODEL` pins, provider-specific model IDs, the effort resolution order with `CLAUDE_CODE_EFFORT_LEVEL` first, `maxEffortLevel`, and the effort levels each model supports.
- [Hooks](https://code.claude.com/docs/en/hooks), Claude Code, read 2026-10-18: the Agent tool input fields (`model`, no `effort`), `resolvedModel` in the PostToolUse response, the common `effort.level` input field and `$CLAUDE_EFFORT`, and the 10,000-character cap on hook context.
- [Skills](https://code.claude.com/docs/en/skills), Claude Code, read 2026-10-18: a skill's `model` and `effort` frontmatter, which hold for the rest of the turn.
- [Plugin components](https://code.claude.com/docs/en/plugins/components), Claude Code, read 2026-10-18: a plugin agent's frontmatter supports `model` and `effort`.
- [Codex model catalog](https://github.com/openai/codex/blob/8c07694/codex-rs/models-manager/models.json), OpenAI Codex source at commit 8c07694, read 2026-10-18: the model descriptions, effort levels and defaults. Codex's source stands in for OpenAI documentation here.
- [Codex agent roles](https://github.com/openai/codex/blob/8c07694/codex-rs/core/src/agent/role.rs), OpenAI Codex source at commit 8c07694, read 2026-10-18: a role file's `model` and `model_reasoning_effort` overrides.
- [Codex spawned agent config](https://github.com/openai/codex/blob/8c07694/codex-rs/core/src/agent/child_config.rs) and [spawn_agent tool text](https://github.com/openai/codex/blob/8c07694/codex-rs/core/src/tools/handlers/multi_agents_spec.rs), OpenAI Codex source at commit 8c07694, read 2026-10-18: the `[agents]` defaults, the per-call overrides and their exposure flag, and the inherit-by-default guidance.
- [Zero data retention](https://code.claude.com/docs/en/zero-data-retention), Claude Code, read 2026-10-18: Fable 5.1 requires data retention by default, so a zero data retention organization may not reach it.

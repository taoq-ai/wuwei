# Feature Specification: agent files carry the table's model and effort, the hook advises on a departure and records what ran, and the report shows outcomes by model and effort

**Feature branch**: `feat/models-record`
**Item**: models-record, tier full, goal G-3
**Input**: the runtime slice of the model table that #1138 wrote into `charters/planner.md`
("Model and effort") and `docs/site/concepts/models.md`. The owner's words: guidance "as sensei,
not dictate", one framework for every repository running WUWEI. So the hook advises and records;
it never denies and never sends `updatedInput`.

## The promise in my words

1. `cli/wuwei/agents.py` holds one `TABLE`: per role a default setting, the setting at a tier
   where the row names one, the setting on risky, owner or contract paths, and the shepherd's
   setting for a logic conflict. `MODELS` is gone. `wuwei agents build` writes `model:` (the full
   model ID) and `effort:` into each `agents/<role>.md` from the role's default. A test reads the
   planner table and checks `TABLE` against it at every tier, on and off those paths.
2. On an Agent launch, the PreToolUse hook reads the role, the model and effort asked for, and the
   item the brief names (`Item: <id>`), and from it the tier, raised one step when the cached
   change failure budget says so. When the launch departs from every setting the table allows
   there, and the brief has no `Model reason:` line, it returns `additionalContext`:
   "table says <model> <effort> for <role> at <tier>; record a 'Model reason:' line in the brief".
   It never returns a permission decision and never `updatedInput`. A Haiku gate is advised even
   with a reason line, since the floor is not a departure a reason can cover; an owner `models`
   row that sets Haiku is the owner's exception and gets no advice.
3. The PostToolUse hook records on `seat.started` the model that ran (`resolvedModel`), the model
   and effort asked for (`unrecorded` when absent), the brief's `Model reason:` line and the item.
   `seat.stopped` records the `effort.level` the SubagentStop input carries (`unmeasured` when
   absent). A gate's `attest` row copies `model` and `effort` from the `seat.started` row with the
   same agent id, and records how many blocking findings the verdict holds.
4. `.wuwei/config.toml` takes a sixth key, `models`: a table of `"<role>[ <tier>]" =
   "<model> <effort>"`. A row for the role and tier, else for the role, replaces the table's
   settings. Every "five keys" statement says six.
5. `wuwei doctor` names `CLAUDE_CODE_EFFORT_LEVEL` and `CLAUDE_CODE_SUBAGENT_MODEL` when set and
   says effort or model advice is then off; the hook skips that half of the comparison.
6. The report's Learning section has one line per seat x model x effort: launches, fix rounds per
   item, blocking findings, escapes traced to a passing gate, tokens, and a line
   "model or effort unrecorded on <n> launches".
7. Codex: a `spawn_agent` launch records `unmeasured` and `unrecorded`, and gets no advice. The
   Codex column of the models page is not rendered into Codex role files (outside this item).

The acceptance scenarios, restated:

1. Given the head, when `bin/wuwei agents build` runs, then every `agents/<role>.md` has the
   table's `model:` and `effort:` lines, `git status` is clean, and `agents.py` defines no `MODELS`.
2. Given a PreToolUse Agent payload for `sentinel-goal` with model `opus` on a standard item, when
   `hook.handle` runs, then it returns `additionalContext` naming "Sonnet 5.5 high" and the
   `Model reason:` line, with no `permissionDecision`.
3. Given a PreToolUse Agent payload that matches the table, when `hook.handle` runs, then it
   returns nothing.
4. Given a PostToolUse Agent payload with `resolvedModel` `claude-opus-5-5`, effort `high` and a
   brief holding `Model reason: conflict in logic`, when `hook.handle` runs, then `seat.started`
   holds that model, effort and reason, and the seat's later `attest` row the same model and
   effort.
5. Given `models = {"builder light" = "opus medium"}`, when the hook reads a light builder launch
   on opus medium, then it gives no advice. Given `CLAUDE_CODE_EFFORT_LEVEL=low`, when
   `wuwei doctor` runs, then it names the variable and says effort advice is off.
6. Given a ledger with gates on two models, when `wuwei report` runs, then Learning shows one line
   per seat x model x effort with launches, fix rounds, blocking findings, escapes and tokens.

## How this fails

1. Advice that is wrong. At launch the hook cannot see the diff's paths or whether a conflict
   changed logic, so it would advise a builder on Opus 5.5 high at standard that is on a risky
   path. Held: a launch that fits any setting the row allows at that tier (the tier's own, the
   paths setting, the conflict setting) gets no advice, and the advice names the paths setting
   too. A brief with no `Item:` line reads as standard. A family match ("opus" in
   `claude-opus-4-1`) passes an older version as a fit; the record keeps `resolvedModel`, so the
   retro sees it.
2. A model ID that does not resolve. The frontmatter names `claude-opus-5-5`; on Amazon Bedrock,
   Google's Agent Platform or Microsoft Foundry the provider's IDs differ, and a seat launched with
   no `model` parameter may fall back to the session's model without notice. Main has the same
   fallback for seven roles (no frontmatter model) and an alias for one. The planner passes
   `model` on each call, and the models page tells those workspaces to set their `models` rows or
   pin the aliases.
3. A record that misleads. A foreground launch's PostToolUse fires after the seat ended, so its
   `attest` row is written before `seat.started` and copies `unrecorded`; the report joins by agent
   id and still groups it. `effort.level` at SubagentStop may be the level of the session that
   fired the hook rather than the seat's: it is recorded on `seat.stopped` only, and the report
   groups by the effort asked for.
4. An older plugin reading a new config. `write_config` now writes `models = {}`; WUWEI before
   this item lists `models` as a retired key and asks for `wuwei init`. Rollback reverts the
   commit; the extra key is then the only trace.

## Clarifications

### Session 2026-10-18

- Q: Which setting is a role's default for the frontmatter? A: The row's setting with no
  condition, and for the builder, whose row has none, the standard one (Opus 5.5 medium), since
  standard is the plan's default tier.
- Q: Does the hook advise on the effort when the Agent input has none? A: It reads the call's
  `effort`, else the brief's `Model: <model> <effort>` line, else the agent file's effort (the
  frontmatter Claude Code then applies). A session transcript on 2026-10-18 shows the Agent
  `tool_use` input carries `effort` when the planner passes it; the hooks page lists only `model`.
  The new fixture `claude-agent-post-model-effort.json` holds that shape.
- Q: Does the hook advise when the call names no model? A: It compares the agent file's model,
  which is what Claude Code runs then.
- Q: Which model does a launch record? A: `model` is `resolvedModel`, what ran (`unmeasured` when
  absent); `asked` is the call's `model` (`unrecorded` when absent). The report groups by `model`.
- Q: What is a fix round per item? A: For a seat x model x effort group, launches on an item past
  the first, averaged over the items the group's launches name. Escapes count the group's gates
  that passed a PR later reverted.
- Q: Does `CLAUDE_CODE_SUBAGENT_MODEL` turn model advice off? A: Yes, as the promise says. By
  Claude Code's order the call's `model` still wins over it, but a workspace that sets it has
  chosen its model; the doctor names it so the owner knows.
- Q: Are Codex seats advised? A: No. A Codex `spawn_agent` call carries no model by default and
  the mapped payload has no brief; it records `unmeasured` and `unrecorded`.
- Q: Does `wuwei config models ...` set the key? A: Yes: `wuwei config models "builder light=opus
  medium, shepherd=sonnet high"`, the same comma list the list keys take.

## User Scenarios & Testing

### US1: agent files carry the table's defaults (P1)

Acceptance 1, and a test that `TABLE` agrees with the planner table at every tier on and off the
paths.

### US2: the hook advises on a departure and stays quiet on a fit (P1)

Acceptance 2, 3 and 5 (first half). Also: a reason line silences the advice except for a Haiku
gate; an owner row for Haiku silences it; a raised tier is read from the cached budget; a Codex
spawn and a non-WUWEI role get none; the environment variables turn each half off.

### US3: what ran is recorded (P1)

Acceptance 4, a Codex spawn recorded as `unmeasured`, and `seat.stopped` carrying `effort.level`.

### US4: the owner's rows and the sixth key (P1)

Acceptance 5, `wuwei config models` parsing, and `retired()` not naming `models`.

### US5: the doctor and the report (P1)

Acceptance 5 (second half) and 6.

## Requirements

- FR-001: `agents.TABLE` replaces `MODELS`; `render` writes `model:` and `effort:` from it.
- FR-002: `hook.pre_tool` returns advice as `additionalContext` only, on an Agent launch outside
  the allowed settings with no reason line, or a Haiku gate.
- FR-003: `seat.started` holds `model`, `asked`, `effort`, `reason`, `item`; `seat.stopped` holds
  `effort`; `attest` holds `model`, `effort`, `blocking`.
- FR-004: `ws.DEFAULTS` holds `models`; `config`, `write_config`, `set_config` and `retired`
  handle it.
- FR-005: `setup.doctor` names the two environment variables when set.
- FR-006: `report.learning` prints the seat x model x effort lines and the unrecorded count.
- FR-007: runtime grows by at most 40 lines (the item's budget) and stays at 3,400 or fewer.

## Assumptions

- The hook's Agent `tool_input` is the call's input, so it holds `effort` when the call passes one
  (from the session transcript). Overturned by captured hook stdin without it; the brief's
  `Model:` line then still gives the effort.
- The cached budget (`budget-<repo>`, one day) is the hook's only source for the raise; with no
  cache the tier stays as planned, so the hook never calls the code host. Overturned if the owner
  wants the hook to read the code host on a launch.
- A family match is a fit (`opus` fits Opus 5.5). Overturned if version drift shows in the record.
- `CLAUDE_CODE_SUBAGENT_MODEL` set turns model advice off (the promise's words, though the call's
  `model` still wins). Overturned by the owner.

## Rollback

Revert the commit, rebuild `agents/` and re-vendor `.claude/`. Rows already written keep fields
readers ignore; a `models = {}` line in a config is then listed as retired.

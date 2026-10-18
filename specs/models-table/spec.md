# Feature Specification: one model and effort table for every seat, drawn from Anthropic's guidance

**Feature branch**: `models-table`
**Item**: models-table, tier full, goal G-3
**Input**: the owner's words: WUWEI should guide model choice "as sensei, not dictate", for every
repository running WUWEI, with a specific framework rather than open-ended advice, and a default
table drawn from Anthropic's docs. Mid-build the planner added Codex catalog facts read from the
openai/codex source at commit 8c07694.

## The promise in my words

Charter, skill, test and docs text only. Runtime lines: 0 (2,976 before and after,
`wc -l cli/wuwei/*.py`).

1. `charters/planner.md` gains "Model and effort": a table with one row per seat in
   `agents/allowlist.json` plus lookups, from signals WUWEI already computes (tier after the change
   failure rate raise, risky and owner paths, contract files).
2. The same section states the escalation ladder (Haiku 5.5 up to Fable 5.1, Opus 5.5 max where
   Fable is unavailable), when to step up and down, the diversity rule, the effort notes, the
   precedence Claude Code documents, the owner's override, and how the brief records the choice
   (`Model:` first line, `Model reason:` on a departure). Nothing is refused.
3. `docs/site/concepts/models.md` gives the reasons per row and the sources, each with the date it
   was read. `team.md`, `codex.md` and `docs/design.md` section 3 point to the table instead of
   `MODELS`; `MODELS` itself stays for models-record.
4. `steward.md` reads outcomes by seat, model and effort and proposes row changes as advice.
   `/wuwei-watch` offers Sonnet 5.5 medium as an option, not a default.
5. Codex: a step-by-step mapping to Codex models, marked unmeasured and named as a reading of
   Codex's catalog, not OpenAI guidance. Role-file rendering stays for models-record.

Outside: frontmatter generation, hook advice, recording and the report (models-record); any refusal
on a model; `cli/wuwei/agents.py`.

The acceptance scenarios, restated:

1. Given `charters/planner.md` at the head, when a reader looks for model choice, then it holds a
   row for each allowlisted seat, the ladder ending in Fable 5.1 (Opus 5.5 max without it), the
   diversity rule and the precedence naming both environment variables.
2. Given the head, when `tests/test_charters.py` runs, then a test finds every allowlisted role in
   the planner table.
3. Given `models.md`, when a reader follows its sources, then each names the document and the date
   it was read.
4. Given `team.md` and `codex.md`, when a reader looks for `MODELS`, then neither names it, both
   link the table, and `codex.md` marks the Codex mapping unmeasured.

## How this fails

1. The table never reaches the planner. `hook.session_start` injects `_way.md`, `_common.md` and
   `planner.md` as one `additionalContext` string, and Claude Code caps that at 10,000 characters:
   over it, the session gets a file path and a 2,000-character preview (code.claude.com hooks,
   read 2026-10-18). Measured with an empty workspace: 12,695 characters at main and 16,168 at the
   head (`ss_len.py` over `hook.session_start`). Not held here: the whole planner charter already
   sits past the preview on main, the fix is runtime in `hook.py`, and it is raised as a
   candidate item. This item adds 3,473 characters to an already truncated string.
2. Effort is silently not applied: the per-call `effort` parameter needs Claude Code v2.1.292 or
   later, and `CLAUDE_CODE_EFFORT_LEVEL` beats it, so a seat runs at Opus 5.5's medium default
   while the brief says high. Held in part: the charter and page name both cases; hooks cannot see
   effort (the Agent input has no `effort` field), so the brief's `Model:` line is the record, and
   models-record measures the resolved model.
3. Diversity silently fails through aliases: `sonnet` resolves to Sonnet 4.5 on Bedrock, and a
   family alias resolves to the session's own model when it shares the family. Held: rule 1 asks
   for full model IDs, and the page says why.

## Clarifications

### Session 2026-10-18

- Q: Are contract files trust paths? A: Yes for this table. The promise lists contract files among
  the inputs and the charters already give them arch at any tier; the table names one term, "trust
  paths", for risky paths, owner paths and contract files. Recorded under Assumptions.
- Q: The table puts every gate on the builder's model at light (Sonnet builder, Sonnet quality) and
  at standard on a trust path (all Opus). How does the diversity rule resolve it? A: The quality
  gate takes the other of Opus 5.5 and Sonnet 5.5, at high. The page names both cases.
- Q: "The weakest tier never sits on the terminal gate for a trust path." Which gate is terminal?
  A: Any gate can be the last to pass, so the charter says Haiku 5.5 never runs a gate on a trust
  path. Stricter, and testable.
- Q: Which model names does the Agent call take? A: Full IDs (`claude-opus-5-5`,
  `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1`), read from Anthropic's models
  overview. Aliases are accepted too, but resolve to the session's model or an older version in the
  cases sub-agents.md names.
- Q: Sonnet 5.5's default effort? A: `high` on the API (effort page) and `medium` in Claude Code
  (model-config page). The charter says to set effort on every call, so the difference does not
  matter to a seat; the page names it.
- Q: The brief said Codex model selection is unverified. The planner then sent Codex catalog facts
  from the openai/codex source at 8c07694. A: I re-read `models.json`, `role.rs`,
  `child_config.rs`, `config/mod.rs` and `multi_agents_spec.rs` at that commit: the descriptions,
  effort levels, defaults, role-file keys, `[agents]` defaults and the `expose_spawn_agent_model_overrides`
  flag (off by default) all match. The mapping goes in, marked unmeasured. The "at most 5
  overrides" detail is `MAX_SPAWN_AGENT_MODEL_OVERRIDES = 5`; its exact meaning is not in the text,
  so the page does not state it.
- Q: The promise cites Anthropic's model table "as cached 2026-10-06". A: I read the live pages on
  2026-10-18 and cite that date; the page says the item named the earlier copy.

## User Scenarios & Testing

Red first, reproduced on `git archive origin/main` (efcd9e7) with the head's
`tests/test_charters.py` copied in, `pytest -q tests/test_charters.py`: `6 failed, 79 passed`
(five tests written first, then the Codex test after the planner's message, each run red before
the text). Green at the head: `pytest -q` gives `1690 passed, 2 skipped`.

- US1 (P1), acceptance 1 and 2: `test_the_planner_table_names_a_model_and_effort_for_every_seat`,
  `test_the_planner_states_the_ladder_the_diversity_rule_and_the_precedence`.
- US2 (P1), acceptance 3: `test_the_models_page_names_and_dates_every_source`.
- US3 (P1), acceptance 4: `test_the_team_and_codex_pages_and_the_design_link_the_table_instead_of_models`,
  `test_the_planner_maps_each_step_to_a_codex_model_and_marks_it_unmeasured`.
- US4 (P2), the steward and watch notes:
  `test_the_steward_reads_outcomes_by_model_and_effort_and_the_watch_may_run_cheaper`.

## Requirements

- FR-001: `planner.md` "Model and effort" holds a row per allowlisted seat and lookups (promise 1).
- FR-002: the ladder, step rules, diversity, effort notes, precedence, override and brief lines
  (promise 2).
- FR-003: `models.md` with reasons and dated sources; nav and concepts index entries (promise 3).
- FR-004: `team.md`, `codex.md`, `design.md` section 3 link the table and name no `MODELS`
  (promise 3).
- FR-005: `steward.md` rule 6 and the `/wuwei-watch` option (promise 4).
- FR-006: the Codex mapping, unmeasured (promise 5).
- FR-007: `agents/` rebuilt, `.claude/` re-vendored; runtime lines unchanged.

## Assumptions

- Trust paths include contract files. Two-way: one word in the charter. Overturned if the owner
  wants a contract-only change on Sonnet gates.
- Full model IDs and the effort values `low` to `max` are what the Agent tool accepts, as the
  sub-agents page documents. Overturned if a launch with them is rejected; the page then names the
  aliases.
- The owner's `models` rows in `.wuwei/config.toml` do not exist until models-record lands; the
  rule names them now so the charter does not change twice. Overturned if models-record names the
  key differently.
- The Codex mapping is the planner's reading of the catalog descriptions, which the planner asked
  for in its message. Overturned by outcomes on Codex or by OpenAI guidance on seats.

## Rollback

Rollback: revert the commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. Text only:
no runtime, config, ledger or format change.

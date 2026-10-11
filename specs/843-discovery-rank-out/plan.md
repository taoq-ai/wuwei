# Implementation Plan: delete discovery intake, the spec guard and rank; the spec check stays in dispatch

**Branch**: `b7-leftovers` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at d60253b8. **[after 17]**: part 17 (#839) rewrites `guards/__init__.py`,
`tests/test_hooks.py`, `tests/test_enforce.py` and `tests/test_guard_mutation.py`; locate by
name. Parts 18 to 20 run first on this branch: `plan.py`, `commands/next.py`, `watch.py`,
`dispatch.py`, `tracker.py` and the lead and planner charters changed; locate by function name.

## Summary

Delete the intraday intake path end to end, the PreToolUse spec guard and the `rank` command.
Keep morning discovery, the ranking inside `plan propose`, the spec step recorder, the builder
stop check, and the spec-before-gates checks in `dispatch.next_step` and the build loop.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: about 300 lines of code, 900 of tests.
One config table retires.

## Constitution Check

- I: nothing added. II: one guard goes; the others keep their exits. III: one ordering
  function (`rank.rank` in `plan propose`). IV: red test first for the dispatch spec cases that
  are new (standard refusal named, light pass) and for `plan template` after the move.
  V: deletion. VII: no publishing edge changes.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Watch sweep discovery and intake, seat-free request, `pending_discovery`, `dispatch discovery` | (a) | nowhere; morning discovery stays; the owner adds mid-day work with `plan add --goal` |
| `plan add` discovery branch, `start_decision`, `discovery.autostart`, `intraday_proposals`, the morning carry | (a) | nowhere |
| `guards/spec.check_edit` (PreToolUse) | (a) for edits | the spec-before-gates check (b) stays in `dispatch.next_step` and `build.complete_checks` |
| `wuwei rank` | (a) a preview | `plan propose` orders by the framework (already, `plan.py:277`) |

No (b) check is lost.

## Files to delete (1 code file)

- `cli/wuwei/commands/rank.py` (move `candidate_template` first)

## Files to edit, code (15)

- `cli/wuwei/commands/plan.py:65`: define `candidate_template(goal, framework)` here (moved
  verbatim) and use it.
- `cli/wuwei/discovery.py`: delete `start_decision` (39-64), `when_seat_frees` (224-228),
  `intake` (231-276); docstring "Read discovery sources through ports for the morning plan";
  drop imports only they used (`fnmatchcase`, `re`, `DAMAGED` if unused).
- `cli/wuwei/commands/discover.py`: docstring says morning discovery.
- `cli/wuwei/dispatch.py:1126-1142`: delete `discovery`.
- `cli/wuwei/commands/dispatch.py:11, 24-25, 51`: delete the `discovery` subcommand.
- `cli/wuwei/guards/agent_launch.py:441-452` (`stop`): delete the seat-free request and its
  `discovery.unmeasured` branch.
- `cli/wuwei/watch.py`: `sweep` (207-215, 226-233) drops discovery and intake and their
  counts; `tick` (534) returns `result`; delete `pending_discovery` (537-553); drop the
  `discovery` import (7).
- `cli/wuwei/plan.py`:
  - `propose`: delete the `intraday_proposals` carry (239-249); rename the plan section
    "## Discovery intake" to "## Discovered" (315);
  - `add`: delete the `discovery_candidates` branch, `_proposal` call, budget, `above_cut`,
    `start_decision` and the `intraday_proposals` propose write (514-585 at the base, after
    part 20's ticket deletions); an unknown name without `--goal` keeps the existing refusal;
  - the `discovery` and `rank` imports stay only if still used (`discovery.discover`,
    `rank.rank`, `rank.validate` are).
- `cli/wuwei/tracker.py:115` (`_candidate`): drop the `discovery_candidates` fallback.
- `cli/wuwei/commands/why.py:151`: drop the `discovery_candidates` score fallback.
- `cli/wuwei/state.py:262-263`: delete the `discovery_candidates` and `intraday_proposals`
  producers.
- `cli/wuwei/commands/event.py:28, 41, 68-69`: delete `build.requested`, `plan.proposed`,
  `discovery.requested`, `discovery.intake` producers (and `discovery.unmeasured` if listed).
- `cli/wuwei/signal.py:21, 23`: delete the `discovery.*` tiers.
- `cli/wuwei/guards/spec.py`: delete `check_edit` and its `GUARDS` row; `WRITES` stays for
  `check_record`; the docstring names the recorder and the stop check.
- `cli/wuwei/guards/__init__.py:29-30` **[after 17]**: `MODULES['spec']` drops `PreToolUse`.
- `cli/wuwei/specmode.py`: delete `own` (185-187) and `OWN` (16) when no reader is left
  (`grep -rn "specmode.own\|OWN\b" cli tests`).
- `cli/wuwei/workspace.py:88-89`: delete SCHEMA `discovery`; `RETIRED` gains `'discovery'`; bump
  `CONFIG_CACHE_VERSION`.

## Files to edit, tests (about 20)

- `tests/test_dispatch.py`: keep `test_gate_dispatch_refuses_an_item_with_a_spec_gap` (45); red
  first: a standard item's refusal names the step and offers no `gates`; a light item with a
  light computed tier gets the gates without a spec. Delete `test_discovery_trigger` (170),
  `test_seat_free_discovery_only_records_the_request` (182).
- `tests/test_intraday_intake.py`: delete the intake cases (51-224, the discovery-candidate
  ones); move the owner-named and finding `plan add` cases (250-406) and `candidate` (31,
  imported by `test_operator_records.py:7` and `test_records_after_dryrun4.py:13`) into
  `tests/test_plan.py`, then delete the file; update both importers.
- `tests/test_goals_rank.py`: delete `test_autostart_strict_full_and_safety` (114),
  `test_seat_free_queue_threshold` (237), `test_sweep_records_discovery_measurement` (269),
  `test_build_returns_loop_status_without_discovery` (284),
  `test_autostart_unknown_risk_or_paths_goes_to_owner` (366),
  `test_rank_cli_returns_order_and_bad_goals_line` (142), `test_rank_lead_json_on_provisional_goals`
  (488), `test_rank_lead_json_ids_only` (515); keep the formula, validation, propose ordering
  and discovery source cases.
- `tests/test_agent_launch.py:397, 416, 439`: delete the builder-stop discovery cases.
- `tests/test_watch.py`: `test_sweep_one_summary_with_counts_and_dead_watch` (94) drops the
  `discovery.requested` assert; delete `test_sweep_reports_unmeasured_discovery_with_measured_scanner`
  (488) and `test_tick_runs_pending_seat_free_discovery_once` (965); `trace_sweep_case` (816)
  stops patching `discover`.
- `tests/test_quiet_sweeps.py:62, 76, 254, 270, 379`: drop the `dispatch.discovery` stubs; keep
  `test_discovery_explains_unavailable_sources` (54).
- `tests/test_heartbeat.py:269`: stop patching `watch.pending_discovery`.
- `tests/test_hooks.py:1106`: SubagentStop events without `discovery.requested`; the `MODULES`
  pin **[after 17]**; `test_spec_helper_loads_only_in_item_worktrees` (247) uses the PostToolUse
  recorder.
- `tests/test_spec_mode.py`: delete `test_pre_tool_use_refuses_source_edits_until_the_spec`
  (255), `test_spec_guard_decides_by_path_not_by_file_name` (268) and the `own` half of
  `test_missing_location_and_own_paths` (118); keep the recorder and stop cases.
- `tests/test_guard_mutation.py:37-41` **[after 17]**: delete the `check_edit` probe row.
- `tests/test_enforce.py:48`: the `spec` table row is a fake check on the module name; keep it
  while `spec` is a guard module.
- `tests/test_e2e_day.py:105-108`: the scripted day's spec gap shows as the build loop's failing
  `spec` check, not a `hook.refusal`; `test_day_names_the_reintroduced_bug` (200) uses another
  launcher command than `wuwei rank`.
- `tests/fakes/day.py:300`: drop the `wuwei rank` call (the proposal order is asserted after
  `plan propose`).
- `tests/test_templates_errors.py`: `test_plan_template_can_be_proposed_from_stdin` (31) drops
  the rank step; delete `test_rank_template_can_be_ranked_from_stdin` (44);
  `test_rice_templates_use_configured_components` (51) uses `plan template`.
- `tests/test_metrics.py:354`, `tests/test_headless_e2e.py:592-601`: the off-path example
  command is another non-loop command (`wuwei goals`).
- `tests/test_plan.py:129`: delete `test_intraday_budget_counts_morning_rank_size`; `992`
  (`test_add_discovery_candidate_with_empty_ticket`) goes.
- `tests/test_why.py:229`: delete `test_intraday_item_takes_its_score_from_discovery`.
- `tests/test_signal_status.py:361-363`: drop the `discovery.*` kinds.
- `tests/test_workspace.py:229`: defaults without `discovery`; `tests/test_config_transition.py`
  retired-keys fixture gains `[discovery]`.
- `tests/test_docs.py`: green after the reference and configuration edits.

## Files to edit, governance and docs (14, plus generated agents)

- `charters/lead.md` (version bump after part 20's): heading "Capacity and discovery" stays;
  step 2 "Discover at the morning plan. Run `wuwei discover` ..." (drop the sweep and
  `min_queue`); step 5 drops "under the configured intraday policy"; step 6 ends "`wuwei plan
  propose` orders the queue by `prioritisation.framework` from this evidence; never hand-order
  it."; step 7 keeps the morning-gate sentence and drops the `discovery.autostart` sentences.
- `charters/builder.md:10` (version bump after part 19's): "The build loop keeps the gates
  until each spec step is done" (no hook refusal).
- `bin/wuwei agents build`.
- `templates/workspace/config.toml:29-31`: the `[discovery]` table; 269 (`[spec]` comment):
  "strict: the gates wait for every step".
- `docs/specs/2026-09-24-wuwei-design.md`: 4.1 row 179 (PreToolUse spec) goes; 5.7 (655-662)
  "Discovery, morning" (drop sweep and `min_queue`), 676 "`wuwei plan propose` computes the
  order", 680-689 (intraday starts) go; 5.10 (845-849) the PreToolUse refusal goes; 1122 the
  intake mention; 1557 "spec mode" in the still-blocks list.
- `docs/site/reference.md`: 16 (morning), 17 (`dispatch` row without discovery), 46 (`rank`
  row), 82-84 (rank template and file); `docs/site/configuration.md`: 11, 28-29, 99, 354-358;
  `docs/site/daily.md`: 108 (`plan propose` orders), 125-126, 241-247; `docs/site/concepts.md`:
  108-116 ("the gates wait"); `docs/site/agent.md:9` unchanged (the lead still ranks through
  `plan propose`).
- `docs/site/assets/hero-dark.svg:65`, `hero-light.svg:65`, `scripts/build-hero.py:67`: "lead:
  discovery when the queue runs low" becomes "lead: morning discovery" (regenerate with the
  script; `tests/test_docs.py::test_hero_files_match_their_generator`).
- `scripts/headless_e2e.py:303, 349, 389`: "do not launch discovery" prompts stay true; edit
  only if they name intake.

## RETIRED

`workspace.RETIRED` gains `discovery`.

## Risks

- **Spec mode advisory.** With `guards.enforce = false`, `specmode.mode` is advisory and
  `dispatch next` warns instead of refusing (part 15). That was already so; the dispatch test
  runs with enforce on. Batch 8 may decide whether this process check should ignore the switch.
- **Moved tests.** `tests/test_intraday_intake.py` holds the owner `plan add` cases and a helper
  two files import; move them before deleting the file.
- **Hero assets.** Regenerate, never hand-edit the SVGs.

## Handoff

- Part 22 (derived `next`): the spec-before-gates refusal is one of its "never offer the wrong
  action" rows.
- Part 24: `wuwei discover` stays a command; the CLI rewrite decides its place.

# Implementation Plan: delete the invariant walk and the prose-pinning tests

**Branch**: `798-invariant-walk-out` | **Date**: 2026-10-11 | **Spec**: `spec.md`
**Input**: Feature specification from `specs/798-invariant-walk-out/spec.md`, read against
main at bfbf6a3 (the pass plan's detail was read at 5816266; every line below was re-read).

## Summary

Tests and governance text only; no runtime code changes. `tests/test_invariants.py` shrinks
to the refusal-string lint. One merge-head case and the `owner_merge` path table move into
`tests/test_merge.py`; the trust-surface case already lives there. The docs and charter
tests keep their structural checks. The constitution drops the invariant-row rule (2.0.0).
Design spec 9.2 becomes the edge table. README and NOTICE stop claiming an exhaustive walk.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime; pytest dev-only.
**Testing**: run only the touched files (pass rule): `python -m pytest -q
tests/test_invariants.py tests/test_merge.py tests/test_docs.py tests/test_charters.py
tests/test_dev_cycle.py tests/test_tone.py tests/test_calibrate.py`. CI runs the rest.
**Constraints**: no emojis, no em-dashes, no absolute local paths, no client, repository or
people's names. Never loosen a kept test or budget.

## Constitution Check

- I (stdlib), II (exits), VI: untouched; no runtime code changes.
- III (one behaviour, one test): each kept process rule keeps its test in the module that owns
  the behaviour (table below); the walk was a second test of rules tested elsewhere.
- IV (test first): the two moved tests pass on arrival (they test existing behaviour); each is
  shown red once with a temporary mutation before it is kept (tasks T003, T005).
- V (simplicity): deletion only; no new helper.
- VII (security): the edges stay refused by the same guards and tests; 9.2 now lists them.
- Workflow: the bullet this change deletes is the rule under review; the owner's pass plan
  orders its removal. Gate: PASS.

## Files

Deleted: none. `tests/test_invariants.py` stays as the lint's home.

Edited (9):

1. `tests/test_invariants.py`
   - Keep lines 30-121: `WALL`, `CARD`, `wall`, `CALLED`, `LATER`, `OWNED`, `MERGES`,
     `EXEMPT`, `_functions`, `corpus`, `listed`, `test_reason_corpus_has_no_wall`.
   - Delete lines 124-1766: `DIMENSIONS` to the end (`CASES`, `CHANNEL`, `TEXT`, `OUTBOUND`,
     `DEPLOY`, `STANDING`, `RELEASE`, `OPAQUE`, `Rules`, `default_has_no_grant`, `i1` to
     `i72` with their cached rule helpers, `INVARIANTS`, `project`, `OUTWARD`, `READS`,
     `PARTS`, `Unread`, `COST`, `INVARIANT_BUDGET`, `walk`, `test_invariants_hold`,
     `test_undeclared_read_raises`, `BROKEN`, `test_a_pace_that_lowers_a_tier_is_caught`,
     `test_broken_rule_is_caught`, the `world` fixture, `test_table_matches_the_checks`,
     `test_no_stale_owner_marks`, `test_merge_only_at_the_gated_green_head`,
     `test_owner_merge_holds_on_every_path`, `test_trust_surface_waits_on_its_gate_not_the_owner`).
   - Imports (lines 3-26): keep `ast`, `from importlib import import_module`, `re`,
     `from test_posture import fixed`, `from test_reasons import CLI, reasons`. Drop
     `contextlib`, `functools`, `gc`, `io`, `itertools`, `math`, `os`, `time`, `pytest`, and
     the imports from `test_card_confirms`, `test_commit_push`, `test_decision`,
     `test_decision_classes`, `test_grants`, `test_merge`, `test_workspace`,
     `wuwei.__main__`, and `ROOT` from `test_reasons`.
   - Docstring (lines 1-2): the refusal-string lint of #530: every guard reason, levelled by
     the posture, is never a wall under observe or guarded.
2. `tests/test_merge.py` (append after the owner-hold tests, near line 1349)
   - `test_merge_waits_on_gates_at_a_moved_head(case)`: the three gate files rewritten with
     `evidence(BASE)`; `policy().execute(REF, root)` exits 1, the reason contains
     `pre-PR gates not passed at current HEAD`, `merged_calls(host) == []`. Auto policy from
     the fixture; no grant, no posture.
   - `test_owner_merge_holds_on_every_path(case, monkeypatch, capsys, path)` with `path` in
     `merge check`, `wuwei merge`, `pr act`, `pr guard`, `overnight shepherd`: the body of
     `tests/test_invariants.py` lines 1684-1734 with `flag='set'` and `grant='none'` fixed
     (drop the grant row write and the cleared branch). Asserts exit 1, the line
     `owner merges: owner_merge set by owner on 2026-09-29` in the text, no merge call. Its
     imports (`plan`, `pr_actions`, `shepherd`, `guards.pr.check`, `watch.records`,
     `wuwei.__main__.main`) stay local to the test, as the module already does for `main`.
   - No trust-surface copy: `test_an_open_security_gate_waits_whatever_the_grant` (line 1487)
     and `test_an_owner_path_is_merged_by_the_owner_whatever_the_grant` (line 1516) are its home.
3. `tests/test_docs.py`
   - Keep: `test_site_pages_are_plain_markdown`, `test_mkdocs_nav_covers_every_page`,
     `test_docs_workflow_deploys_mkdocs`, `test_every_template_config_key_is_documented`,
     `_hero` with `test_hero_files_match_their_generator`,
     `test_release_asset_ships_every_linked_doc`, `test_reference_lists_every_cli_command`,
     `test_configuration_names_every_config_section`,
     `test_skills_use_the_recorded_executable_directly`; constants `ROOT`, `SITE`, `TABLE`.
   - Delete the other 81 tests and the helpers only they use: `GLOSSARY`, `_prose`,
     `PRINCIPLES`, `_principles`, `RECOVERY`, `_smil`, `_value_at`, `_hero_parts`,
     `_timing`, `_popped`, `_place`, `_plain`, `TROUBLESHOOTING`.
   - Imports: drop `json`, `ElementTree` and `calibrate` if no kept test uses them (verify
     each name with grep after the cut); keep the rest the kept tests use.
   - Docstring: keep the public docs aligned with the shipped entry points and config.
4. `tests/test_charters.py`
   - Keep: `test_charter_set_and_frontmatter`, `test_numbered_checklists_are_ordered`,
     `test_generic_content_lint`, `test_generic_patterns_cover_case_without_english_false_positives`,
     `test_charter_sentences_have_one_home`, `test_sentinel_agents_carry_clean_probes`,
     `test_no_blocking_instruction_in_skills_or_charters`, `test_blocking_pattern_samples`,
     `test_plain_tone_rule_has_five_items_and_ships_in_every_agent`,
     `test_no_charter_holds_its_own_verdict_format`; constants `ROOT`, `CHARTERS`, `FILES`,
     `BANNED`, `charter_text`, `BLOCKING`, `INSTRUCTIONS`.
   - Delete: `test_no_repository_engagement_list`, `RULES` with
     `test_section_5_3_rule_has_one_home`, `test_amended_role_rules`,
     `test_gate_and_merge_safety_contract`, `test_pre_review_class_sweep`,
     `test_class_sweep_anchors_first_verbs`, `test_never_auto_path_flag_scope`,
     `test_writing_for_a_person_names_the_humanizer_and_carries_the_checklist`,
     `test_docs_obligation_in_quality_and_builder_charters`,
     `test_tracker_hygiene_commands_have_one_home`,
     `test_lead_proposes_each_ticket_and_the_planner_asks_it`, `test_decision_lens_charters`,
     `test_never_blocking_rule_is_written_down`,
     `test_builder_names_claude_codes_report_file_check`, `test_governing_document_charters`.
5. `tests/test_dev_cycle.py` line 17: remove `('test_invariants.py', 'test_invariants_hold'),`
   from `TIMING`.
6. `.specify/memory/constitution.md`
   - Delete the Workflow bullet at lines 103-104 ("Any item that adds or changes a guard or
     decision rule adds its invariant ...").
   - Footer: `**Version**: 2.0.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-11`.
   - Principle VII's "(design spec 4.6, 4.7 and 9.2)" stays: 9.2 is the edge table.
7. `docs/specs/2026-09-24-wuwei-design.md` lines 2004-2061 (heading `### 9.2 Safety
   invariants` through "A later item that adds a rule ..."): replace with the text under
   "New 9.2" below.
8. `README.md` line 113: "...so hooks check each call against the invariant table in design
   spec 9.2, and a test walks every case of it." becomes "...so hooks check each edge in
   design spec 9.2 at the moment of the call, and each edge has its own test." Line 282:
   "the invariant table and its exhaustive test, without the model checker." becomes "a table
   of safety properties, each with its own test, without the model checker."
9. `NOTICE` lines 107-108: "Used: the invariant table and its exhaustive test, without the
   model checker (design spec 9.2)." becomes "Used: a table of safety properties, each with
   its own test, without the model checker (design spec 9.2)."

Checked and left alone: `.github/workflows/*.yml` (no walk or budget reference; the timing
rerun step is generic and still serves the other clock tests), `scripts/*` (no reference),
`pyproject.toml` (the `xdist_group` marker serves the other clock tests), `docs/site/*` (no
page names the walk), charters, skills, agents, hooks, templates (no invariant-row rule),
`CHANGELOG.md` (history). Comments citing 9.2 ids: see spec Clarifications.

## New 9.2 (paste as written)

```markdown
### 9.2 Process edges (owner, 2026-10-11, #789)

An edge is an action WUWEI cannot take back: it changes what others see or leaves the
workspace. The hooks refuse each edge outside its one path. Every other process rule lives in
code (`next`, dispatch, the verdict lint, the merge policy) and is tested where it lives.

| Edge | Rule | Guard | Test |
| --- | --- | --- | --- |
| Host merge | A PR merges only through `bin/wuwei merge` under the merge policy (4.6): at the head the gates checked, with green required checks, never with `owner_merge` set; a session `gh pr merge` or a merge API call is refused naming it | `guards/pr.py`, `merge.check` | `tests/test_pr_guards.py`, `tests/test_merge.py` |
| Approve | WUWEI never approves a PR: `gh pr review --approve` and an APPROVE review event are refused, and the code host port has no approval call | `guards/pr.py` | `tests/test_pr_guards.py`, `tests/test_code_host.py` |
| Admin | `--admin` and branch protection or ruleset writes are refused | `guards/pr.py` | `tests/test_pr_guards.py` |
| Force push | `git push --force` in every form (`-f`, `--force-with-lease`, `--mirror`) is refused | `guards/commit_push.py` | `tests/test_commit_push.py` |
| Deploy | WUWEI never deploys (4.7) | `guards/deploy.py` | `tests/test_deploy.py` |
| Outward send | A message, tracker or docs write leaves only as the outward lint and tiers allow (4.3, 4.9) | `guards/outward.py` | `tests/test_outward.py` |
| PR raise | An item's PR is raised with `wuwei pr raise --item`, which links it and refuses unless every gate passed at the head; a `gh pr create` for a recorded item warns naming it, and is refused under strict | `guards/pr.py`, `shepherd.raise_pr` | `tests/test_pr_guards.py`, `tests/test_shepherd.py` |

`tests/test_invariants.py` keeps one check across all guards: no guard reason is a wall under
observe or guarded (#530).
```

## Removed units: (a) process machinery or (b) a check that stops a real process error

Walk machinery (dimensions, `Rules`, `Unread`, `walk`, the CPU budget, `BROKEN`, the `world`
fixture, the table-matches and stale-mark tests, the constitution bullet, the 9.2 table): (a).
They make every guard change a table entry and a budget negotiation.

| Row | Subject | Kind | Where its job is held after this change |
| --- | --- | --- | --- |
| I1 | no wall below strict | kept | `test_reason_corpus_has_no_wall`; the per-case `classify` part is posture machinery (a) |
| I2 | held message has a card path | a | drafts and cards; `tests/test_drafts.py` until their PR |
| I3 | merge only at the gated green head | b | moved: `test_merge_waits_on_gates_at_a_moved_head`; plus `test_merge_pins_head_and_writes_evidence_and_undo`, `test_refused_merge_never_calls_mutation`, `test_required_check_must_be_green`, `test_pr_guards.py::test_session_merge_names_wuwei_merge`, `test_policy_actions` |
| I4 | owner DM sends | a | outward tiers; `tests/test_outward.py` |
| I5 | no seat creates a grant | a | grants; `tests/test_grants.py` until their PR |
| I6 | a seat never posts an owner marker | b | `tests/test_pr_ownership.py`, `tests/test_outward.py`, `tests/test_stop.py` |
| I7 | docs and tracker auto | a | `tests/test_outward.py` |
| I8 | record commands after a card | a | decision cards; `tests/test_protect_state.py` |
| I9 | push and raise pass below strict | a | posture levelling; `tests/test_commit_push.py`, `tests/test_pr_guards.py` |
| I10 | opaque reads pass below strict | a | `tests/test_shell.py` |
| I11 to I14 | budget classes, calibration, shadow, raise | a | their own test modules until their PR |
| I15, I16 | pace floors | a | `tests/test_pace.py` until its PR |
| I17 | merge only at green checks | b | `tests/test_merge.py::test_required_check_must_be_green` |
| I18 | setup answers allow no publish | a | `tests/test_grants.py`, `tests/test_setup.py` |
| I19, I21, I55 | outward thread, word and ticket tiers | a | `tests/test_outward.py`, `tests/test_outbound.py` |
| I20 | CAP from the host | b | `tests/test_calibrate.py` `calibrate.host` cases (the pass moves the measure into dispatch later) |
| I22, I23 | undo door, novelty | a | `tests/test_undo.py`, `tests/test_novelty.py` until their PR |
| I24 | register equals config | a | `tests/test_graph.py` |
| I25 | doctor and guard agree on identity | b | `tests/test_commit_push.py`, `tests/test_doctor.py` (`unset_identity`) |
| I26 | `next` start command works with several repositories | b | `tests/test_dispatch.py::test_start_names_the_repository_when_several_are_configured` |
| I27 | goals approve the plan, approve never writes owner memory | b | `tests/test_plan.py`, `tests/test_goals_rank.py` |
| I28, I32, I33 | interview, config cards, record class | a | their own modules |
| I31 | empty fast checks never refuse below strict | a | `tests/test_brief.py`, `tests/test_calibrate.py` |
| I34 | docs-only diff never lowers review | b | `tests/test_dispatch.py` tier tests (`test_code_or_trust_surface_keeps_three_gates`, `test_docs_only_diff_gets_one_reviewer`) |
| I35 | no fix round past the cap | b | `tests/test_dispatch.py::test_open_fix_counts_rounds_and_refuses_at_the_cap`, `test_round_cap_is_read_from_gates_and_the_tier_override` |
| I36 | ticket attached by the planner | a | owner-verb table; `tests/test_protect_state.py` until its PR |
| I37 | `owner_merge` on every path | b | moved: `test_owner_merge_holds_on_every_path`; plus `test_owner_hold_reads_the_item_record`, `test_owner_merge_refuses_before_every_other_rule` |
| I38 | launch registration | b | `tests/test_agent_launch.py` |
| I39 | FIX verdict needs a parsed blocking finding | b | `tests/test_verdict.py` (`finding_blocks` id forms) |
| I40 | soak skipped only for a base fix | b | `tests/test_merge.py::test_fixes_base_names_checks_red_at_base_and_green_at_head` and the soak tests |
| I41 | Bash judged by what it runs | a | `tests/test_shell.py` until the edges PR |
| I42 | generated and data lines never count | b | `tests/test_merge.py` uncounted tests, `tests/test_dispatch.py` tier tests |
| I43 | flagged item runs step zero | b | `tests/test_process_depth.py` |
| I44 | sentinel agents carry the format the lint accepts | b | `tests/test_agents.py` (`lint_file` on each rendered example), `tests/test_verdict.py` |
| I46 | docs value never called missing | a | docs system; `tests/test_dispatch.py` docs tests until its PR |
| I50, I52 | traces timeout, records `python -c` | a | `tests/test_traces.py`, `tests/test_protect_state.py` |
| I72 | merge method the repository allows | b | `tests/test_merge.py::test_merge_method_follows_the_repository` |
| Trust surface (I3 part) | a trust-surface PR waits on its gate | b | `tests/test_merge.py::test_an_open_security_gate_waits_whatever_the_grant`, `test_an_owner_path_is_merged_by_the_owner_whatever_the_grant`, `test_trust_surface_with_security_pass_merges_under_the_normal_policy`; gate selection in `tests/test_dispatch.py::test_code_or_trust_surface_keeps_three_gates` |

Docs tests deleted (81): (a). They pin sentences of README, site pages, skills, NOTICE,
SECURITY.md and CONTRIBUTING.md; none stops a process error. Two that read code tables
(`test_security_posture_table_matches_the_code`, `test_remote_runbook_matches_the_code`)
cover posture and the remote plane, which later PRs delete; `test_repository_gate_keys_are_documented`
is subsumed for the shipped keys by `test_every_template_config_key_is_documented`.

Charter tests deleted (15): (a). They pin charter sentences. The process rules they echo are
enforced in code: round cap (`dispatch`, `build.open_fix`), verdict format (`verdict.FORMAT`
and its lint), gate at the pinned head (`brief.gate_ready`, `dispatch.receive`), PR raise
(`pr raise --item`, the PR guard), merge (`merge.check`, the PR guard).

## Risks for the builder

- `test_owner_merge_holds_on_every_path` sets `host.results['label']` and calls
  `plan.set_owner_merge`; it ran in `tests/test_invariants.py` on the same `case` fixture, so
  it runs unchanged in `tests/test_merge.py`. The `pr act` path monkeypatches
  `pr_actions.evaluate`; keep that.
- The module-level `OWNED` in `tests/test_merge.py` (line 1497) is an unrelated path constant;
  the moved test does not use the walk's `OWNED`.
- `tests/test_tone.py` measures README in the `docs` class (budget 77 long sentences, 3.0
  nominalisations per 100 words): keep both edited sentences under 35 words.
- No loosening: the kept tests are copied byte for byte apart from the removed parameters.

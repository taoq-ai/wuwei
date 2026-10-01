# Tasks: risk-tiered gates computed from the diff, with per-repository floors and escaped-defect measurement

**Input**: `specs/280-tiered-gates/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names. No absolute local paths, emojis or
em-dashes in any file.

Shared test helper for Phases 2 to 4, in `tests/test_dispatch.py`: `tiered(root,
monkeypatch, paths, floor='light', flags=(), track='SLICE', lead=None, extra='')` writes
`.wuwei/config.toml` with one `[[repos]]` (`name = "acme/widget"`, `path = "repo"`,
`default_branch = "main"`), `[repos.gates] floor = ...` and the `extra` TOML text,
creates `root / 'repo'`,
sets item A's `worktree` to it plus the given flags, track and lead `tier` with
`state._write_state(..., reserved=False)`, and monkeypatches `registry.load` so `vcs` is
`fakes.vcs.Fake(results=...)` with `head` (`'a' * 40`), `merge_base` (`'b' * 40`),
`repo_context` (`{'path': <repo>, 'common_dir': <repo>/.git}`) and `diff_stat` built
from `paths` (a list of `(path, additions, deletions)`). Returns the fake.

## Phase 1: Shared pieces (config, matcher, reserved names)

- [X] T001 Test, `tests/test_workspace.py` (`test_repository_gate_defaults_and_floor_choices`):
  a config with one `[[repos]]` entry loads `repos[0]['gates'] == {'floor': 'standard',
  'light_max_lines': 100, 'trust_paths': [<the nine defaults from plan.md section 1>]}`;
  `floor = "lowest"` and `light_max_lines = -1` are refused by `workspace.load_config`
  the same way other schema violations are (reuse the existing invalid-config assertion
  style in that file). Run `python -m pytest -q tests/test_workspace.py -k gate`.
- [X] T002 Implement, `cli/wuwei/workspace.py` (`SCHEMA['repos']` gains `gates`).
- [X] T003 Test, `tests/test_merge.py` (`test_matched_checks_every_path_suffix`):
  `merge.matched('cli/wuwei/guards/pr.py', ['guards/*']) == 'guards/*'`,
  `merge.matched('uv.lock', ['*.lock']) == '*.lock'`,
  `merge.matched('docs/guide.md', ['guards/*', '*.lock']) is None`. Run
  `python -m pytest -q tests/test_merge.py -k "matched or never_auto or rename"`.
- [X] T004 Implement, `cli/wuwei/merge.py` (`matched`, used by `check` in place of the
  inline loop at lines 242-244). Keep `test_never_auto_paths` and
  `test_rename_cannot_hide_protected_source` green.
- [X] T005 Test, `tests/test_state_allowlist.py`: add `('items.A.gates', 'wuwei dispatch
  next')` and `('items.A.tier', 'wuwei plan approve')` to
  `test_nonallowlisted_state_paths_refuse_without_write`, and `('gate.tiered', 'wuwei
  dispatch next')` to `test_nonfree_events_refuse_without_append`; in
  `tests/test_signal_status.py`, assert `signal.classify({'kind': 'gate.tiered',
  'payload': {}}, {})[0] == 'silent'` (next to the existing `gate.received` row). Run
  `python -m pytest -q tests/test_state_allowlist.py tests/test_signal_status.py -k "nonallowlisted or nonfree or silent or classify"`.
- [X] T006 Implement, `cli/wuwei/state.py` (`_producer_error` map),
  `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS['gate.tiered']`) and
  `cli/wuwei/signal.py` (`SILENT`).

## Phase 2: US1 a small, safe diff runs one gate (P1)

- [X] T007 Test, `tests/test_dispatch.py`
  (`test_issue_acceptance_docs_only_light_floor_runs_quality_only`): `tiered(root,
  monkeypatch, [('docs/guide.md', 3, 1)])`; `dispatch.next_step('A', root)` returns
  `action == 'gates'`, `roles == ['quality']`, `seats == []` and `tier == {'tier':
  'light', 'computed': 'light', 'roles': ['quality'], 'reasons': ['4 changed lines within
  light_max_lines 100']}`; `state.read_state(root)['items']['A']['gates']` equals that
  record; exactly one `gate.tiered` event with payload `{'item': 'A', **record}`. A second
  `next_step` returns the same dict, adds no `diff_stat` call to `fake.calls` and no
  second `gate.tiered` event. Run `python -m pytest -q tests/test_dispatch.py -k tier`.
- [X] T008 Implement, `cli/wuwei/dispatch.py` (`TIERS`, `gate_set`, `tier`, and the gate
  phase of `next_step` recording the tier and returning `tier`), as plan.md section 3.
- [X] T009 Test, `tests/test_dispatch.py` (`test_light_item_receives_and_fixes_quality_only`):
  these behaviours depend only on a recorded LIGHT set, so write it directly with
  `state._write_state(lambda data: data['items']['A'].update(gates=LIGHT), root,
  reserved=False)` where `LIGHT = {'tier': 'light', 'computed': 'light', 'reasons': [],
  'roles': ['quality']}` (module constant). Then `record(root, 'arch', 'arch-1', PASS)`
  raises `dispatch.Refused` matching `not in the item gate set`; `record(root, 'quality',
  'quality-1', PASS + 'Simplicity: none\nDesign: none\n')` then `next_step` is
  `{'action': 'raise', 'notes': []}`. A second test with `built(root)` first (as
  `test_fix_pass_then_only_quality_delta`), the LIGHT record and a quality FIX gives
  `{'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}`; after
  `state.transition('A', 'delta', root)` the delta returns `{'action': 'gates', 'roles':
  ['quality'], 'seats': []}`. A malformed record (`roles: ['arch']`) makes `next_step`
  raise `ValueError` matching `invalid recorded gate set`. Run
  `python -m pytest -q tests/test_dispatch.py -k "tier or light"`.
- [X] T010 Implement, `cli/wuwei/dispatch.py` (fix and delta phases iterate
  `gate_set(row)`; `receive` refuses a role outside it).
- [X] T011 Test, `tests/test_pr_guards.py`
  (`test_pr_gate_accepts_quality_only_for_a_light_item`): with the `case` fixture, record
  only `9:quality:initial` PASS at the current head (as
  `test_pr_gate_accepts_quality_only_delta_after_fix` builds records) and set
  `items['9'] = {'gates': {'tier': 'light', 'computed': 'light', 'reasons': [], 'roles':
  ['quality']}}`; `gate_check(..., item='9') == (0, '')`. Without the `gates` record the
  same evidence returns code 1 naming `arch, security` (today's rule). With
  `roles: ['arch']`, `gate_check` raises `ValueError` matching `invalid recorded gate
  set` (which the guard's `check` maps to exit 2). Run
  `python -m pytest -q tests/test_pr_guards.py -k "light or recorded"`.
- [X] T012 Implement, `cli/wuwei/guards/pr.py` (`_recorded_gates(..., items=None)` using
  `dispatch.gate_set`; `gate_check` passes `data['items']`).
- [X] T013 Test, `tests/test_merge.py` (`test_light_item_merge_evidence_lists_quality_only`):
  from the `case` fixture used by `test_clean_has_head_bound_evidence`, keep only the
  quality verdict record and file, set the item's `gates` record to light, and assert
  `check(case)` is exit 0 with `len(result.data['verdicts']) == 1` and its path ending
  `quality.md` (adapt to the fixture's verdict naming). Run
  `python -m pytest -q tests/test_merge.py -k "light or clean or quality_delta"`.
- [X] T014 Implement, `cli/wuwei/merge.py` (verdict evidence loop over
  `dispatch.gate_set(data['items'][item])`).

## Phase 3: US2 and US3 risky paths, flags and unmeasured diffs (P1)

- [X] T015 Test, `tests/test_dispatch.py`
  (`test_issue_acceptance_trust_path_is_standard_regardless_of_floor`): `tiered(root,
  monkeypatch, [('docs/guide.md', 3, 1), ('cli/wuwei/guards/pr.py', 2, 0)])`; tier
  `standard`, roles all three, and `'cli/wuwei/guards/pr.py matches trust path guards/*'`
  in `reasons`. Run `python -m pytest -q tests/test_dispatch.py -k tier`.
- [X] T016 Test, `tests/test_dispatch.py`
  (`test_issue_acceptance_lockfile_includes_security_at_any_tier`), parametrized over
  `floor` in `light`, `standard`, `full` and over track `SLICE`, `FULL`:
  `[('uv.lock', 10, 2)]` gives `'security' in action['roles']` and a reason containing
  `uv.lock matches never-auto path`. Plus
  `test_full_track_pattern_forces_arch`: `extra='[brief]\nfull_path_patterns =
  ["^api/"]\n'` and `[('api/schema.json', 1, 0)]` gives `'arch' in roles` and a reason
  naming `^api/`. Run the same command.
- [X] T017 Test, `tests/test_dispatch.py`
  (`test_issue_acceptance_lead_raises_and_cannot_lower`): parametrize each flag on a LIGHT
  docs diff: tier `standard`, reason `lead flag <name>`; lead `tier='full'` on a LIGHT
  diff: tier `full`, reason `lead tier full`; lead `tier='light'` on the trust-path diff
  of T015: tier `standard`, roles all three, reason `lead tier light refused: below
  standard`. Track FULL alone: tier `full`, roles all three. Run the same command.
- [X] T018 Test, `tests/test_dispatch.py` (`test_size_binary_and_unmeasured_diffs_stay_standard`):
  `[('src/app.py', 90, 11)]` gives `standard` with `101 changed lines over
  light_max_lines 100`; `[('logo.png', None, None)]` gives `standard` with `logo.png
  binary change`; with `fake.results['diff_stat'] = Result(2, None, 'git failed')` the
  tier is `standard` with a reason starting `diff unmeasured:`; an item with no worktree
  (the module `root` fixture plus `[repos.gates] floor = "light"` config) gives
  `standard` and `diff unmeasured: no worktree`; an item that already has an initial
  verdict before its first dispatch (as `test_fix_with_park_or_missing_gate_stays_in_gate`)
  gets no `gates` record and no `tier` key. An empty diff `[]` gives `light`. Run the same
  command.
- [X] T019 Implement, `cli/wuwei/dispatch.py` (`tier`: trust paths, never-auto paths,
  FULL-track patterns, binary rows, size, flags, track, floor, lead tier, unmeasured), as
  plan.md section 3 steps 1 to 6, until T015 to T018 pass.

## Phase 4: The lead's tier in the plan (P1, needed by T017 in real flows)

- [X] T020 Test, `tests/test_plan.py` (`test_candidate_tier_is_optional_validated_and_copied`):
  a proposal candidate with `tier: "medium"` is refused naming `tier must be light,
  standard or full`; with `tier: "full"` the approved item has `tier == 'full'`; a
  candidate without `tier` gives an item without a `tier` key (existing shape). The
  intraday `plan.add` path copies it too (extend the nearest existing `add` test). Run
  `python -m pytest -q tests/test_plan.py tests/test_intraday_intake.py -k tier`.
- [X] T021 Implement, `cli/wuwei/plan.py` (`_proposal` validation, `approve` and `add`
  copy), as plan.md section 7.

## Phase 5: US4 the tier is visible (P2)

- [X] T022 Test, `tests/test_signal_status.py` (`test_status_json_shows_recorded_tiers`):
  `day(tmp_path, {'cap': 1, 'items': {'A': {'phase': 'gate', 'gates': <light record>},
  'B': {'phase': 'gate'}}})`; `status --json` has `gates == {'A': <light record>}`.
  Run `python -m pytest -q tests/test_signal_status.py -k tier`.
- [X] T023 Implement, `cli/wuwei/commands/status.py` (`snapshot` adds `gates`).
- [X] T024 Test, `tests/test_shepherd.py` (`test_raise_body_names_the_review_tier`): in
  the raise setup used by the existing approved-raise test, set item `ITEM-1`'s `gates`
  to the light record; after `raise_pr(..., 'Body', 'ITEM-1') == 0`, the `create_pr`
  call's body is `'Body\n\nReview tier: light (quality)'`; with no record the body is
  `'Body'` unchanged. Run `python -m pytest -q tests/test_shepherd.py -k tier`.
- [X] T025 Implement, `cli/wuwei/shepherd.py` (`raise_pr` appends the line before the
  outward lint).

## Phase 6: US5 escaped defects per tier (P2)

- [X] T026 Test, `tests/test_metrics.py` (`test_escaped_defects_counted_per_computed_tier`):
  two day directories under `.wuwei/days` (dates on or before `WUWEI_NOW`), day 1 state
  with `A` merged (`gates.computed = 'light'`) and `C` merged (`computed =
  'standard'`), day 2 state with `B` merged (`computed = 'standard'`) and a `brief
  written` event `{'item': 'B', 'role': 'builder', 'path': <day2 briefs/b.md relative to
  the workspace root>}` whose file text says `Fix the regression from A.`; `metrics.collect(root)['escaped_defects_per_tier']
  == {'light': {'merged': 1, 'escaped': 1}, 'standard': {'merged': 2, 'escaped': 0}}`.
  A gate brief (role `sentinel-quality`) naming `C` does not count. With no tiered merged
  item the value is `'unmeasured'` (`metrics.UNMEASURED`). Run
  `python -m pytest -q tests/test_metrics.py -k tier`.
- [X] T027 Implement, `cli/wuwei/metrics.py` (`_escaped_by_tier`, wired in `collect`).

## Phase 7: US6 existing behaviour, docs and polish

- [X] T028 Update the additive `tier` expectations only: `tests/test_dispatch.py` line 34
  and lines 613-614 and `tests/test_e2e_day.py` line 27 compare the action without `tier`
  to the old dict and assert `tier['tier'] == 'standard'` and `tier['roles'] ==
  ['arch', 'quality', 'security']`. Run
  `python -m pytest -q tests/test_dispatch.py tests/test_e2e_day.py tests/test_headless_e2e.py`.
- [X] T029 Test, `tests/test_docs.py` (`test_repository_gate_keys_are_documented`): every
  key of `workspace.SCHEMA['repos'][0]['gates']` appears as `` `repos.gates.<key>` `` in
  `docs/site/configuration.md`, and `docs/site/reference.md` mentions the candidate
  `tier`. Run `python -m pytest -q tests/test_docs.py -k gate` (fails on the page).
- [X] T030 Docs, `docs/site/configuration.md`, `docs/site/reference.md`,
  `charters/_common.md` rule 4 and `charters/lead.md` rule 5, as plan.md section 11; then
  `bin/wuwei agents build` and `bin/wuwei agents check` (exit 0). Run
  `python -m pytest -q tests/test_docs.py tests/test_agents.py tests/test_charters.py`.
- [X] T031 Run the full suite, `python -m pytest -q`. Any other failure must be an exact
  equality on a first initial-round `gates` action or on a vcs call list that now includes
  the tier reads; fix those by the T028 pattern and list them in the final report. No
  expected role list, verdict, phase or exit code may change. Check every file you wrote
  for em-dashes, emojis and absolute local paths.

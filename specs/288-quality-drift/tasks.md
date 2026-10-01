# Tasks: quality by hour and by session age, and planned planner-session rotation

**Input**: `specs/288-quality-drift/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to
fail for the expected reason before its implementation task starts. Run from the
repository root with the interpreter your task names. No absolute local paths, emojis or
em-dashes in any file. Every test that asserts an hour band writes `[owner]\ntimezone =
"UTC"\n` into `.wuwei/config.toml` and pins `WUWEI_NOW`, so the machine's zone never
decides a band.

## Phase 1: Shared pieces (config, zone, counting rule, reserved kind)

- [X] T001 Test, `tests/test_workspace.py`: update
  `test_config_defaults_and_independence` for `owner.timezone: ''`,
  `metrics.band_margin: 0.2` and `sessions.rotate_after: {'turns': 0, 'compactions': 0,
  'clock': ''}`; add `test_owner_zone`: `workspace.zone(config)` is `None` for an empty
  zone, `ZoneInfo('Europe/Amsterdam')` for that name, and raises `ValueError` matching
  `owner.timezone` for `"Mars/Base"`; `rotate_after = { turns = -1 }` is refused by
  `load_config` like other schema violations. Run
  `python -m pytest -q tests/test_workspace.py -k "defaults or zone or invalid"`.
- [X] T002 Implement, `cli/wuwei/workspace.py` (`SCHEMA` keys and `zone`, plan.md
  section 1).
- [X] T003 Test, `tests/test_sessions.py`: update
  `test_record_inserts_then_moves_only_last_seen` so the row after the `Stop` record
  carries `'turns': 1`; add `test_record_counts_turns_and_compactions`: records with hooks
  `SessionStart:startup`, `Stop`, `Stop`, `SessionStart:compact`, `plan session`,
  `SubagentStop:Explore` leave `turns == 2`, `compactions == 1`; `sessions.rows` shows
  `turns`, `compactions` (0 for a row without them) and `rotated` when set. Run
  `python -m pytest -q tests/test_sessions.py -k "record or rows"`.
- [X] T004 Implement, `cli/wuwei/sessions.py` (`COUNTED`, `count`, the `record` call and
  the `rows` fields, plan.md section 2).
- [X] T005 Test, `tests/test_state_allowlist.py`: add `('session.rotated', 'wuwei hook
  Stop')` to `test_nonfree_events_refuse_without_append`; `tests/test_signal_status.py`:
  add `'session.rotated': 'silent'` to the expected map in
  `test_emitted_kinds_have_intended_tiers`. Run
  `python -m pytest -q tests/test_state_allowlist.py tests/test_signal_status.py -k "nonfree or emitted"`
  (the signal test fails once T008 emits the kind; write it now, see the allowlist part
  fail now).
- [X] T006 Implement, `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS`) and
  `cli/wuwei/signal.py` (`SILENT`).

## Phase 2: US2 rotation at a clean boundary (P1)

- [X] T007 Test, `tests/test_sessions.py`
  (`test_issue_acceptance_rotation_after_turns`): config `[sessions]\nrotate_after = {
  turns = 200 }\n`; seed state with `planner_session_id='P'`, a registry row for `P` with
  `turns: 199`, a running seat `builder-1` (item `ITEM-1`, brief path) and
  `decision_routes={'D-1': {...}}` answered by the owner in `decision_outcomes`
  (`{'option': 'A', 'decided_by': 'owner'}`). Pipe Stop for `P` through the `hook` helper:
  returns 0, no `session.rotated` event, row `turns == 200`. Set the seat to `stopped`;
  Stop again: returns 2 (block), stdout JSON `decision: block` whose reason contains
  `turns 201 >= 200` and `wuwei plan session "$WUWEI_SESSION_ID" --take-over`; exactly one
  `session.rotated` event with `{'session_id': 'P', 'reason': ..., 'turns': 201,
  'compactions': 0}`; `wuwei sessions` shows `rotated` for `P`. A third Stop returns 0
  and adds no `session.rotated`. Then `main(['plan', 'session', 'Q', '--take-over'])` and
  `lifecycle.session_start` for `Q` (with `goals.md`, `plan.md`, `goals: ['G-1']`,
  `gate_approved`, a running seat and an unanswered route `D-2`) returns a payload
  containing the goal outcome text, `plan.md`, `D-2` and the brief path. Run
  `python -m pytest -q tests/test_sessions.py -k rotation`.
- [X] T008 Implement, `cli/wuwei/sessions.py` (`rotation`, `_due`) and
  `cli/wuwei/guards/lifecycle.py` `stop` (plan.md sections 2 and 3). The SessionStart part
  of T007 passes after T014.
- [X] T009 Test, `tests/test_sessions.py` (`test_rotation_not_at_dirty_boundary_or_off`,
  parametrized): no rotation and no event when (a) `rotate_after` is unset at 500 turns,
  (b) an owner decision route is unanswered, (c) a planner wake marker is pending (the
  wake message is returned instead and rotation waits), (d) the Stop is from a
  non-planner session, (e) `stop_hook_active` is true (turns unchanged), (f) and (g) a
  Codex build with no seat is in `builds` with status `running` or `check`. Run
  `python -m pytest -q tests/test_sessions.py -k rotation`.
- [X] T010 Implement, only if T009 fails: tighten `sessions.rotation` and
  `lifecycle.stop` ordering.
- [X] T011 Test, `tests/test_sessions.py` (`test_rotation_by_compactions_and_clock`):
  `{ compactions = 1 }` rotates after one `SessionStart:compact` for the planner;
  `{ clock = "13:00" }` with `[owner] timezone = "UTC"` does not rotate at
  `WUWEI_NOW=...T12:59:00+00:00` and does at `13:00:00` for a row started at 09:00;
  `{ clock = "noon" }` makes Stop return 0 with a message starting `planner wake
  unmeasured:` and writes no event. Run `python -m pytest -q tests/test_sessions.py -k
  rotation`.
- [X] T012 Implement, `cli/wuwei/sessions.py` (`_due` compactions and clock branches).

## Phase 3: US3 the payload restates active constraints (P1)

- [X] T013 Test, `tests/test_memory.py` (`test_payload_opens_with_active_constraints`):
  workspace with `goals.md` (`G-1`, `outcome: Ship checkout v2`, target, date, priority),
  today's `plan.md`, state `goals=['G-1']`, `gate_approved=True`,
  `approved_items=['ITEM-1']`, a running seat with a brief path, a stopped seat with
  another brief path, and routes `D-1` (unanswered) and `D-2` (owner answered).
  `memory.session_payload(root)[0]` starts with `Active constraints:` and contains
  `G-1 Ship checkout v2`, the relative `plan.md` path with `approved: ITEM-1`,
  `Open decisions: D-1` (not `D-2`), the running seat's brief and not the stopped one's,
  and the brief of a `builds` entry in `check` (a Codex build has no seat);
  the reported size equals the UTF-8 length of the whole text. A second case with an
  unparseable `goals.md` gives `Goals: unmeasured:` and still contains `Spine:`; a third
  with no goals and no approval gives `Goals: none` and `Plan: not approved`. Run
  `python -m pytest -q tests/test_memory.py -k "payload"`.
- [X] T014 Implement, `cli/wuwei/memory.py` (`constraints`, prepended in
  `session_payload`, plan.md section 4).
- [X] T015 Test, `tests/test_sessions.py`
  (`test_issue_acceptance_payload_after_compaction`): with the T013 day state, pipe
  PreCompact then SessionStart with `source: compact` for the planner through
  `commands.hook.run`; the printed `hookSpecificOutput.additionalContext` starts with
  `Active constraints:` and contains the goal text, `plan.md`, `Open decisions: D-1` and
  the brief path; the planner row has `compactions == 1`. Run
  `python -m pytest -q tests/test_sessions.py -k compaction`.
- [X] T016 Implement, only if T015 fails (T004 and T014 should cover it).

## Phase 4: US1 quality by band in metrics, report and retro (P1)

- [X] T017 Test, `tests/test_metrics.py` (`test_quality_by_hour_and_session_age`): config
  `[owner]\ntimezone = "UTC"\n`; write `events.jsonl` rows directly (as the latency
  fixture does, `chmod` around the append) with explicit `ts` across the day:
  `plan.session` for `P` at 08:00; 10 `session.seen` Stop rows for `P` in the morning;
  a morning `gate.received` PASS; a midday `gate.received` FIX; 60 more Stop rows, then
  an evening `gate.received` FIX and FIX-phase `state.transition` (phase_changes
  `{'A': 'fix'}`) and two `verdict.rejected` rows for the same `(file, sha256)`; one
  `SessionStart:compact` row then one late-evening `gate.received` PASS. Assert
  `collect(root)['quality_by_band']`: every hour band and age band present;
  `hour['morning']` gates 1, FIX rate 0.0; `hour['midday']` FIX rate 1.0;
  `hour['evening']` gates 2, fix_rounds 1, lint_rejections 1; `session_age['0-49
  turns']` gates 2; `session_age['50-199 turns']` gates 1, fix_rounds 1;
  `session_age['compacted']` gates 1; an empty band has `fix_rate == 'unmeasured'`;
  `interventions == 'unmeasured'` everywhere (no transcripts). A second assertion with
  `timezone = "Europe/Amsterdam"` moves a `10:30+00:00` gate into `midday`. With no
  `events.jsonl`, `quality_by_band == 'unmeasured'`. Run
  `python -m pytest -q tests/test_metrics.py -k quality`.
- [X] T018 Implement, `cli/wuwei/metrics.py` (`HOURS`, `AGES`, `COUNTERS`, `_hour_band`,
  `_age_band`, `_bands`, `bands`, and the `collect` lines, plan.md section 5).
- [X] T019 Test, `tests/test_metrics.py` (`test_band_interventions_from_transcripts`):
  point `[metrics] transcripts` at a `tmp_path` folder with one JSONL transcript holding
  two human turns (morning, evening; `cwd` inside the workspace, as the existing
  owner-intervention tests build them); `hour['morning']['interventions'] == 1`,
  `hour['evening']['interventions'] == 1`, other bands 0; `owner_intervention` is
  unchanged versus `main` for the same input; monkeypatch-count `_human_times` calls in
  one `collect`: exactly 1. Run `python -m pytest -q tests/test_metrics.py -k
  "quality or intervention"`.
- [X] T020 Implement, `cli/wuwei/metrics.py` (`_owner_intervention(turns, now)` and the
  shared `turns`).
- [X] T021 Test, `tests/test_metrics.py` (`test_worst_band_margin`, table test on
  `metrics.worst`): two bands with gates and rates 0.6 vs 0.2 at margin 0.2 name the 0.6
  band with `(band, 0.6, 0.2)`; 0.3 vs 0.2 returns `None`; one measured band returns
  `None`; bands with zero gates are ignored. Also `metrics.band_lines('Hour', table)`
  yields a header row, a separator and one row per band in constant order with rates as
  `0.50`, and `['Hour: unmeasured']` for `'unmeasured'`. Run
  `python -m pytest -q tests/test_metrics.py -k "worst or band_lines"`.
- [X] T022 Implement, `cli/wuwei/metrics.py` (`worst`, `band_lines`).
- [X] T023 Test, `tests/test_report_retro.py`
  (`test_issue_acceptance_report_shows_quality_bands`): a day with the T017 events (shared
  module helper `banded_day(root)`); `main(['report'])` output contains `## Quality by
  band`, a `| Hour |` header, a `| midday | 1 | 1.00 |` row prefix and a
  `| Session age |` header; `test_report_metrics_are_the_metrics_json` stays green. Run
  `python -m pytest -q tests/test_report_retro.py -k "report"`.
- [X] T024 Implement, `cli/wuwei/report.py` (`build`, plan.md section 6).
- [X] T025 Test, `tests/test_report_retro.py`
  (`test_issue_acceptance_retro_names_worst_band`): with captured role evidence (as
  `test_retro_compiles_role_evidence_and_cycle`) and two earlier day directories plus
  today holding `gate.received` rows: evening 3 FIX of 4, other bands 0 FIX of 2 each;
  `retro.compile` text contains `## Quality by band (last 7 days)`, `Worst hour band:
  evening (FIX rate 0.75; others at most 0.00)`; one
  `proposals/quality-hour-evening.json` with target `.wuwei/charters/planner.md`, action
  `add`, text naming `sessions.rotate_after`, and evidence equal to the retro path; it is
  listed under `## Proposed`. A second compile writes no second file; with
  `quality-hour-evening.rejected` present in an earlier day of the window, none is
  written. A balanced window prints `Worst hour band: none` and `Worst session age band:
  none` and writes no quality proposal. `test_retro_compiles_role_evidence_and_cycle`
  still finds exactly one proposal. Run `python -m pytest -q tests/test_report_retro.py
  -k retro`.
- [X] T026 Implement, `cli/wuwei/retro.py` (`compile`, plan.md section 7).

## Phase 5: US4 latency, config template and docs

- [X] T027 Test, `tests/test_hooks.py` `seeded_workspace`: add a `goals.md` with one goal,
  `goals=['G-1']` in the seeded state and `[sessions]\nrotate_after = { turns = 1 }\n` to
  the config (the running seat keeps the turn dirty, so Stop still prints nothing). Run
  `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k "workspace_hook_latency and (Stop or SessionStart)"`
  and record the printed p95 figures; both must stay within the asserted budget.
- [X] T028 Fix, only if T027 breaks the budget: move the offending import inside the
  function that needs it (`zoneinfo`, `goals`, `decision`) and re-measure.
- [X] T029 Test, `tests/test_docs.py`: `test_every_template_config_key_is_documented`
  covers the new template keys; add `test_daily_long_sessions_section`: `daily.md` has
  `## Long sessions` before `## 6. Close`, and it names `sessions.rotate_after`,
  `--take-over`, `Active constraints`, `Quality by band` and `owner.timezone`. Run
  `python -m pytest -q tests/test_docs.py -k "template_config or long_sessions"`.
- [X] T030 Implement, `templates/workspace/config.toml`, `docs/site/configuration.md`
  and `docs/site/daily.md` (plan.md section 9).

## Phase 6: Verification

- [X] T031 Run the full suite, `python -m pytest -q`; everything passes.
- [X] T032 Check every file touched for em-dashes, emojis and absolute local paths
  (`grep -rnP '\x{2014}|[\x{1F300}-\x{1FAFF}]'` over the changed files) and remove any.

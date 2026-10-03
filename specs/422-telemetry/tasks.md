# Tasks: Telemetry (#422)

**Input**: spec.md, plan.md, data-model.md in `specs/422-telemetry/`.
**Rule**: every test task runs red (for the stated reason) before its implementation task.
Tests run with `python -m pytest -q <file>`; no network, fixtures under `tmp_path`, the clock
from `WUWEI_NOW`. `[P]` marks tasks on files no other open task touches.

## Phase 1: Hook path (US2, the only hook change)

- [X] T001 [US2] Test in tests/test_hooks.py: a refusing fake guard returning exit 1 and one
  returning exit 2 produce `hook.refusal` rows with `exit` 1 and 2; under observe, one
  `guard.would_refuse` with `exit`. Update the existing expected rows (around lines 1163,
  1196, 1212, 1222) to carry `exit`. Red: rows have no `exit`.
- [X] T002 [US2] Test in tests/test_hooks.py: event-count pin per path: one allowed
  PreToolUse appends 0 events, one refused appends exactly 1 (`hook.refusal`), one warned
  with one refusing guard appends exactly 1 (`guard.would_refuse`), a heartbeat-session
  refusal appends 0. Extend `test_no_hook_path_imports_heartbeat` to also refuse any import
  naming `telemetry`, and add `wuwei.telemetry` and `secrets` to both deny sets of
  `test_hook_imports_no_unused_stdlib`. Red only for the parts T001 code has not met; the
  pins must pass after T003 and stay green to the end.
- [X] T003 [US2] cli/wuwei/commands/hook.py: carry `code` from `run` line 111 through
  `posture` and `refuse` (plan.md "Hook path"). No new import, append or step.
- [X] T004 [US2] Test in tests/test_heartbeat.py: `measure` returns `ms` for `refused`,
  `allowed`, `state_write`, `read_loop` from the fake service's third element, and none for a
  timed-out call; update the literal at line 359. Red: no `ms`.
- [X] T005 [US2] cli/wuwei/heartbeat.py `measure`: add `ms` to the four hook probe rows.

## Phase 2: Foundation (config, protection, events)

- [X] T006 [P] Test in tests/test_workspace.py: `load_config` defaults `telemetry.enabled`
  true, `share` `""`, `endpoint` `""`, `repository` `taoq-ai/wuwei`, `otlp.endpoint` and
  `otlp.headers_env` `""`; `share = "maybe"` is a ConfigError. Red: unknown section.
- [X] T007 cli/wuwei/workspace.py: `[telemetry]` in `SCHEMA`; `CONFIG_CACHE_VERSION = 2`.
- [X] T008 [P] Test in tests/test_protect_state.py: a Write to `.wuwei/metrics/2026-W40.json`
  and to `.wuwei/metrics/token` is refused; `bin/wuwei telemetry send` from an agent Bash
  call is refused with the owner-action reason. Red: allowed.
- [X] T009 cli/wuwei/guards/protect_state.py: `metrics` in `_protected_name`;
  `('telemetry', 'send')` in `_OWNER_ACTIONS`.
- [X] T010 [P] Test in tests/test_signal_status.py: `telemetry.ready` classifies as nudge and
  the other five `telemetry.*` kinds as silent; `wuwei event telemetry.shared` is refused
  naming its producer. Red: unlisted kinds are nudges; producer text missing.
- [X] T011 cli/wuwei/signal.py `SILENT` and cli/wuwei/commands/event.py `EVENT_PRODUCERS`.
- [X] T012 [P] Test in tests/test_profiles.py: importing a profile with `telemetry.share` is
  refused and exporting a workspace with `telemetry.share = "anonymous"` drops it. Red:
  carried.
- [X] T013 cli/wuwei/profiles.py `DENIED`: `telemetry.*`.

## Phase 3: Aggregation (US1)

- [X] T014 [US1] Test in tests/test_telemetry.py (new): a fixture builder that seeds one ISO
  week of day directories (events, traces lines, day state with `decision_routes` and
  `decision_outcomes`, decision records with `Class:`) and an expected dict for every 5.13
  metric key; `telemetry.aggregate` equals it; an empty week gives `"unmeasured"` rates;
  `first_hour_refusals` only in the earliest day's week; a refusal row without `exit` counts
  as exit 1 and a row-less `hook.refusal` as `config` exit 2. Red: no module.
- [X] T015 [US1] cli/wuwei/telemetry.py: constants, `week_of`, `read_days`, `aggregate`
  (plan.md per-metric notes), reusing `watch.records`, `watch.days`, `metrics._percentile`,
  `metrics._escaped_by_tier`, `decision.naming`, `decision.answered`,
  `decision.weekday_hours`, `verdict.rows`. Top-level imports stdlib only.
- [X] T016 [US1] Test in tests/test_telemetry.py: the vocabulary literals equal
  `guards.MODULES` keys, `guards.AREAS` values, `state.PHASES`, the gate floor tiers,
  `decision.CLASSES`, `workspace.POSTURES`, `workspace.AREAS` and `registry.known(port)` for
  every port; `cli/wuwei/telemetry.py` imports and `validate` runs with only its own
  directory on `sys.path` (no `wuwei` package). Red until the literals match.
- [X] T017 [US1] cli/wuwei/telemetry.py: fix the literals; keep `wuwei` imports inside
  functions.
- [X] T018 [US1] Test in tests/test_telemetry.py: `week_file` writes `final: false` for the
  current week and `final: true` with `proposals` for an earlier one, keeps `shared`,
  `ready` and `presented` from an existing file, rounds to two decimals. Red.
- [X] T019 [US1] cli/wuwei/telemetry.py `week_file`, `load_week`.
- [X] T020 [US1] Test in tests/test_telemetry.py: `step` with an `events.jsonl` over a
  monkeypatched `MAX_DAY_BYTES`, and with `BUDGET_SECONDS` 0, records exactly one
  `telemetry.skipped` with week and reason, keeps the previous file, saves
  `watch.telemetry.skipped`; a second call within 24 hours does nothing; `enabled = false`
  returns `off` and writes nothing. Red.
- [X] T021 [US1] cli/wuwei/telemetry.py `step` steps 1, 2 and 5 (plan.md).
- [X] T022 [US1] Test in tests/test_watch.py: `sweep` puts the step's status in
  `counts['telemetry']`; a step raising `ValueError` leaves `exit`, `owed` and `unreadable`
  as without it. Red: no key.
- [X] T023 [US1] cli/wuwei/watch.py `sweep`: the call after the steward block.
- [X] T024 [US1] Test in tests/test_metrics.py: `wuwei metrics --week <week>` prints the file;
  absent, computes and writes it; `--week bad` exits 2; bare `wuwei metrics` unchanged. Red.
- [X] T025 [US1] cli/wuwei/commands/metrics.py `--week`.
- [X] T026 [US1] Test in tests/test_board_mcp.py: the board text has a Telemetry table with
  the current week's metrics; with `watch.telemetry.skipped` set it shows `unmeasured` and
  the reason; with no file, `unmeasured`. Red.
- [X] T027 [US1] cli/wuwei/commands/board.py `read`: the Telemetry table.

## Phase 4: Proposals (US3)

- [X] T028 [US3] Test in tests/test_telemetry.py: fixtures for `floor-raise`, `area-block`
  and `wait-hours` each yield one proposal with the exact 5.13 command; a table test puts
  each of the five rules at and one below its threshold. Red.
- [X] T029 [US3] cli/wuwei/telemetry.py `proposals`.
- [X] T030 [US3] Test in tests/test_telemetry.py: `wuwei telemetry proposals` lists and writes
  nothing; `--widget` prints one widget per proposal (header `Telemetry`, `Yes` first,
  `record` the command), sets `presented`, appends one `telemetry.presented`; a second run
  prints `[]`. Red.
- [X] T031 [US3] cli/wuwei/commands/telemetry.py `proposals`; `telemetry` in
  cli/wuwei/__main__.py `GROUPS`; the four `telemetry` paths in cli/wuwei/commands/__init__.py
  `WRITES`.

## Phase 5: Sharing (US4)

- [X] T032 [US4] Test in tests/test_telemetry.py, the anonymiser corpus: seed the week with a
  repository name, a path, a handle, a ticket id, an item id, reason text and a full
  timestamp in every record field that carries them; `payload` has exactly the 5.13
  top-level keys and its JSON contains none of the seeded strings; `validate` raises for each
  corpus value injected as a metric value, a metric inner key, an adapter name and a version,
  for an extra top-level key, and for a payload over 16 KB. Red.
- [X] T033 [US4] cli/wuwei/telemetry.py `payload`, `validate`, `token`, `issue`.
- [X] T034 [US4] [P] Test in tests/test_adapters.py: `watch_service.post` refuses a non-https
  URL, returns the status of a stubbed `urlopen` (2xx and an `HTTPError` 409), sends
  JSON with the extra headers. Red.
- [X] T035 [US4] adapters/watch_service.py `post`.
- [X] T036 [US4] [P] Test in tests/test_code_host.py: `issue` is in the port interface; the
  GitHub adapter posts `repos/<repo>/issues` with title and body through the allowlist (a
  `PATH` stub or the module's `subprocess.run` replaced) and refuses an invalid repository;
  the none adapter returns exit 2. Red.
- [X] T037 [US4] cli/wuwei/registry.py `PARAMETERS`; adapters/code_host/github.py `issue` and
  the `_run` allowlist; adapters/code_host/none.py `issue`.
- [X] T038 [US4] Test in tests/test_telemetry.py: `step` under `anonymous` posts each unshared
  final week through a fake service with the token; 2xx and 409 mark `shared` and append
  `telemetry.shared`; 500, `OSError` and an empty endpoint append `telemetry.unsent` and
  keep the week; only the four newest weeks are tried; under `attributed`, one
  `telemetry.ready` per final week, once; under `""` and `off`, the fake sees no call. Red.
- [X] T039 [US4] cli/wuwei/telemetry.py `step` step 3.
- [X] T040 [US4] Test in tests/test_telemetry.py: `wuwei telemetry preview` names the mode in
  force, prints the anonymous payload with the token and the attributed title and body; the
  body equals `telemetry.issue(...)[1]` that `send` passes to the fake code host;
  `wuwei telemetry off` writes `share = "off"` with no confirmation and appends one
  `telemetry.off`; `send` refuses unless `attributed`, refuses a shared week, declines on a
  `no` (fake `_host_confirm`), refuses on a canary in the body, and on yes calls `issue` once
  and marks `shared`. Red.
- [X] T041 [US4] cli/wuwei/commands/telemetry.py `preview`, `off`, `send`.
- [X] T042 [US4] [P] Test in tests/test_interview.py: the `telemetry` question follows
  `posture` with the 5.13 question, labels and texts in order and the three
  `telemetry.share` effects. Red.
- [X] T043 [US4] cli/wuwei/interview.py `QUESTIONS`.
- [X] T044 [US4] Test in tests/test_doctor.py: with `share` unset and telemetry enabled,
  doctor lists `telemetry` as warn with `bin/wuwei calibrate --interview telemetry`; with
  `share = "off"` the row is ok. Adjust any doctor expectation the new row changes. Red.
- [X] T045 [US4] cli/wuwei/commands/doctor.py `_calibration`.

## Phase 6: OpenTelemetry export (US5)

- [X] T046 [US5] Test in tests/test_telemetry.py: `spans` over a fixture day maps a refusal
  row, a warning and a seat run to spans with the data-model.md attributes and a decision,
  a loop and a gate round to span events; no command text, reason or target reaches the body;
  it returns the end offset. `otlp_metrics` emits sums and gauges and omits `"unmeasured"`.
  `step` with `otlp.endpoint` posts to `/v1/traces` and `/v1/metrics` with the header from
  `headers_env`; a failed post keeps `otlp_at` and appends `telemetry.unsent` mode `otlp`;
  the header value is in no event and no output. Red.
- [X] T047 [US5] cli/wuwei/telemetry.py `spans`, `otlp_metrics`, `step` step 4, with the
  `ponytail:` note on allowed calls.
- [X] T047a [US5] Review fix: the OTLP export runs on every sweep, outside the once-a-day
  gate; a final week keeps an `otlp` mark and each of the newest four without it is posted
  again on the next sweep. `watch_service.post` does not follow redirects, so a 3xx comes
  back as its status and the headers never reach the Location host. Tests first in
  tests/test_telemetry.py and tests/test_adapters.py.

## Phase 7: Project side (US6)

- [X] T048 [US6] Test in tests/test_telemetry_worker.py (new; imports
  scripts/telemetry-worker/worker.py with `cli/wuwei` on `sys.path` as the deploy bundle
  does): `accept` returns 201 and `data/<week>/<token>.json` for a valid payload, 400 for
  invalid JSON, a failing payload or no token, 422 for a week outside the window, 409 for a
  repeat, 429 at 10 per IP and at 1000 writes; `summary.summarise` counts workspaces and sums
  integer metrics per week from a fixture directory. Red.
- [X] T049 [US6] scripts/telemetry-worker/worker.py, scripts/telemetry-worker/summary.py,
  scripts/telemetry-worker/README.md, .github/workflows/telemetry-label.yml.

## Phase 8: Template, skill and docs

- [X] T050 Test: run tests/test_docs.py after adding the commented `[telemetry]` and
  `[telemetry.otlp]` blocks to templates/workspace/config.toml; it fails on the undocumented
  keys, the missing `[telemetry]` section and the missing `bin/wuwei telemetry` command row.
  Add to tests/test_docs.py one test that the plan skill names
  `wuwei telemetry proposals --widget` and the security page states the IP address and the
  attributed login. Red.
- [X] T051 templates/workspace/config.toml, skills/wuwei-plan/SKILL.md,
  docs/site/configuration.md (keys and the OpenTelemetry paragraph), docs/site/reference.md
  (command row, `metrics --week`, heartbeat `ms`, host terminal action),
  docs/site/concepts.md (host terminal action), docs/site/security.md (what leaves).

## Phase 9: Finish

- [X] T052 Run `python -m pytest -q`; everything passes. Check every changed file for
  em-dashes, emojis and absolute local paths.

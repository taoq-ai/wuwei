# Tasks: posture profiles

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are in
plan.md. New behaviour tests go in a new `tests/test_posture.py` unless a task names another
file. A test sets a posture by writing `[security]\nposture = "<name>"\n` (and
`[security.areas]` lines) into the workspace `.wuwei/config.toml`.

## Phase 1: Config, resolver and the records floor (FR-001, FR-002, FR-003; US3-1, US6-1)

- [X] T001 In `tests/test_posture.py`, add failing tests for `workspace`: an empty config
  loads `security == {'required': False, 'posture': 'guarded', 'areas': {<six areas>: ''}}`;
  `workspace.posture(config)` returns `('guarded', {'integrity': 'block', 'mcp': 'warn',
  'publish': 'block', 'records': 'block', 'outward': 'warn', 'seats': 'warn'})`; `observe`
  gives every area `warn` except `records` `block`; `strict` gives every area `block`;
  `[security.areas] mcp = "off"` under guarded gives `mcp: off` and leaves the rest;
  `[guards] mode = "shadow"` with `posture = "strict"` gives name `observe`;
  `posture = "loose"` and `areas.mcp = "maybe"` raise `ConfigError` naming the key;
  `records = "warn"` and `records = "off"` raise `ConfigError` whose text names
  `security.areas.records` and `floor`; `records = "block"` loads. Fails today:
  `security.posture` is an unknown key.
- [X] T002 In `cli/wuwei/workspace.py`, add `AREAS`, `AREA_LEVELS`, `POSTURES`, `FLOORS`,
  the `security` schema, the floor check in `load_config` and `posture()` (plan.md 1). T001
  passes; run `tests/test_workspace.py`.
- [X] T003 In `tests/test_posture.py`, add a failing `config check` test (issue acceptance 3):
  with `[security.areas]\nrecords = "warn"\n`, `main(['config', 'check'])` returns 1 and
  stderr names `security.areas.records` and the floor. With `[security.areas]\nmcp = "off"\n`
  stdout has `Posture: guarded`, `  mcp: off (security.areas)`, `  records: block (floor)`
  and the owner-only line; with `[guards]\nmode = "shadow"\n` it has `Posture: observe` and
  one line containing `deprecated` and `security.posture = "observe"`, and the exit code is
  the same as without it. Reuse the setup of the `main(['config', 'check']) == 0` tests in
  `tests/test_env_credentials.py` so credentials and host protections do not decide the
  exit. Fails today: no Posture section (the floor case already exits 1 for
  the unknown key, so assert the floor text).
- [X] T004 In `cli/wuwei/commands/config.py`, print the Posture section and the deprecation
  line (plan.md 6). T003 passes.

## Phase 2: Guard areas and the hook decision point (FR-004, FR-005; US1, US2-3/4, US3-2, US4-3)

- [X] T005 In `tests/test_posture.py`, add a failing meta-test for `wuwei.guards`: the
  module-level keys of `AREAS` (those without a dot) equal `set(MODULES)`; every value is in
  `workspace.AREAS` or is `None` only for `agent_launch.check_mcp`; every `OWNER_ONLY` entry
  names a module in `MODULES` or a `module.function` that exists; `level(check, levels)` for
  `outward.check_tier` and `deploy.check` is `block` with `owner-only` in the line under
  observe levels; for `protect_state.check_file` it is `block` with `floor`; for
  `commit_push.check` under observe it is `('commit_push', 'publish', 'warn', 'posture:
  publish = warn (set security.areas.publish)')`; for a lambda from an unknown module it is
  `block` with an empty line. Fails today: no `AREAS`.
- [X] T006 In `cli/wuwei/guards/__init__.py`, replace `NEVER_SHADOWED` with `AREAS`,
  `OWNER_ONLY` and `level` (plan.md 2). T005 passes.
- [X] T007 In `tests/test_hooks.py`, rewrite the shadow tests against the posture (they use
  the `plugin` fixture, `install`, `refusing`, `events_of`, `assert_refusal`):
  (a) `test_never_shadowed_guards_refuse_in_shadow_mode` becomes a posture table test: under
  `observe`, a stub installed under `protect_state`, `deploy` and `pr` each returning
  `(1, 'kept')` is refused with stderr `kept\nposture: <area> = block (<floor or owner-only
  text>)\n` and no `guard.would_refuse`; a stub under `commit_push` and one under
  `integrity` are recorded with `area`, `level: 'warn'`, `posture: 'observe'` and exit 0;
  under `strict` the `commit_push` stub is refused with `posture: publish = block (set
  security.areas.publish)`; with `[security.areas] publish = "off"` under strict it exits 0
  and writes no event (US2-4);
  (b) `test_shadow_mode_records_and_allows`, `..._target_is_the_normalised_command`,
  `..._target_is_redacted` and `..._enforces_when_it_cannot_record` keep `mode = "shadow"`
  but make the `fake` stub warn with `plugin[1].setitem(wuwei.guards.AREAS, 'fake',
  'publish')`; the recorded payload additionally holds `area`, `level`, `posture`;
  (c) `test_enforce_mode_refuses_as_before` also runs with `posture = "strict"` and with the
  default, and the stub `fake` (no area) is refused byte-identically with no posture line
  (US4-3);
  (d) the heartbeat test stays as is.
  Fails today: no posture lines, no `area` field, `fake` is shadowed.
- [X] T008 In `cli/wuwei/commands/hook.py`, carry the check in `refusals`, replace `shadow`
  with `posture`, append posture lines to the shown reasons and keep raw reasons in
  `hook.refusal.refusals` (plan.md 3). T007 passes; run all of `tests/test_hooks.py`.
- [X] T009 In `tests/test_e2e_day.py`, add the failing end-to-end test for issue acceptance
  1 with the `day` fixture: after appending `[security]\nposture = "observe"\n` (and the
  identity line the existing shadow e2e test adds), `git push --force origin main` in
  `day.repo` returns `''` and the last event is `guard.would_refuse` with `guard:
  commit_push`, `area: publish`, `level: warn`, `posture: observe`; a `Write` to
  `day.directory / 'state.json'` exits 2 and its `permissionDecisionReason` contains
  `posture: records = block`; `day.bash(['decision', 'outcome', 'D-1', 'A'], expected=2)`
  still refuses; after the unconfirmed plugin change a `Read` exits 0 and the last event is
  `guard.would_refuse` with `area: integrity` (US1-5). Update
  `test_shadow_mode_records_force_push_and_keeps_records_refused` the same way for its
  integrity step (shadow is observe, integrity warns). Passes after T008 except the integrity
  step if anything is missing; fix in T008 scope only.

## Phase 3: MCP level and the launch gate record (FR-006, FR-007; US2-1/2, US3-3, US4-1)

- [X] T010 In `tests/test_mcp.py`, add failing tests (issue acceptance 2):
  (a) with `[security.areas]\nmcp = "off"\n` and a discovered project server, `core().check`
  returns exit 0 with reason `MCP registry: not checked (security.areas.mcp = "off")`, the
  fake scanner is never called, no `mcp.checked` or `mcp.finding` event is written and
  `.wuwei/ziran/status.json` does not exist; `core().cached` returns 0 with the same reason;
  (b) the same config: `plan.propose(proposal(), configured)` succeeds, its plan's sweep line
  names `not checked`, and `status.attention(day)` has no row whose source starts with
  `mcp.`;
  (c) extend `test_posture_block_table` with a posture column: every existing row keeps its
  `cached_exit` under the default (`guarded`); under `strict` the `(None, 'unmeasured')` and
  `('[]', 'critical')` rows block (2 and 1); under `observe` every row's `cached` is 0;
  every non-zero `cached` reason contains `mcp: ` and either `floor: scanner.mcp.block` or
  `security.areas.mcp`.
  Fails today: the mcp level is not read.
- [X] T011 In `cli/wuwei/mcp.py`, add `NOT_CHECKED`, the off return in `check`, and the
  `cached` wrapper over `_cached(root, block)` (plan.md 5). T010 passes; run all of
  `tests/test_mcp.py`.
- [X] T012 In `tests/test_agent_launch.py`, add failing tests: `agent_launch.GUARDS` holds a
  `check_mcp` record before `check` for `('PreToolUse', 'Agent')`; with `mcp.cached` patched
  to return `Result(1, 'MCP registry findings: x')`, `check_mcp` on a WUWEI seat payload in
  scope returns that result and `check` no longer calls `mcp.cached`; for a non-WUWEI
  `subagent_type` `check_mcp` returns `(0, '')`. Through the hook (`tests/test_hooks.py`
  `plugin` fixture, default `guarded`), a WUWEI Agent launch with the MCP gate refusing is
  denied even though `seats` is `warn` (US3-3 at the hook). Fails today: no `check_mcp`.
- [X] T013 In `cli/wuwei/guards/agent_launch.py`, extract `_seat`, add `check_mcp`, drop the
  `mcp.cached` call from `_check` and reorder `GUARDS` (plan.md 4). T012 passes; run
  `tests/test_agent_launch.py`, `tests/test_launch_contract.py`, `tests/test_guard_mutation.py`.

## Phase 4: Surfaces (FR-008; US5, US6-2)

- [X] T014 In `tests/test_shadow.py`, update and add failing tests: the status parametrize
  writes `[security]\nposture = "observe"` (and the old `[guards]\nmode = "shadow"` row
  stays as the deprecated form); `data['posture']` is `observe`, `guarded` or `strict`;
  `status.line(data)` contains ` | observe` and ` | strict` for those postures and no
  posture part for `guarded`; the `guards.shadow` nudge reason contains
  `security.posture = "guarded"` and `guards.shadow_days`; the SessionStart test asserts the
  observe line (`Observe posture is on`) under `observe` and under `mode = "shadow"`, and
  none under `guarded`. Fails today: `shadow` field and old texts.
- [X] T015 In `cli/wuwei/commands/status.py` and `cli/wuwei/guards/lifecycle.py`, apply
  plan.md 7 (nudge text, scan condition, `posture` field and part) and plan.md 9. T014
  passes.
- [X] T016 In `tests/test_signal_status.py` (or `tests/test_posture.py`), add failing tests:
  `classify` of a `guard.would_refuse` with `posture: 'guarded'` is `nudge`, with
  `posture: 'observe'` or no posture `silent`; `status.attention` over a day with three
  `guard.would_refuse` events from `outward` and one from `agent_launch`, all `posture:
  'guarded'`, yields exactly two nudge rows whose reasons name `security.areas.outward` and
  `security.areas.seats`. Keep `test_emitted_kinds_have_intended_tiers` expecting `silent`
  for the bare kind. Fails today: the kind is always silent.
- [X] T017 In `cli/wuwei/signal.py` and `cli/wuwei/commands/status.py`, apply plan.md 8 and
  the scan key and reason of plan.md 7. T016 passes.
- [X] T018 In `tests/test_why.py`, add a failing case: a `guard.would_refuse` with `area:
  'publish', level: 'warn', posture: 'observe'` prints `posture: publish = warn (observe)`
  after its fix line; the existing `SHADOWED` case without `area` is unchanged. Then apply
  plan.md 10 in `cli/wuwei/commands/why.py`.
- [X] T019 In `tests/test_workspace.py`, update `test_init_shadow` and add failing cases:
  `init --posture strict` writes `posture = "strict"` and leaves `shadow_since = ""`;
  `init --posture observe` and `init --shadow` write `posture = "observe"` and today's
  `shadow_since`; plain `init` writes the template bytes unchanged and its config resolves
  to `guarded`; `--posture` with `--upgrade` raises `ValueError`. Fails today: no
  `--posture`, the template has no `posture` line.
- [X] T020 In `cli/wuwei/commands/init.py` and `templates/workspace/config.toml`, apply
  plan.md 11 (init and template). T019 passes; run `tests/test_docs.py` (template keys
  documented) after T026 if it fails only on docs.
- [X] T021 In `tests/test_interview.py`, replace the `guards` question tests: the question
  ids end with `'posture'`; `settings({'posture': 'Observe'}, {})` is
  `[(('security',), 'posture', 'observe'), (('guards',), 'shadow_since', '2026-09-29')]`;
  `Guarded` and `Strict` yield only the posture row; with `shadow_since` already set no date
  row is added; the parse test at line 402 uses the new answer. Fails today: no `posture`
  question.
- [X] T022 In `cli/wuwei/interview.py`, replace the question and the `settings` condition
  (plan.md 11). T021 passes.
- [X] T023 In `tests/test_calibrate.py`, add `('security.posture', 'observe', True, '')` and
  `('security.areas.mcp', 'off', True, '')` to `REVIEWED` (refused as personal keys), and a
  check that `profiles` export of a config with `posture = "strict"` carries no `security`
  key. Fails today: `security` is not private. Then add `'security'` to `PRIVATE` and
  `NOT_LITERALS` in `cli/wuwei/profiles.py`.

## Phase 5: Default posture across the suite (US4-1/2, SC-002)

- [X] T024 Run the full suite: `python -m pytest -q`. For each failure, decide by cause:
  a test that depends on seats, outward (lint) or MCP blocking through a hook gets
  `[security]\nposture = "strict"\n` in its own config (or its fixture, when every test in
  the file depends on it, for example the strict-profile outward tests in
  `tests/test_profiles.py`, the Agent-launch hook tests and the `tests/fakes/day.py` steps
  that expect an Agent refusal); a test asserting the old shadow texts, the `shadow` status
  field or `NEVER_SHADOWED` is updated to the posture form. Any other failure is a bug in
  T002-T023: fix the code, not the test. Record in the task which files were pinned to
  strict.
  Done: pinned to strict: the `configured` fixture of `tests/test_profiles.py` (outward
  lint). Updated to the posture form: `tests/test_mcp.py::test_morning_check_before_launch`
  (the MCP gate is now `check_mcp`), `tests/test_guard_mutation.py` (a probe for
  `check_mcp`), `tests/test_hooks.py::test_import_map_matches_guard_tables` (two Agent
  records share one matcher). The Agent-launch hook tests and `tests/fakes/day.py` needed no
  pin: their refusals already come from integrity or protect_state, which block under guarded.
- [X] T025 Add `tests/test_posture.py::test_hook_level_suites_pass_under_strict` only if
  T024 shows a file whose guard or hook tests were not run under `strict` anywhere; otherwise
  note here that the strict pins of T024 cover acceptance 4. Run
  `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency` and confirm the budgets
  hold.
  Done: no extra test; the strict pins of T024 and the strict rows of
  `test_posture_block_table`, `test_enforce_mode_refuses_as_before` and
  `test_posture_levels_at_the_hook` cover acceptance 4. Budgets hold with `WUWEI_BENCH=1`.

## Phase 6: Docs (FR-009)

- [X] T026 Update `docs/site/security.md` (new `## Security posture` with the table, floors,
  guard areas and where to run each posture), the design spec 9.1 amendment paragraph,
  `docs/site/configuration.md` (keys, deprecated `guards.mode`, interview row, profiles
  paragraph), `docs/site/concepts.md` (`## Security posture` replacing `## Shadow mode`),
  `docs/site/reference.md` (`init --posture`, event payload, status part, nudge, why, deny
  posture line), `docs/site/daily.md` and `README.md` (first week with
  `init --posture observe`), and every `#shadow-mode` link (plan.md 12). Run
  `tests/test_docs.py`.
- [X] T027 Run the full suite (`python -m pytest -q`); everything passes. Grep the changed
  files for em-dashes and emojis and remove any; confirm no absolute local path was written.

# Tasks: Shadow mode

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are
in plan.md. New behaviour tests go in a new `tests/test_shadow.py` unless a task names
another file. A test that needs shadow mode writes `[guards]` and `mode = "shadow"` into
the workspace `.wuwei/config.toml`.

## Phase 1: Config (FR-001)

- [X] T001 In `tests/test_workspace.py`, add failing tests: an empty config loads
  `guards == {'mode': 'enforce', 'shadow_days': 7, 'shadow_since': ''}`;
  `mode = "shadow"` with `shadow_since = "2026-09-25"` loads; `mode = "off"`,
  `shadow_days = 0`, `shadow_since = "next week"` and `shadow_since = "20260925"` each
  raise `ConfigError` naming the key. Fails today: `guards` is an unknown key.
- [X] T002 In `cli/wuwei/workspace.py`, add the `guards` table to `SCHEMA` and the
  `shadow_since` check in `load_config`; in `templates/workspace/config.toml`, append the
  `[guards]` table; in `docs/site/configuration.md`, document the three keys (plan.md 1, 10).
  Run `tests/test_docs.py` and `tests/test_workspace.py`.

## Phase 2: The decision point (US1, US2, US3; FR-002, FR-003)

- [X] T003 In `tests/test_hooks.py`, add failing tests using the `plugin` fixture, a
  `.wuwei/config.toml` with shadow mode, and `tests/payloads/PreToolUse/bash.json`:
  (a) a stub module `fake` returning `(1, 'guard reason')` exits 0 with empty stdout, and
  today's events hold exactly one `guard.would_refuse` with
  `{'guard': 'fake', 'reason': 'guard reason', 'target': 'npm test', 'session': <payload
  session_id>, 'item': None}` and no `hook.refusal`;
  (b) the same for a Stop and a PostToolUse stub (exit 0, event written);
  (c) with `session_id = 'wuwei-heartbeat'` the refusal is enforced (`assert_refusal`) and
  no `guard.would_refuse` is written;
  (d) with `state.append_event` monkeypatched to raise `OSError` the call is denied
  (exit 2, deny JSON) and stderr names `could not record shadow refusal`;
  (e) with no config file, and with `mode = "enforce"`, the stub is refused exactly as
  today and no `guard.would_refuse` is written;
  (f) a Bash `sh -c 'git push --force origin main'` target is recorded as
  `git push --force origin main`; a command that does not parse is recorded raw.
  Fails today: the hook ignores the mode.
- [X] T004 In `tests/test_hooks.py`, add the failing never-shadowed meta-test:
  `guards.NEVER_SHADOWED == {'protect_state', 'integrity', 'deploy', 'outward', 'pr'}`, every
  name is in `guards.MODULES` and the shadowable complement is pinned too; for each name, install a stub module under that name returning
  `(1, 'kept')` (first `monkeypatch.delitem(sys.modules, 'wuwei.guards.<name>',
  raising=False)` so the real module is not reused) and replay the bash payload in shadow
  mode: refused with exit 2 and a deny decision, no `guard.would_refuse`. With a second
  stub `fake` also refusing, the deny reason is `kept` only and one `guard.would_refuse`
  names `fake`. Fails today: no `NEVER_SHADOWED`.
- [X] T005 In `cli/wuwei/guards/__init__.py`, add `NEVER_SHADOWED`; in
  `cli/wuwei/commands/hook.py`, tag refusals by module and add `shadow`, `target` and
  `claimed` (plan.md 2, 3). T003 and T004 pass.
- [X] T006 Add a failing end-to-end test in `tests/test_e2e_day.py` with the `day`
  fixture (`tests/fakes/day.py`) after appending shadow mode to its `config.toml`
  (issue acceptance 1 and 2):
  (a) `day.hook('PreToolUse', tool_name='Bash', cwd=str(day.repo), tool_input={'command':
  'git push --force origin main'})` exits 0, and the last event is `guard.would_refuse`
  with `guard == 'commit_push'` and a reason naming the force push;
  (b) a `Write` to `day.directory / 'state.json'` exits 2 with a deny decision;
  (c) `day.bash(['decision', 'outcome', 'D-1', 'A'], expected=2)` is still refused;
  (d) after the unconfirmed plugin change of `test_unconfirmed_plugin_change_denies_pretooluse`,
  a `Read` is still denied.
  Then confirm it passes with T005 in place; if (a) needs a claimed item, also assert
  `item`. Fails before T005.
- [X] T007 Run `tests/test_hooks.py`, `tests/test_guard_mutation.py`,
  `tests/test_protect_state.py`, `tests/test_commit_push.py`, `tests/test_heartbeat.py` and
  `tests/test_e2e_day.py` unchanged (issue acceptance 3); with `WUWEI_BENCH=1` run
  `tests/test_hooks.py -k latency`. Fix the code, never these tests.

## Phase 3: Producer-only event (FR-004)

- [X] T008 In `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`, add
  `'guard.would_refuse': 'silent'` to `expected`; in `tests/test_shadow.py`, add a failing
  test that `main(['event', 'guard.would_refuse', '{}'])` returns 1 and prints
  `reserved; written by wuwei hook (shadow mode)`. Fails today: the tier test sees an
  unexpected emitted kind and the producer text is the generic one.
- [X] T009 Add the kind to `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py` and to
  `SILENT` in `cli/wuwei/signal.py`.

## Phase 4: Report (US4, FR-005)

- [X] T010 In `tests/test_shadow.py`, add failing table tests for
  `report.shadow_lines(directories)` on day directories written with
  `state.append_event` (`WUWEI_NOW` fixed): no events gives `[]`; five `commit_push`
  events over two days (four `git push --force ...`, one `git push origin x`) and one `pr`
  event give the exact lines of plan.md 6, guards in count order, at most three forms per
  guard; the four-times form is a candidate; adding a `base.red` event (page tier) after
  its first refusal removes it from the candidates; a page event before the first refusal
  does not; exactly 3 refusals is not a candidate. Fails today: no `shadow_lines`.
- [X] T011 In `cli/wuwei/report.py`, add `FALSE_POSITIVE_AFTER` and `shadow_lines`.
- [X] T012 In `tests/test_report_retro.py` (or the existing day report test file), add
  failing tests: with today's `guard.would_refuse` events, `report.build` contains
  `## Shadow` and the grouping, at `owner.verbosity.report` `brief` and `full`; without
  them the text equals the output of the same workspace before any shadow event (no
  `## Shadow`). Fails today.
- [X] T013 Add the `## Shadow` section to `report.build` (plan.md 6).
- [X] T014 In `tests/test_shadow.py`, add failing tests for `main(['shadow', 'report'])`:
  exit 0 and `# WUWEI shadow report` then `none` with no events; with events on
  2026-09-28 and 2026-09-29 and `shadow_since = "2026-09-29"` only the second day counts;
  with `shadow_since = ""` both count; a corrupt `events.jsonl` line exits 2; outside a
  workspace exits 2. Fails today: no `shadow` command.
- [X] T015 Add `cli/wuwei/commands/shadow.py` (plan.md 7) and its row in
  `docs/site/reference.md` `## Commands`. Run `tests/test_docs.py`.

## Phase 5: Visible and time-boxed (US5, FR-006, FR-007)

- [X] T016 In `tests/test_shadow.py`, add failing status tests with a day directory and
  `WUWEI_NOW`: shadow mode gives `status --line` a ` | shadow` part and
  `snapshot(...)['shadow'] is True`; enforce mode gives no part and `False`;
  `shadow_since` seven days before today gives exactly one `attention(...)` row with
  `source == 'guards.shadow'`, tier `nudge` and a reason naming `guards.mode = "enforce"`
  and `guards.shadow_days`, and `snapshot(...)['nudges']` counts it once (issue acceptance
  4); six days gives none; `shadow_days = 3` with four days gives one; empty
  `shadow_since` gives none. Fails today.
- [X] T017 In `cli/wuwei/commands/status.py`, add `SHADOW_NUDGE`, the `scan` row, the
  `snapshot` field and the `line` part (plan.md 8).
- [X] T018 In `tests/test_shadow.py` (or `tests/test_hooks.py` next to the SessionStart
  tests), add a failing test: `lifecycle.session_start` on a workspace in shadow mode
  returns a context containing `Shadow mode is on` and `bin/wuwei shadow report`; in
  enforce mode it does not. Fails today.
- [X] T019 Add `SHADOW_LINE` to `cli/wuwei/guards/lifecycle.py` `session_start` (plan.md 5).

## Phase 6: Writers of the mode (US6, FR-008)

- [X] T020 In `tests/test_workspace.py` (next to the init template test), add failing
  tests: `init --shadow <path>` writes a config whose `guards.mode` is `shadow` and
  `guards.shadow_since` is `WUWEI_NOW`'s date, and `load_config` accepts it; plain `init`
  still equals the template bytes; `init --upgrade --shadow` exits 2. Fails today: unknown
  option.
- [X] T021 Add `--shadow` to `cli/wuwei/commands/init.py` (plan.md 9).
- [X] T022 In `tests/test_interview.py`, append `'guards'` to the pinned id list in
  `test_question_table_fits_widgets_and_every_choice_validates`, and add a failing test:
  `interview.settings({'guards': 'Shadow first week'}, config)` equals
  `[(('guards',), 'mode', 'shadow'), (('guards',), 'shadow_since', <today>)]`;
  `'Enforce'` gives only the mode. Fails today: unknown question.
- [X] T023 Add the `guards` question and the `settings` line to `cli/wuwei/interview.py`
  (plan.md 9); add the question to the owner interview section of
  `docs/site/configuration.md`.

## Phase 7: Docs and full run (FR-009)

- [X] T024 Update `docs/site/concepts.md` (`## Shadow mode`), `docs/site/daily.md`
  (first-week path in `## 2. Configure`), `README.md` `## Quick start` (`bin/wuwei init
  --shadow .`), and `docs/site/reference.md` (`init --shadow`, the `shadow` status part,
  the `guards.shadow` nudge, the `guard.would_refuse` payload) per plan.md 10. Follow the
  humanizer checklist; no em-dashes, no emojis.
- [X] T025 Run the full suite with `python -m pytest -q`; everything passes. Grep the
  changed files for em-dashes, emojis and absolute local paths and remove any.

## Phase 8: Review fixes

- [X] T026 Add `outward` and `pr` to `NEVER_SHADOWED` and pin the shadowable complement in
  the meta-test, so a new guard module fails until it is placed (review F1, F3).
- [X] T027 Redact the `guard.would_refuse` target with `redact.redact` and
  `security.redact` before recording; test that the canary and a URL token are absent
  from the event and the report (review F2).
- [X] T028 `interview.settings` writes `shadow_since` only when it is unset (review F4).

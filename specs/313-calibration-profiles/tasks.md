# Tasks: shareable calibration profiles: export a promoted calibration and interview, import as a proposal

**Input**: `specs/313-calibration-profiles/spec.md`, `specs/313-calibration-profiles/plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Every behaviour is a test task followed by its implementation task. Run each test, see it
fail for the expected reason, then implement the minimum that makes it pass. `[P]` marks
tasks that touch different files and can run in parallel. Profile tests go at the end of
`tests/test_calibrate.py` to reuse its `workspace_root`, `ports`, `configure`, `main` and
`promote` helpers.

## Phase 1: The deny table and the review (US2, US3)

- [X] T001 Test: in `tests/test_calibrate.py`, a parametrized table test over
  `profiles.review(profile, config, names)` with a config built from
  `templates/workspace/config.toml` plus one repository `acme/widget`:
  refused, each named by its dotted key: `repos.merge.auto = true`;
  `decisions.cruise.levels.approach = 2` with the workspace at `levels.approach = 1`;
  `decisions.cruise.levels.defer = 1` (default L0); `decisions.cruise.enabled = true`
  with the workspace at `enabled = false`; `repos.gates.floor = "light"` with the
  workspace at `standard`; `shepherd.autostart = true`; `adapters.scanner = "ziran"`;
  `calendar.url`, `watch.ping_url`, `codex.command`; `gates.second_opinion = "codex:gpt-5"`; private keys `owner.name`,
  `repos.identity.email`, `shepherd.review_channel`, `guards.mode`. Accepted (not
  refused): `decisions.cruise.levels.approach = 1`, `repos.gates.floor = "full"`,
  `repos.merge.auto = false`, `repos.fast_checks`, `deploy.deny`,
  `gates.second_opinion = "off"`. Also: `_shape` rejects
  a non-object, `wuwei_profile` 2, a name `Bad Name`, `config` a list, `config.repos` a
  list, an unknown role `nope`, a role without `text` or with `reasons` not a list of
  strings; `review` with a `repos` part and no configured repository raises the
  `NO_REPOS` reason; `settings` expands `repos.gates.floor` to
  `(('repos', 0, 'gates'), 'floor', 'full')` for each target in configuration order.
  Expect ModuleNotFoundError (`wuwei.profiles`).
- [X] T002 Implement in `cli/wuwei/profiles.py`: `PLUGIN`, `STARTERS`, `ROLES`,
  `PRIVATE`, `FLOORS`, `DENIED`, `_leaves`, `_nest`, `_strings`, `_current`, `refusal`,
  `_shape`, `review` (refusals only), `settings`. T001 passes.
- [X] T003 Test: in `tests/test_calibrate.py`, `profiles.review` flags instruction-like
  text: a builder `text` whose third line is an override-of-previous-instructions phrase
  gives `('charters.builder:3', 'override')` and no `builder` in `accepted['charters']`
  while a clean `planner` role stays; a reason with a push-to-main phrase flags
  `charters.<role> reason 1` and drops that role; a `deploy.deny` item with a bypass
  phrase flags `deploy.deny` and drops only that key. Build the phrases in the test from
  `calibrate.INSTRUCTION_LIKE` examples already used in `tests/test_calibrate.py`.
  Expect the assertion on `flagged` to fail.
- [X] T004 Implement the flag pass of `profiles.review` with `calibrate.instruction_like`.
  T003 passes.

## Phase 2: Reading a source (US2, US4)

- [X] T005 Test: in `tests/test_calibrate.py`, `profiles.read`: a local file path; a
  starter name (with `profiles.STARTERS` monkeypatched to a `tmp_path` directory, since
  the shipped starters land in T018); an `https://` URL
  with `urllib.request.urlopen` monkeypatched to a fake response; `http://x` raises
  `ValueError` without calling `urlopen`; a fake response whose `geturl()` is `http://...`
  raises; a file of `calibrate.MAX_BYTES + 1` bytes, invalid JSON and a bad shape raise.
  Expect AttributeError (no `read`).
- [X] T006 Implement `profiles.read` in `cli/wuwei/profiles.py`. T005 passes.

## Phase 3: Import writes proposals only (US2)

- [X] T007 Test: in `tests/test_calibrate.py`, `main('calibrate', 'import', <file>)` with
  one repository `acme/widget` (fixture `python`): a profile with `repos.fast_checks`,
  `repos.gates.floor = "full"`, `deploy.deny = ["twine upload*"]` and a builder block of
  two lines (one already in `charters/builder.md`) exits 0; prints the diff with
  `floor = "full"` and `proposals/profile-builder.json`; writes
  `.wuwei/days/2026-10-01/profile.json` (`repos == ["acme/widget"]`) and
  `profile-builder.json` (`action` add, the one new line only, `reason` starting
  `profile <name>`, `evidence` `.wuwei/days/2026-10-01/profile.json`); `config.toml` is
  byte-identical and `.wuwei/charters/` is unchanged.
- [X] T008 Test: in `tests/test_calibrate.py`, import variants: `--skip
  repos.gates.floor` leaves the floor out of `profile.json` and the diff; `--skip
  charters.builder` writes no builder proposal and removes the one from an earlier
  same-day import; `--skip nope.key` exits 2 and writes nothing; a profile with
  `repos.merge.auto = true` and `owner.name` exits 1, stderr names both keys, nothing is
  written under `.wuwei/days`; a flagged builder block exits 1 and still writes
  `profile.json` with the config part; no configured repository exits 2 with the
  `NO_REPOS` reason; `--repo acme/other` exits 2; an unknown config key (`repos.nope`)
  exits 2 from the preview; `import` without a source exits 2.
- [X] T009 Implement `profiles.skip` and `profiles.record` in `cli/wuwei/profiles.py`,
  and in `cli/wuwei/commands/calibrate.py` the `action`, `target` and `--skip`
  arguments, the `if args.action` dispatch and the import half of `_profile`. T007 and
  T008 pass; every existing calibrate and interview test passes unchanged.

## Phase 4: Promote applies only what was accepted (US2)

- [X] T010 Test: in `tests/test_calibrate.py`, after the T007 import, `promote(root,
  confirm)` (the existing helper) prints `Profile <name>: repos.0.gates.floor = "full"`
  in the summary, writes `floor = "full"` and `"twine upload*"` into `config.toml`; with
  an interview answer `gates=Standard` recorded the same day the interview value wins
  and no error is raised; `promotion.promote(root)` lands `profile-builder.json` and the
  ledger reason starts with `profile <name>`. A forged `profile.json` (a refused key; an
  instruction-like line; a repository name not configured; not JSON; a symlink) makes
  `promote` return 2 and leaves `config.toml` byte-identical.
- [X] T011 Implement `profiles.load` in `cli/wuwei/profiles.py` and the three-line change
  in `promote` in `cli/wuwei/commands/config.py`. T010 passes.
- [X] T012 [P] Test: in `tests/test_protect_state.py`, mirror
  `test_interview_answers_are_protected` for `.wuwei/days/2026-10-01/profile.json`
  (Write and Bash both refused with `outside agent tools`). Expect the assertion to fail.
- [X] T013 [P] Implement: add `'profile.json'` to the day-file tuple in
  `cli/wuwei/guards/protect_state.py:194`. T012 passes.

## Phase 5: Export without anything personal (US1)

- [X] T014 Test: in `tests/test_calibrate.py`, the redaction scenario. Config with
  `owner.name = "Pat Example"`, `owner.handles = ["U12345"]`,
  `control_plane.owner = "T0AAA/U0BBB"`, `shepherd.review_channel = "C0CCC"`,
  repository `acme/widget` at the absolute fixture path with `fast_checks`,
  `[repos.gates] floor = "full"` and `trust_paths`; `.wuwei/charters/builder.md` = the
  shipped builder charter plus lines: a heading naming `acme/widget`, a line naming
  `Pat Example`, a line with a `ghp_` token built by concatenation, a line with
  `/srv/pat/src/x`, and two plain rule lines; a ledger row landing that target with
  reason `calibration of acme/widget: repository conventions` and one with
  `owner interview: interrupt`. With `ports['redactor']` the real builtin adapter and
  `chdir` to `tmp_path`, `main('calibrate', 'export', 'team')` exits 0; the text of
  `team.json` contains none of `Pat Example`, `U12345`, `T0AAA`, `U0BBB`, `C0CCC`, the
  token, `acme/widget`, `str(workspace_root)`, `str(Path.home())` or `/srv/pat`; it
  keeps `fast_checks`, `floor`, `trust_paths`, the two plain lines and the interview
  reason; `dropped` has entries for `config.owner.name`, `config.control_plane.owner`,
  `config.shepherd.review_channel` and each dropped charter line and reason, with `why`
  in (`personal`, `absolute path`, `secret`). Then the same file imports into a second
  workspace with one repository with exit 0.
- [X] T015 Test: in `tests/test_calibrate.py`, export edges: `merge.auto = true` (with
  `merge_deploys = false`), `gates.floor = "light"` and `shepherd.autostart = true` are
  absent from `config` and listed as `outside what a profile may carry`; `--repo
  acme/gadget` exports that repository's `fast_checks`; exit 2 and no `<name>.json` for:
  name `Team`, an unknown `--repo`, an existing `team.json` (left byte-identical), a
  symlinked `.wuwei/charters/builder.md`, a ledger line that is not JSON, and a redactor
  stub returning `Result(2, None, 'down')`.
- [X] T016 Implement `ABSOLUTE`, `_template`, `_changed`, `_why` and `export` in
  `cli/wuwei/profiles.py`, and the export half of `_profile` in
  `cli/wuwei/commands/calibrate.py` (`atomic_write(..., replace=False)`). T014 and T015
  pass.

## Phase 6: Starters, docs, hook path (US4)

- [X] T017 Test: in `tests/test_calibrate.py`, for each file in `templates/profiles/`
  (exactly `cli-tool.json` and `python-library.json`): `main('calibrate', 'import',
  <stem>)` in a fresh workspace with one repository exits 0, prints a non-empty diff,
  and writes at least one charter proposal; the file has `"dropped": []`. Expect a
  failure (directory missing).
- [X] T018 Add `templates/profiles/python-library.json` and
  `templates/profiles/cli-tool.json` with the content in plan.md section 5. T017 passes.
- [X] T019 [P] Test: in `tests/test_docs.py`, `## Calibration profiles` follows
  `## Owner interview` in `docs/site/configuration.md` and names `calibrate export`,
  `calibrate import`, `--skip`, `profile.json`, `templates/profiles/`, `python-library`,
  `cli-tool`, `merge.auto`, `gates.floor`, `shepherd.autostart`, `decisions.cruise`,
  `adapters`; the `bin/wuwei calibrate` row of `docs/site/reference.md` names `export`
  and `import`. In `tests/test_hooks.py::test_calibrate_is_off_every_hook_path`, add
  `"wuwei.profiles"` to the module set. Expect the docs test to fail.
- [X] T020 [P] Write the section in `docs/site/configuration.md` and update the
  calibrate row in `docs/site/reference.md` (plan.md section 6), following
  `owner.verbosity` brevity and the humanizer checklist. T019 passes.

## Phase 7: Finish

- [X] T021 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file written for em-dashes, emojis and absolute local paths, and remove any.

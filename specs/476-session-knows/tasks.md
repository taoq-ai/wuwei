# Tasks: the session knows the whole plugin at start

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the task names. Signatures, texts and layout are in plan.md.
Fixtures: `tmp_path` workspaces, the `root` and `calibrated` helpers and the SessionStart
`hook`/`context` helpers of `tests/test_next.py`, the PreToolUse `hook` helper pattern of
`tests/test_cli_known_command.py`, the `evidence()` pattern of `tests/test_headless_e2e.py`.
Neutral names only; no absolute local path in any file.

## Shared block writer (FR-003, US1 scenario 3)

- [X] T001 In `tests/test_memory.py`, add failing tests for `memory.write_block`: with an
  owner paragraph and a rules block already in CLAUDE.md, writing a second block with other
  markers keeps both byte for byte and returns `(path, True)`; writing the same block again
  returns `(path, False)` and leaves the file's mtime and bytes unchanged; `write=False`
  returns `changed` and writes nothing; two start markers or a start without an end raise
  `ValueError` naming the `fix` argument; an absolute, `..`, `.wuwei/` or symlinked
  `export_to` raises the existing messages. Then `memory.export` after the second block
  leaves that block unchanged. Fails today: `AttributeError: write_block`.
- [X] T002 In `cli/wuwei/memory.py`, extract `write_block(root, start, end, block, fix,
  write=True)` from `export` and make `export` call it (plan.md). The existing
  `tests/test_memory.py` export tests stay green unchanged.

## The reference text (FR-001, US1 scenario 4)

- [X] T003 In `tests/test_guide.py` (new), add failing tests for `guide.text()`: every name in
  the `Daily` and `Recovery` groups of `__main__.GROUPS` appears as `- <name>: <help>` with
  the help its parser registers; every `protect_state._OWNER_ACTIONS` key appears, rendered
  `group verb`, under the owner-only heading that says to ask the owner; every
  `commands.READ_ONLY` path appears on the read-only line (`calibrate --questions` for
  `calibrate`); `shell.UNPARSED` and `shell.WORKSPACE_ROOT` (prefixes cut),
  `protect_state._STATE_HINT` and `next.EXECUTABLE` appear; the posture table has one row per
  `workspace.AREAS` entry with the `workspace.POSTURES` cells; every `guide.WIDGETS` entry
  appears as `wuwei <entry>`; no absolute path, no em-dash and no emoji; fewer than 97 lines
  (the block adds three). Fails today: `ModuleNotFoundError: wuwei.guide`.
- [X] T004 In `tests/test_guide.py`, add a failing drift test: walking the full parser (as
  `tests/test_cli_known_command.py::_registered` does), every subparser path that defines
  `--widget` is the start of some `guide.WIDGETS` entry, and every `WIDGETS` entry starts
  with a registered command path; `monkeypatch` of `workspace.POSTURES` (one cell changed)
  or of `commands.READ_ONLY` (one path added) changes `guide.text()`. Fails today: no module.
- [X] T005 In `cli/wuwei/commands/next.py`, add the `EXECUTABLE` constant and use it in
  `orientation` with the text unchanged (existing `tests/test_next.py` stays green).
- [X] T006 In `cli/wuwei/guide.py` (new), write `START`, `END`, `WIDGETS`, `RECORDS` and
  `text()` (plan.md layout).

## The guide command (FR-002, US1 scenario 1)

- [X] T007 In `tests/test_guide.py`, add a failing test: `wuwei.__main__.main(['guide'])`
  exits 0 and prints exactly `guide.text()`; `commands.read_only(['guide'])` is True; `guide`
  is in the Daily group. Fails today: `invalid choice: 'guide'`.
- [X] T008 In `cli/wuwei/commands/guide.py` (new) add `register` and `run`; in
  `cli/wuwei/commands/__init__.py` add `'guide'` to `READ_ONLY`; in `cli/wuwei/__main__.py`
  add `guide` after `next` in the Daily group. `tests/test_cli_known_command.py` stays green.

## The guide block on init and upgrade (FR-004, FR-005, US1 scenarios 1 and 2)

- [X] T009 In `tests/test_guide.py`, add failing tests: `init.run` on a `tmp_path` project
  (as the init tests in `tests/test_workspace.py` call it) leaves CLAUDE.md with exactly one
  guide block whose second line names `integrity.version()` and the first 12 hex characters
  of `sha256(guide.text())`, whose body equals `guide.text()`, and whose block is under 100
  lines; a second `init.upgrade` on the same workspace leaves CLAUDE.md byte-identical and
  prints no guide line; an owner paragraph above the block survives an upgrade; with
  `memory.export_to = "NOTES.md"` the block goes to NOTES.md. Fails today: no CLAUDE.md.
- [X] T010 In `cli/wuwei/guide.py`, add `export(root, write=True)`; in
  `cli/wuwei/commands/init.py`, write the block in `run` after the rename and in `upgrade`
  (plan.md), including the "No workspace changes needed" condition.

## Drift seen and fixed by the doctor (FR-006, US3)

- [X] T011 In `tests/test_guide.py`, add failing tests on an initialised workspace: after
  `monkeypatch` of `workspace.POSTURES` (one cell changed), `init.upgrade` with `dry_run=True`
  prints `Would upgrade CLAUDE.md: guide block` and leaves CLAUDE.md unchanged; the doctor's
  workspace rows (`doctor.diagnose` or `doctor._workspace`, as `tests/test_doctor.py` calls
  them, with the real `init.upgrade`) have the `template` row `warn` with that line in
  `detail` and `apply == 'init-upgrade'`; applying the `init-upgrade` fix
  (`doctor.FIXES['init-upgrade']` preview then apply) makes the block body equal the new
  `guide.text()`. The same three hold when the block was deleted by hand. Fails until T010.
- [X] T012 No production change expected; if T011 fails, fix it in `init.upgrade` only.
- [X] T012a In `tests/test_guide.py`, add a failing test: with `CLAUDE.md` a symlink to
  `AGENTS.md`, `init.run` and `init.upgrade` (dry run and real) exit 0, print
  `wuwei init: warning: guide block not written:` on stderr and leave AGENTS.md unchanged;
  the doctor's `template` row stays `ok` and a `guide` row is `warn` naming the reason.
  Then in `cli/wuwei/commands/init.py` route both exports through `_guide`, which catches
  `OSError` and `ValueError` and warns, and in `cli/wuwei/commands/doctor.py` turn that
  warning into the `guide` row.

## SessionStart steps (FR-007, FR-008, FR-009, US2)

- [X] T013 In `tests/test_next.py`, add failing tests for `next_command.steps`: for
  `wuwei-plan` and `wuwei-report` the result has one entry per line of the skill file
  matching `^\d+\. `, each entry a prefix of its line ending at the first sentence; an
  unreadable skill gives one `steps unmeasured:` entry naming the path. Fails today:
  `AttributeError: steps`.
- [X] T014 In `tests/test_next.py`, update `test_orientation_block`,
  `test_orientation_seat_entry` and `test_issue_acceptance_session_start_orients` to the
  new contract (plan.md, "Tests that change") and add failing tests: a `plan` row with
  `session='S'` gives `Do this now.`, `wuwei plan session S`, every `steps('wuwei-plan')`
  entry, `wuwei guide` and the daily.md path, under 30 lines under observe with a spec label;
  without a session the register line shows `<session id>`; a `close` row gives every
  `steps('wuwei-report')` entry and `Do this now.`; a stubbed stuck row
  (`{'state': 'stuck', 'step': 'Seat builder-1 has no process and no stop.', 'command':
  'wuwei seat stop builder-1 --unmeasured "<reason>"'}`) gives `wuwei seat stop` and none of
  `/wuwei:wuwei-plan`, `plan session`, `Do this now.`, `wuwei-plan/SKILL.md`; a decision
  row's command, from `step()`, is `wuwei decision show D-1 --widget` (update line 102).
  Fails today: entry line still present, no steps, no `--widget`.
- [X] T015 In `tests/test_next.py`, add a failing hook-level test: SessionStart through
  `hook(monkeypatch, root)` in a calibrated workspace with no plan injects the register line
  with the payload's session id `S` and the plan steps, and the orientation block (from the
  header to the `Reference:` line) is under 30 lines; SessionStart with `cwd` outside any
  workspace prints no `additionalContext` and exits 0. Fails today: no register line.
- [X] T016 In `tests/test_cli_known_command.py` (built: it holds the PreToolUse `hook`, `workspace`
  and `passes` helpers), add a failing replay test: from that injection, take
  every backticked or plain `wuwei ...` command on the register and step lines, replace
  `<json-file>` with `proposal.json`, `<approved IDs>` with `A` and the session placeholder
  with `S`, prefix the recorded executable (`.wuwei/executable` holding the plugin's
  `bin/wuwei`), and pipe each as a Bash PreToolUse payload through `hook.run` in process
  under observe, guarded and strict: every call exits 0, no `hook.refusal` event is
  written, and no command carries `--help` or `-h`. Fails until T017 if any injected form is
  refused; otherwise it pins the forms.
- [X] T017 In `cli/wuwei/commands/next.py`, add `steps`, the `session` parameter and the
  new entry and reference lines in `orientation`, and the `--widget` decision command; in
  `cli/wuwei/guards/lifecycle.py` `session_start` only, pass the payload's session id.
- [X] T018 Run `python -m pytest -q tests/test_hooks.py` and confirm the SessionStart import
  pins still hold (no `wuwei.guide`, `argparse`, `pkgutil`, `hashlib` on the hook path).

## Conformance run (FR-010, US4)

- [X] T019 In `tests/test_headless_e2e.py`, add failing tests: `runner.start_prompt()`
  contains `Start the day.` and no `Skill`, no `wuwei-plan`, no line starting with a digit
  and a dot, and no `wuwei ` followed by a subcommand; start-mode evidence built from the
  existing `evidence()` minus the refusal probe, the Skill row and the scripted Stop block,
  plus one `cli` row `['close']` exit 0, passes `runner.validate(..., start=True)`; adding a
  `hook.refusal` event, a `cli` row with `--help`, a PreToolUse Bash row whose command ends
  in ` -h`, or removing `plan.approved`, `seat launched` or `day.close_requested` each gives
  exactly one more finding; `runner.main(['--start'])` without a key exits 2 before any
  external call. Fails today: no `start_prompt`, `validate` takes no `start`.
- [X] T020 In `scripts/headless_e2e.py`, add `start_prompt`, `conformance`, the `start`
  parameter of `validate` and `exercise`, and `--start` in `main`.

## Docs (FR-011, US5)

- [X] T021 In `tests/test_docs.py`, update `test_agent_guide_ships_and_is_linked`,
  `test_one_gate_question` and `test_charters_carry_the_spec_mode` (plan.md) and add failing
  assertions: the text between agent.md's guide markers equals `guide.text()`; daily.md
  section 1 contains "open Claude Code in the workspace and say what you want; the session
  knows the rest"; configuration.md's `memory.export_to` row mentions the guide block;
  `docs/headless-e2e.md` names `--start`. The reference.md Commands test fails until the
  `guide` row exists. Fails today: no markers in agent.md.
- [X] T022 Edit `docs/site/agent.md` (paste `wuwei guide` output between the markers),
  `docs/site/daily.md`, `docs/site/configuration.md`, `docs/site/reference.md` and
  `docs/headless-e2e.md` (plan.md).

## Finish

- [X] T023 In `tests/test_workspace.py` and `tests/test_doctor.py`, fix every test that
  asserted "No workspace changes needed" on a workspace built without `init` by writing the
  guide block in its setup with `guide.export(root)`; never weaken the assertion.
- [X] T024 Run `python -m pytest -q` from the repository root; everything passes. Grep the
  changed files for em-dashes, emojis and absolute local paths and remove any.

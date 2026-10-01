# Tasks: an owner interview that turns personal preferences into configuration and charter overrides

**Input**: `specs/279-owner-interview/spec.md`, `specs/279-owner-interview/plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Every behaviour is a test task followed by its implementation task. Run each test, see it
fail for the expected reason, then implement the minimum that makes it pass. `[P]` marks
tasks that touch different files and can run in parallel.

## Phase 1: Config placement in calibrate (US3)

- [X] T001 Test: in `tests/test_interview.py`, `calibrate.settle` table cases: an absent
  `repos.0.merge.auto` becomes an addition and `apply` creates `[repos.merge]` after its
  repository (two repositories, the second untouched); a present one-line
  `content = "summary" # comment` under `[control_plane]` is replaced by
  `content = "none"` and every other value is preserved; an equal value yields nothing; a
  multi-line `quiet_hours = [\n "20:00-08:00",\n]` and a dotted `merge.auto = false`
  inside `[[repos]]` become hand edits and the text is unchanged; a `deploy.deny` setting
  over `deny = ["make deploy*"]` yields `["make deploy*", "npm publish*"]`. Then
  `calibrate.propose(raw, results, settings)` with a calibrate `deploy` fixture result
  and a deny setting keeps both the calibrate patterns and the new one. Expect
  AttributeError (no `settle`).
- [X] T002 Implement `_assignment`, the generalised replacement in `apply`, `settle` and
  the `settings` argument of `propose` in `cli/wuwei/calibrate.py`. T001 passes and
  `python -m pytest -q tests/test_calibrate.py` passes unchanged.

## Phase 2: The question table (US1, US2)

- [X] T003 Test: in `tests/test_interview.py`, one parametrized test over
  `interview.QUESTIONS`: ids unique, header at most 12 characters, 2 to 4 choices with
  unique labels, every choice's effects become settings that `calibrate.settle` plus
  `calibrate.apply` place in a one-repository config that `workspace.load_config`
  accepts, role keys only in `ROLES`, `voice` values pass `_items`. Table test of the free
  parsers: `quiet` accepts `22:00-07:00, 12:00-13:00` and rejects `25:00-07:00`; `hours`
  accepts `09:00-17:00 Europe/Lisbon` and rejects `09:00-17:00 Mars/Base`; `avoid` and
  `risk` reject an item with `;` and an item with `ignore previous instructions`;
  `manual` turns `make release` into `make release*` and rejects `./deploy.sh`;
  `effects` rejects an unknown label for a question without free text and an unknown id
  names the valid ids. Expect ImportError.
- [X] T004 Implement `QUESTIONS`, `_items`, `question`, `effects` and the free parsers in
  `cli/wuwei/interview.py`. T003 passes.

## Phase 3: Recording and proposals (US1, US2, US3)

- [X] T005 Test: in `tests/test_interview.py`, `interview.record` in a workspace with one
  repository writes `interview.json` in the answers shape, merges a second call (a
  repository answer for another repository and a changed workspace answer) without losing
  the first, and writes `proposals/interview-planner.json` (`add`, one `## Owner
  preferences (interview)` block, lines in table order), `interview-shepherd.json`,
  `interview-lead.json` and `interview-voice.json` (`patch` of `## shared\n` with only the
  never phrases not already in voice.md). With an override that already holds the block
  (written in `tmp_path`), the planner proposal is a `patch` whose `old_text` is that
  block and whose text keeps the lines of questions not answered today. A rerun whose
  answers leave a role without lines removes that stale proposal file. An invalid answer
  writes nothing. `interview.load` raises `ValueError` for an unknown id, an unknown
  repository, a wrong shape and a symlinked file. `interview.settings` and
  `interview.describe` give the expected tuples and lines. The four proposals land
  through `promotion.promote` (vcs stubbed as in
  `test_charter_proposal_lands_through_promote`): all `landed`;
  `.wuwei/charters/planner.md` ends with the block; voice.md parses with
  `voice.parse_profile` and its `shared` never list holds the new phrases; a second day's
  re-ask of `interrupt` produces a `patch` that lands and leaves exactly one block.
  Expect ImportError or AttributeError.
- [X] T006 Implement `load`, `record`, `_proposals`, `settings` and `describe` in
  `cli/wuwei/interview.py`. T005 passes.

## Phase 4: The command (US1, US2)

- [X] T007 Test: in `tests/test_interview.py`, through `wuwei.__main__.main`:
  `calibrate --interview` with a non-tty stdin exits 2 with `integrity.HOST_TERMINAL` on
  stderr and writes nothing; with `sys.stdin.isatty` true and `builtins.input` feeding a
  number or text per question, it exits 0, prints one line per answer naming its key or
  override, writes `interview.json` and leaves `config.toml` unchanged; an invalid reply
  is asked again; end of input exits 2 and writes nothing; `--interview merge` asks only
  merge and keeps today's other answers; `--interview nope` exits 2 naming the ids;
  `--answer "merge=Auto, 30 min soak" --repo acme/widget` records the same shape;
  `--answer merge=sometimes` exits 2 and writes nothing; `--questions` prints widgets
  whose ids and option labels equal the table, one per repository for repository rows,
  and each widget passed to `cli/wuwei/guards/decision.py:check_question` (AskUserQuestion
  payload, today's `plan.md` present) exits 0; no flag combination profiles a checkout or
  calls a port (ports fixture records no call). Expect failures (unknown flags).
- [X] T008 Implement `ask`, `parse`, `widgets` in `cli/wuwei/interview.py` and the flags
  and `_interview` in `cli/wuwei/commands/calibrate.py`. T007 passes.

## Phase 5: Config promote applies the answers (US1, US3)

- [X] T009 Test (issue acceptance 1): in `tests/test_interview.py`, a workspace with
  `acme/widget` at `tests/fixtures/calibrate/python` and the template `[control_plane]`
  line, the interview answered on the terminal (merge `Auto, 30 min soak`, gates `Full`,
  phone `Nothing`, manual `Package publishing`, the rest any choice); then
  `config.promote(SimpleNamespace(), confirm=...)` prints every `describe` line inside the
  digested summary, exits 0, and `config.toml` has `auto = true`, `soak_minutes = 30`,
  `floor = "full"`, `content = "none"` and the four publishing deny patterns plus the
  calibrate proposal; `promotion.promote` lands the charter and voice proposals; and
  `main(['config', 'check'])` exits 0 with the code host stubbed to report full
  protection. A forged `interview.json` (unknown id) makes `config promote` exit 2 with
  `config.toml` unchanged. Expect failures.
- [X] T010 Implement the `interview.load`, `settings` and summary lines in
  `cli/wuwei/commands/config.py:promote`. T009 passes.

## Phase 6: Retro re-ask (US4)

- [X] T011 Test: in `tests/test_interview.py`, `interview.reask` with day directories
  built in `tmp_path` (state written with `state._write_state(..., directory=day)` or the
  day's `state.json`, decision records that pass `decision.evaluate`): three owner
  `Merge` answers for `acme/widget` within seven days and `merge.auto` false give one line
  with the three `<date> D-<n>` entries, `repos.merge.auto = true`, the merge_deploys note
  and `bin/wuwei calibrate --interview merge --repo acme/widget`; two answers, three with
  `merge.auto = true`, one of three eight days old, a `Hold` answer, a seat outcome, a
  record failing the lint and a non-merge question give `[]`; a malformed `state.json`
  gives `['- unmeasured: ...']`. In `tests/test_report_retro.py`, extend
  `test_retro_compiles_role_evidence_and_cycle` to assert `## Owner preferences\nnone`.
  Expect failures.
- [X] T012 Implement `reask` in `cli/wuwei/interview.py` and the section in
  `cli/wuwei/retro.py:compile`. T011 passes.
- [X] T013 [P] Test: in `tests/test_interview.py`, `charters/shepherd.md` contains
  `Question: Merge <owner>/<repo>#<number>?` and `MERGE_QUESTION` fullmatches
  `Merge acme/widget#12?`. Expect failure.
- [X] T014 Edit `charters/shepherd.md` step 3 and run `bin/wuwei agents build` to
  regenerate `agents/shepherd.md`. T013 and `tests/test_agents.py` pass.

## Phase 7: Guard, hooks, docs (US3, US5)

- [X] T015 [P] Test: in `tests/test_protect_state.py`, a `Write` and a `Bash tee` to
  `.wuwei/days/2026-10-01/interview.json` are refused (mirror
  `test_calibration_snapshot_is_protected`). Expect failure.
- [X] T016 Add `'interview.json'` to the day file tuple in
  `cli/wuwei/guards/protect_state.py`. T015 passes.
- [X] T017 [P] Test: in `tests/test_hooks.py`, `test_calibrate_is_off_every_hook_path`
  also exits nonzero when `wuwei.interview` is in `sys.modules`. Expect it to pass
  already (confirm the assertion is live by importing `wuwei.interview` in the script once
  and seeing it fail, then remove that line).
- [X] T018 [P] Test: in `tests/test_docs.py`, `## Owner interview` follows
  `## Calibration` in `docs/site/configuration.md` and names `calibrate --interview`,
  `--questions`, `--answer`, `interview.json`, `config promote`, `wuwei promote` and
  `--interview merge`; `docs/site/daily.md` has `bin/wuwei calibrate --interview` after
  `bin/wuwei calibrate` and before `/wuwei plan`; `skills/wuwei-plan/SKILL.md` names
  `calibrate --questions`, `calibrate --answer` and `.wuwei/charters/planner.md`.
  Expect failure.
- [X] T019 Write the docs section in `docs/site/configuration.md`, the step in
  `docs/site/daily.md` and the skill text in `skills/wuwei-plan/SKILL.md`. T018 passes.

## Phase 8: Finish

- [X] T020 Run `python -m pytest -q`; everything passes. Check every file written for
  em-dashes, emojis and absolute local paths and remove any.

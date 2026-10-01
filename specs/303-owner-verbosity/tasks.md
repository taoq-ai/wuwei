# Tasks: Verbosity levels for what the owner reads, and humanizer-checked text

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root using
the interpreter the task names. Signatures, texts and formats are in plan.md.

## Config and the shared resolver (US2, FR-001)

- [X] T001 In `tests/test_workspace.py`, add failing tests: a default config gives
  `config['owner']['verbosity'] == {'default': 'brief', 'decisions': '', 'digest': '', 'nudges': '', 'dm': '', 'report': ''}`;
  `[owner.verbosity]` with `default = "full"` and `dm = "brief"` gives
  `workspace.verbosity(config, 'dm') == 'brief'` and `workspace.verbosity(config, 'report') == 'full'`;
  `default = "short"` and `dm = "loud"` each raise `ConfigError`; an unknown key `owner.verbosity.retro`
  raises `ConfigError`; `templates/workspace/config.toml` loads with `default = "brief"`.
  Fails today: `KeyError: 'verbosity'`.
- [X] T002 In `cli/wuwei/workspace.py`, add `LEVELS`, `SURFACES`, the `owner.verbosity` schema and
  `verbosity()`; in `templates/workspace/config.toml`, add the `[owner.verbosity]` block.

## One decision formatter (US1, FR-002)

- [X] T003 In `tests/test_decision.py`, add failing tests for `decision.present` on the template
  record and on a three-option record: `brief` is exactly
  `['D-3: <question>', 'A: <desc> (score 80)', 'B: <desc> (score 20)', 'Recommended: A, ahead of B on Outcome.']`
  for the template; an option failing a must shows `(score n, fails a must)`; one passing option
  gives `the only option that passes every must`; equal top scores give `tied with <id> on score`;
  `standard` adds the five lines of plan.md and still holds the brief lines first; `full` is not
  a `present` level (see T033); `evaluate` keeps
  its return value and error messages (existing tests stay green). Fails today:
  `AttributeError: present`.
- [X] T004 In `cli/wuwei/decision.py`, extract `_scored` from `evaluate` and add `present`.

## `wuwei decision show` (US1, FR-003)

- [X] T005 In `tests/test_decision.py`, add failing CLI tests in a fixture workspace with a routed
  D-3: `main('decision', 'show', 'D-3')` exits 0 and prints the `brief` text plus
  `Full record: wuwei decision show D-3 --full`, under 12 lines; `--full` prints the `full` text
  and no hint line; `owner.verbosity.decisions = "standard"` prints the standard text; a missing
  record exits 2, a symlinked record exits 2, an invalid record exits 1 with the lint reason; no
  event is appended. Fails today: argparse rejects `show` (exit 2 with `invalid choice`).
- [X] T006 In `cli/wuwei/commands/decision.py`, add the `show` parser, `show()` and its dispatch in
  `run`.

## DM decision text and `more D-n` (US1, FR-004, FR-005)

- [X] T007 In `tests/test_control_plane.py`, add failing tests: at the default level
  `escalate('D-3', transport=fake)` sends a text that starts with
  `decision.present('D-3', fields, 'brief')`, then `Reply more D-3 for the full record.`, then
  `HELP`, and contains neither `Context` nor `Pre-mortem`; with `[owner.verbosity] dm = "full"`
  it sends the full text and no `Reply more` line; `poll_replies` echo uses the same level;
  `content = "none"` tests stay as they are. Fails today: no scores in the DM.
- [X] T008 In `cli/wuwei/control_plane.py`, change `render`, add `_level`, and update `escalate` and
  `poll_replies`; update the `escalation()` helper in `tests/test_remote.py` as plan.md says.
- [X] T009 In `tests/test_remote.py`, add failing tests: `parse('more d-3') == ('more', 'D-3')`
  and `parse('More D-3.') == ('more', 'D-3')`; through `handle` with a recording transport,
  `more D-3` for a pending D-3 sends the full form once and returns 0; `more D-9` sends
  `D-9 is not waiting on you.` and returns 1; with `content = "none"` it sends `D-3 options: A, B`;
  a transport that refuses the full text with exit 1 gets `The full record of D-3 is on the host.`;
  `more` needs no code and records no `remote.pending`; `NOT_PENDING`, `ON_HOST` and the new
  `VOCABULARY` join `test_fixed_lines_pass_the_outward_lint`. Fails today: `more D-3` gets
  `VOCABULARY`.
- [X] T010 In `cli/wuwei/remote.py`, update `VOCABULARY` and `parse`, add `NOT_PENDING`, `ON_HOST`
  and `more`, and dispatch it in `handle`.

## The interview asks verbosity (US2, FR-006)

- [X] T011 In `tests/test_interview.py`, add failing tests: `interview.effects('verbosity', 'brief')
  == {'owner.verbosity.default': 'brief'}` (and for `Standard`, `Full`); `settings` gives
  `(('owner', 'verbosity'), 'default', 'full')`; `calibrate.propose` on the template config with
  that setting yields a config that loads with `default = "full"`; `describe` prints
  `owner.verbosity.default = "full"`; update `test_interview_on_the_terminal` to one more reply
  and 13 answers. Fails today: `unknown interview question 'verbosity'`.
- [X] T012 In `cli/wuwei/interview.py`, append the `verbosity` question.

## Report, digest and nudge levels (US2, FR-007)

- [X] T013 In `tests/test_report_retro.py`, add failing tests: at the default level the report's
  first section after the title is `## Changed` with at most three outcome lines whose value
  differs from the baseline (`none` when none differ), the Merged, Open at close, Parked,
  Decisions answered and Carry headings are present, and Outcome, Quality by band and Process
  metrics are absent; at `report = "standard"` the text equals today's (pin with the existing
  assertions, which now set `standard`); at `full` each Decisions answered line ends with
  `(decisions/<id>.md)`; `remote.handle` `report` still counts merged, open, parked and answered
  at `brief`. Fails today: no `## Changed` section.
- [X] T014 In `cli/wuwei/report.py`, read the level in `build` and shape the sections; set
  `report = "standard"` in the existing report tests that read the dropped sections.
- [X] T015 In `tests/test_decision_digest.py`, add failing tests: at `digest = "full"` each digest
  line is `- D-n: <option> (decisions/D-n.md)`; at the default level the text is today's
  `Two-way decisions taken:` list. Fails today: no path at `full`.
- [X] T016 In `cli/wuwei/watch.py` `digest`, read the level and add the path at `full`.
- [X] T017 In `tests/test_listen.py`, next to the existing PR notify tests, add failing tests: at
  `nudges = "full"` the DM is `<summary> (fields: checks, threads)` followed by the usual tail; at
  the default level it is today's single line; a payload whose `fields` is not a list of strings
  adds nothing. Fails today: no fields at `full`.
- [X] T018 In `cli/wuwei/listen.py` `notify`, read the level and append the fields at `full`.

## Tells: non-blocking style finding and metric (US4, FR-009 to FR-011)

- [X] T019 In `tests/test_outward.py`, add failing table tests for `outward.tells`: one positive
  and one negative case per `TELLS` row; `"This is not just a fix but a rewrite. We delve into it."`
  gives `['not-x-but-y', 'stock-word']`; plain text gives `[]`; an em-dash text still makes
  `outward.lint` return exit 1 with `outward: banned character` and `tells` never changes a lint
  exit. Fails today: `AttributeError: tells`.
- [X] T020 In `cli/wuwei/outward.py`, add `TELLS` and `tells` from plan.md.
- [X] T021 In `tests/test_drafts.py`, add failing tests: `drafts.create` with that two-tell text
  stores `row['style'] == ['not-x-but-y', 'stock-word']`; a row without `style` still passes
  `drafts.read`; approving a draft whose edited text has an em-dash is still refused with exit 1.
  Fails today: no `style` key.
- [X] T022 In `cli/wuwei/drafts.py` `create`, add `style` to the row.
- [X] T023 In `tests/test_decision.py`, add failing tests: a valid record whose Context holds the two
  tells lints `(0, 'OK: A (80)\nstyle: not-x-but-y, stock-word')`; `lint_file` records no
  `decision.rejected` for it; the template still lints `(0, 'OK: A (80)')`. Fails today: no
  `style:` line.
- [X] T024 In `cli/wuwei/decision.py` `lint`, append the `style:` line.
- [X] T025 In `tests/test_metrics.py`, add failing tests: with that draft and that record today,
  `metrics.collect(root)['ai_tells'] == {<draft id>: 2, 'D-1': 2}`; a draft row without `style` is
  absent; a symlinked `D-2.md` is absent; the retro's `## Metrics` JSON and the report's process
  metrics at `standard` carry `ai_tells`. Fails today: `KeyError: 'ai_tells'`.
- [X] T026 In `cli/wuwei/metrics.py` `collect`, add `ai_tells`.

## CLI templates stay plain (US5, FR-012)

- [X] T027 In `tests/test_outward.py`, add `test_owner_facing_templates_are_plain`: parse with `ast`
  `cli/wuwei/control_plane.py`, `remote.py`, `listen.py`, `report.py`, `decision.py`, `retro.py`,
  `interview.py`, `commands/decision.py` and `commands/status.py`; every `str` constant has no
  em-dash and `outward.tells(value) == []`. Run it; it passes once T010 and T012 land (it pins
  the state; rewrite any line it flags to the brief voice).

## Seats write with the humanizer skill (US3, FR-008)

- [X] T028 In `tests/test_charters.py`, add failing tests: `_common-authoring.md` has a
  `## Writing for a person` section that names `humanizer` and `embedded mode` and holds ten
  numbered lines; every `agents/<role>.md` for the nine roles contains that section verbatim;
  `skills/wuwei-plan/SKILL.md` names `humanizer`, `decision show` and `Writing for a person`; the
  section text has no em-dash and `outward.tells(section) == []`. Fails today: no section.
- [X] T029 In `charters/_common-authoring.md`, append the section from plan.md; run
  `bin/wuwei agents build` from the repository root outside a workspace to regenerate
  `agents/*.md`; add the paragraph to `skills/wuwei-plan/SKILL.md`. Confirm
  `tests/test_agents.py` reports no drift.

## Docs (FR-013)

- [X] T030 In `tests/test_docs.py`, add failing assertions: `configuration.md` names
  `owner.verbosity.default` and each surface key; `daily.md` and `reference.md` name
  `decision show` and `--full`; `remote.md` holds the new `VOCABULARY` and `more D-n`;
  `concepts.md` names `humanizer`, `3.1.0` and `MIT`. Fails today on each page.
- [X] T031 Update `docs/site/configuration.md`, `daily.md`, `reference.md`, `remote.md` and
  `concepts.md` as plan.md says.

## Review fixes

- [X] T033 `full` is the validated record text, not fields rebuilt by `evaluate`: `decision show
  --full`, `more D-n` and `dm = "full"` keep fenced blocks, quotes and a `## Notes` section.
  Tests in `tests/test_decision.py`, `tests/test_control_plane.py` and `tests/test_remote.py`;
  `control_plane.render` reads the record at `full`, and `present` drops its `full` branch.
- [X] T034 `configuration.md` `control_plane.content` and design spec section 15.4 say what
  `summary` now lets leave the host: the `owner.verbosity.dm` text and the `more D-n` reply.
- [X] T035 `outward.tells` ignores inline code spans and no longer counts `underscore`;
  `watch.py` joins the plain owner-facing template list; `concepts.md` says the report carries
  `ai_tells` at standard or full.

## Finish

- [X] T032 Run the full suite with `python -m pytest -q`; guard, mutation, hook-level and status
  line latency tests must pass unchanged. Check every file written for em-dashes, emojis and
  absolute local paths.

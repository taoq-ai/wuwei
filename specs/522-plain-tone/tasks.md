# Tasks: Plain tone

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (`fixture-org/...` repositories, items `A`, `B`). New tests go in
`tests/test_tone.py` unless a task names another file. Reuse `all_reasons`, `_sources` and
`_text` from `tests/test_reasons.py`, the `proposal()` fixture shape of `tests/test_plan.py`,
the hook-path refusal pattern of `tests/test_config_failure.py` (around line 100) and the
workspace and payload helpers of `tests/test_protect_state.py` (import or copy the few lines
needed; no new fixture framework).

## Phase 1: the measure (FR-002)

- [X] T001 Test in `tests/test_tone.py`: `sentences` on a table of inputs: front matter,
  a fenced code block, an HTML comment and a heading give no sentence; inline code counts as
  one word; `[text](url)` counts its text only; each list item and each table cell is its own
  sentence and the separator row none; `?` and `!` end a sentence; `;` does not; `{}` is one
  word; lines of one paragraph join. `measure('a b c. d e.', 'f g h i')` gives sentences 3,
  words 9, average 3.0, longest 4, over 0; a 36-word sentence gives over 1; `measure()` of
  text with no prose gives average 0.0; nominalisations count `documentation`,
  `measurements` and `readiness` but not `ask`, `run` or a word inside a code fence.
- [X] T002 Implement `AVERAGE`, `LONGEST`, `NOMINAL` (with its `ponytail:` comment),
  `_blocks`, `sentences`, `measure`, `at_rule` and `line` in `cli/wuwei/commands/lint.py`.

## Phase 2: the command (US1, FR-002, FR-003)

- [X] T003 Test in `tests/test_tone.py` (no workspace; `monkeypatch.chdir(tmp_path)` and no
  `WUWEI_WORKSPACE`): `main(['lint', 'tone', <file>])` exits 0 and prints the exact US1
  scenario 1 line ending `at the rule`; a file with a 36-word sentence exits 1 with
  `1 over 35` and `over the rule`; a directory with two `*.md` files and one `.txt` measures
  the two in sorted order and prints a `total:` line; a missing path and an empty directory
  each exit 2 with the reason naming the path and `pass a markdown file or a directory of
  them` on stderr; a file with invalid UTF-8 exits 2 with `pass a readable UTF-8 file`.
- [X] T004 Test in `tests/test_cli_known_command.py`: `(['lint', 'tone', 'README.md'], True)`
  in the `read_only` parameter table. Run it with the existing set-equality test and see both
  fail.
- [X] T005 Implement `register` and `run_tone` in `cli/wuwei/commands/lint.py`; add
  `'lint tone'` to `READ_ONLY` in `cli/wuwei/commands/__init__.py`; add `lint` to the
  Plumbing group in `cli/wuwei/__main__.py`; add the `bin/wuwei lint` row to the command
  table in `docs/site/reference.md`. Run `tests/test_tone.py`,
  `tests/test_cli_known_command.py`, `tests/test_guide.py`, `tests/test_docs.py` and
  `tests/test_reasons.py` (the new reasons name a next step, no pronoun).

## Phase 3: the base numbers (US1 scenario 5, FR-006)

- [X] T006 Before any existing text changes (Phases 4, 5 and 7): write `classes()` in `tests/test_tone.py` (reasons,
  cards, skills, charters, docs as in plan.md) and run `measure` over each class and
  `bin/wuwei lint tone skills charters docs/site README.md` on the base. Record the before
  column (average, longest, over 35, nominalisations per 100 words per class, and the per-file
  over-35 counts for concepts.md, daily.md and README.md) in
  `specs/522-plain-tone/research.md`. Record the docs pages outside the pass and their total
  over-35 count: that is the docs over budget.

## Phase 4: the rule (FR-001)

- [X] T007 Test in `tests/test_charters.py`: `charters/_common-authoring.md` has a
  `## Plain tone` section with exactly five numbered items, naming `bin/wuwei lint tone`,
  `20`, `35`, "one idea", "the owner" and `#362`; the section is in every generated agent.
- [X] T008 Add the `## Plain tone` section (plan.md text) to `charters/_common-authoring.md`,
  bump its patch version, run `bin/wuwei agents build`; run `tests/test_charters.py` and
  `tests/test_agents.py`.

## Phase 5: the acceptance texts (US3)

- [X] T009 Test in `tests/test_tone.py`: in a seeded workspace (the `tests/test_protect_state.py`
  fixture shape), a seat's Write to `.wuwei/days/<day>/state.json` runs through
  `main(['hook', 'PreToolUse'])` with the payload on stdin and is refused; then
  `main(['why', 'last', 'refusal'])` exits 0, and measuring each output line on its own gives
  no line over 35 words and an average under 20.
- [X] T010 Test in `tests/test_tone.py`: in a fixture day (the `tests/test_plan.py` `root`
  and `proposal()` shapes, host pinned as its `host` fixture does), render
  `plan.gate_widget(root)`, `commands.close.widget(root, 'A', {'status': 'building', 'phase': 'build'})`
  and the first of `interview.widgets(root, ['fixture-org/web'])`; for each card, the
  question and every option description has no sentence over 35 words, averages under 20, and
  does not match `\bthe owner\b`. See it fail on the gate card's Approve text.
- [X] T011 Rewrite `plan.gate_widget` in `cli/wuwei/plan.py` (Approve parts joined as
  sentences, Change something as short sentences; plan.md); update `tests/test_plan.py:342`
  (`Claims PR-12`) and any other assertion on the old separators. If T009 fails, rewrite the
  records floor reason in `cli/wuwei/guards/protect_state.py` to the rule and update its
  asserting tests. Run `tests/test_tone.py`, `tests/test_plan.py`, `tests/test_why.py`,
  `tests/test_protect_state.py`.

## Phase 6: the budgets (US2, FR-004)

- [X] T012 Test in `tests/test_tone.py`: `BUDGETS` with over 0 for reasons, cards, skills and
  charters, the T006 count for docs, and nominal rates at the T006 before rates; the budget
  test asserts per class `average < AVERAGE`, `over <= budget` and `rate <= nominal budget`,
  with `line(name, m)` as the message. A second test appends a 40-word sentence to the
  charters class texts in memory and asserts the budget check fails naming `charters`. Run
  it: it fails on skills, charters and reasons (the pass has not run).

## Phase 7: the pass (US4, FR-005)

Each task: grep `tests/` and `docs/` for a fragment of every text before changing it, update
each match with the same meaning, never delete an assertion, run the focused tests named.

- [X] T013 Reasons over 25 words: list them with `all_reasons()` and `sentences`; rewrite each
  to the rule in its module, keeping the #362 shape, the next-step verb, the family suffix,
  the first `; ` split and the pronoun rule. Run `tests/test_reasons.py` and the tests of each
  touched module.
- [X] T014 Guard reasons: every reason under `cli/wuwei/guards/` reread for verbs over nouns,
  plain words and one idea per sentence. Run `tests/test_protect_state.py`,
  `tests/test_commit_push.py`, `tests/test_pr_guards.py`, `tests/test_outward.py`,
  `tests/test_stop.py`, `tests/test_agent_launch.py`, `tests/test_deploy.py`,
  `tests/test_spec_mode.py`, `tests/test_verdict.py`, `tests/test_traces.py`,
  `tests/test_integrity.py`, `tests/test_why.py`, `tests/test_reasons.py`.
- [X] T015 Cards: literal questions and option descriptions in every `widget(` call
  (`commands/close.py`, `commands/consolidate.py`, `commands/telemetry.py`,
  `commands/doctor.py`, `drafts.py`, `interview.py`) and `interview.QUESTIONS`. Keep labels,
  headers and record commands. Run `tests/test_stop.py`, `tests/test_consolidation.py`,
  `tests/test_telemetry.py`, `tests/test_doctor.py`, `tests/test_drafts.py`,
  `tests/test_interview.py`, `tests/test_guide.py`, `tests/test_reasons.py`.
- [X] T016 Skills: the four `skills/*/SKILL.md` to the rule, every command and loop step
  kept. Run `tests/test_skill_evals.py`, `tests/test_charters.py`, `tests/test_path_day.py`,
  `tests/test_next.py`, `tests/test_docs.py`.
- [X] T017 Charters: every `charters/*.md` to the rule (0 over 35 each), one-home sentences
  kept in their home, patch version bumped per changed charter; `bin/wuwei agents build`, then
  `bin/wuwei agents check` exits 0. Run `tests/test_charters.py`, `tests/test_agents.py`.
- [X] T018 Docs: `docs/site/concepts.md`, `docs/site/daily.md` and `README.md` to the rule,
  headings, anchors, links, list counts and asserted phrases kept; the reader is "you". Run
  `tests/test_docs.py`, `tests/test_guide.py`.
- [X] T019 Run `bin/wuwei lint tone` on concepts.md, daily.md, README.md, `skills` and
  `charters`: each file exits 0 (US4 scenario 1). Fix any file that does not.

## Phase 8: budgets, table, suite

- [X] T020 Measure every class after the pass; set each nominal budget to the after rate
  rounded up to one decimal (assert it is not above the before rate) in `BUDGETS`; write the
  after column into `specs/522-plain-tone/research.md`. Run `tests/test_tone.py`: all pass.
- [X] T021 Run the full suite in the background (`python -m pytest -q` from the repository
  root with the task's interpreter, output to a file) and wait for it; every test passes.
- [X] T022 Check every file this feature wrote or changed for em dashes, emojis, absolute
  local paths and client or repository names; remove any.

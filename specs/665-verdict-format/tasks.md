# Tasks: one verdict format for the lint and the charters

Test first: run each test task and see it fail for the expected reason before its
implementation task. Tests are in-process and use neutral synthetic verdict text and the
existing fixtures (`VALID`, `PASS`, `RETRO`, `FINDING` in `tests/test_verdict.py`; `plugin`
in `tests/test_agents.py`). No text from a real workspace goes into the repository. Run the
touched test files after each phase, then the full suite.

## Phase 1: a numbered list in prose is not a finding (FR-001, FR-002; US1)

- [X] T001 Tests in `tests/test_verdict.py`:
  (a) US1.1: `PASS` + `Evidence:\n1. ran the suite\n2. read the diff\n` and the same under
  `## Evidence`: `finding_blocks(active_text(text)) == []` and `lint(text, class_sweep=True)
  == (0, 'OK: PASS')`;
  (b) US1.2: a FIX with `F1 medium cli/example.py:12 fails when input is empty. blocks: yes`
  then `## Evidence` and `1. ran pytest\n2. read cli/example.py\n`: `(0, 'OK: FIX')` and
  exactly one block, starting `F1`;
  (c) US1.3: `Findings:` (and `## Findings`) then `1. cli/example.py:12 fails when empty; P1;
  blocks: yes\n2. read the code\n`: two blocks, and the message contains `finding 2: missing`;
  (d) US1.4: outside any `Findings` heading, `1. P1 ...`, `1. Severity: medium. ...`,
  `1. F1 ...` and `1. the guard at cli/example.py:12 fails when empty, blocks: yes` each
  still start one block, and `PASS` plus the last one is refused with `PASS verdict carries
  a blocking finding`;
  (e) edge: a finding followed by `Evidence:` then a numbered line carrying `cli/other.py:3`
  does not give the finding a citation it lacks (message names `file:line`);
  (f) edge: `### P1: empty input` then a `Scenario:` label line with the scenario on the next
  line stays one finding and lints clean.
  Today (a), (b) and (c second block absent) fail; (d), (e), (f) pass and guard the change.
- [X] T002 Implement in `cli/wuwei/verdict.py`: `FIELDS` and `HEADING` constants, the
  `findings` flag, the narrowed `numbered` rule and heading-closes-block in
  `finding_blocks` (plan, Design). T001 passes; the rest of `tests/test_verdict.py` passes
  unchanged.

## Phase 2: one format table and the class line the charter shows (FR-003, FR-006; US2.1, US3)

- [X] T003 Tests in `tests/test_verdict.py`:
  (a) US2.1: `verdict.CLASSES` matches every `f'{name}: PASS'` for `name in
  verdict.CLASS_NAMES`; `PASS` with `VAL: PASS` replaced by the class example line
  `verdict.FORMAT['Class'][1]` lints `(0, 'OK: PASS')` with `class_sweep=True`;
  (b) US3.2: `PASS.replace('VAL: PASS', 'CLASS: PASS')` with `class_sweep=True`: exit 1, the
  message contains `'CLASS: PASS'` and `FORMAT['Class'][0]`, and no line of the message
  contains `(CLASS: PASS|N.A.|FINDING <id>)`;
  (c) US3.1: a finding missing a citation: the message line starts `finding 1: missing
  file:line`, quotes the finding's first line and contains `FORMAT['Finding'][0]`;
  (d) US3.3: `Head: abc12` quotes `'Head: abc12'` and `FORMAT['Head'][0]`; a second
  `Verdict: FIX` line is quoted; `PASS + FINDING` quotes the finding line and ends the hint
  with `or blocks: no`;
  (e) every message still ends with `REJECT: send back to the seat`.
- [X] T004 Implement `CLASS_NAMES`, `CLASSES` from it, `FORMAT` and `_fix`, and the message
  changes in `lint` in `cli/wuwei/verdict.py` (plan, Design table), including the FIX hint
  wording. T003 passes; `test_source_refusals`, `test_source_refusal_order` and every other
  existing test in `tests/test_verdict.py` and `tests/test_process_depth.py` pass unchanged.

## Phase 3: build renders the table into the sentinel agents (FR-004, FR-005, FR-007; US2.2 to US2.4)

- [X] T005 Tests:
  (a) `tests/test_verdict.py`: `verdict.section()` starts `## Verdict format\n`, has one
  `- <key>: <form>` line per `FORMAT` key in order, and its fenced example is the `FORMAT`
  example lines in order;
  (b) `tests/test_agents.py`, US2.2 / FR-007: for each of `sentinel-arch`,
  `sentinel-quality`, `sentinel-security`, `sentinel-goal`, take the fenced block under
  `## Verdict format` in the checked-in `agents/<role>.md`, write it to
  `tmp_path / 'decisions' / f'gate-{role}.md'` and assert
  `verdict.lint_file(path, role=role) == (0, 'OK: FIX')`; and the five other agents carry no
  `## Verdict format`;
  (c) `tests/test_agents.py` with the `plugin` fixture: after `agents.build(plugin)`, each
  sentinel agent contains `verdict.section()` right after the `_common` body and the
  builder agent does not;
  (d) `tests/test_agents.py`, US2.3: a `plugin` charter (one test for `_common`, one for a
  role charter) with a `## Verdict format` section appended: `agents.build(plugin) == 2`,
  `agents.check(plugin) == 2`, stderr contains `Verdict format`, and no `agents/*.md` is
  written;
  (e) `tests/test_agents.py`, US2.4: after `agents.build(plugin)`, monkeypatch
  `verdict.FORMAT['Probe']` to another form: `agents.check(plugin) == 1` naming a sentinel
  agent;
  (f) `tests/test_charters.py`: `charters/_common.md` does not contain
  `` `CLASS: PASS|N.A.|FINDING <id>` `` and no charter contains `## Verdict format`.
  (a) fails until `section` exists, (b) and (c) until `render` renders it, (d) until it
  checks, (f) until the charter edit; (e) passes once (c) does and guards the drift path.
- [X] T006 Implement `section()` in `cli/wuwei/verdict.py` (plan, Design). T005(a) passes.
- [X] T007 Implement the render and the check in `agents.render` in
  `cli/wuwei/commands/agents.py` (plan, Design). T005(c), (d), (e) and every existing test in
  `tests/test_agents.py` pass with the `plugin` fixture unchanged.
- [X] T008 Edit `charters/_common.md`: version `1.9.0`, item 8's class parenthetical to
  `(see Verdict format)` (plan, charters); the file stays at 30 lines. Regenerate
  `agents/*.md` with `bin/wuwei agents build`. T005(b), (f), `tests/test_charters.py`,
  `tests/test_tone.py`, `tests/test_process_depth.py::test_charters_follow_the_depth_line`
  and `test_checked_in_agents_match_charters_and_allowlist` pass.

## Phase 4: invariant and docs (FR-008)

- [X] T009 Test: add the invariant check (next free id; I44, reserved for this item) to
  `tests/test_invariants.py` and its row to design 9.2 in
  `docs/specs/2026-09-24-wuwei-design.md` (plan, Design); registered in `INVARIANTS` and
  `READS` with `()`. It passes once T002, T007 and T008 are in; confirm it fails with the
  `numbered` change reverted or the section left out of `render`. I39 still passes.
- [X] T010 Docs: `docs/site/reference.md` "Gate verdict layout" lint rules (plan,
  docs). `tests/test_docs.py` (`test_reference_verdict_example_and_phase_table`) passes.

- [X] T012 Review fix: a bare label line inside a finding (`Fix:`, `Failure scenario:`)
  keeps the finding open; only a markdown heading or a verdict section label (Findings,
  Evidence, Probes, Residual risk, Assumptions) closes it.
  `tests/test_verdict.py::test_label_line_inside_a_finding_keeps_it_open` fails without it.

## Phase 5: verify

- [X] T011 Run the three Root cause texts from spec.md through `verdict.lint` and confirm
  SC-001. Run the full suite with `python -m pytest -q` from the repository root. Read any
  failure beyond the plan's table before changing it. Check every file written for
  em-dashes, emojis and absolute local paths.

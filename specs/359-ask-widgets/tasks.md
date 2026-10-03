# Tasks: owner questions as AskUserQuestion widgets

**Input**: `specs/359-ask-widgets/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, client names, emojis
or em-dashes in any file. Tests build workspaces under `tmp_path`, set `WUWEI_NOW`, and
never need the network, a scanner, or a terminal.

Before T001, check whether #354, #357 or #358 is on main. Build T001 to T020 either way;
the rebase tasks T021 to T023 apply only to what landed.

## Phase 1: the shared printer (FR-001, FR-002)

- [X] T001 Test, `tests/test_decision.py`: `test_widget_shape` (a two-option widget has
  exactly the keys `question`, `header`, `options`, `multiSelect`, `record`, options as
  `{label, description}` in the given order; a 13-character header, one option and five
  options each raise `ValueError`), and `test_decision_widget_passes_the_question_guard`
  (save `VALID` as `D-3`; `record_widget('D-3', fields)` has question
  `D-3: Which fix?`, header `D-3`, labels `['A', 'B']`, the `A` description
  `Recommended. Implement fix`, `multiSelect` false, record
  `wuwei decision outcome D-3 <label>`; with `Recommendation: B` scores swapped so B
  passes the lint, `B` comes first; the four AskUserQuestion keys through
  `check_question` give `(0, '')`; a five-option valid record gives four options, the
  recommended first). Run `python -m pytest -q tests/test_decision.py -k widget`
  (fails: no `widget`).
- [X] T002 Implement, `cli/wuwei/decision.py`: `RECORD`, `widget`, `gate`,
  `record_widget` as in plan section 1, with the `ponytail:` comment on the four-option
  cap. Rerun T001; passes.

## Phase 2: US1, `decision show --widget`

- [X] T003 Test, `tests/test_decision.py`: `test_decision_show_widget` (chdir to `ws`,
  save `VALID`; `main(['decision', 'show', 'D-3', '--widget']) == 0` and stdout parses to
  `[record_widget('D-3', fields)]`; an invalid record exits 1 with `missing fields` on
  stderr; a missing record exits 2; `--widget --full` raises `SystemExit` 2). Run
  `python -m pytest -q tests/test_decision.py -k show_widget` (fails: unrecognized
  argument).
- [X] T004 Implement, `cli/wuwei/commands/decision.py`: the mutually exclusive
  `--full`/`--widget` group in `register`, the widget branch in `show` (plan section 3).
  Rerun T003 and `tests/test_decision.py::test_decision_show`; both pass.

## Phase 3: US4, interview widgets on the shared printer

- [X] T005 Test, `tests/test_interview.py`: extend
  `test_widgets_come_from_the_table_and_pass_the_question_guard` so each widget's
  `record` is `wuwei calibrate --answer "<id>=<label>"`, followed by
  ` --repo acme/widget` or ` --repo acme/gadget` for a repository question; everything
  it asserts today still holds. Run `python -m pytest -q tests/test_interview.py -k widgets`
  (fails: no `record`).
- [X] T006 Implement, `cli/wuwei/interview.py`: `widgets` on `decision.widget` and
  `decision.gate` (plan section 2). Rerun T005 and the whole of `tests/test_interview.py`;
  pass.

## Phase 4: US2, `mcp check --widget`

- [X] T007 Test, `tests/test_mcp.py`: `test_findings_summary_per_server` (with
  `configured`, `fake_scanner(monkeypatch, 1, [{**metadata('high'), 'server_name':
  'alpha'}, {**metadata('critical'), 'server_name': 'alpha'}, {**metadata('medium'),
  'server_name': 'beta'}])` and `core().check(configured)`: `core().findings(configured)
  == ['alpha: 1 critical, 1 high', 'beta: 1 medium']`; after appending an
  `mcp.decided` event with outcome `proceed` through `state.append_event`, it is `[]`;
  a second check leaves the counts at one each, since only the last completed check
  counts (review F1); an `mcp.finding` event with `server_name` `'bad name; run x'` and
  severity `'urgent'`, followed by `mcp.checked`, reads `unnamed server: 1 unknown`). Run `python -m pytest -q tests/test_mcp.py -k
  findings_summary` (fails: no `findings`).
- [X] T008 Implement, `cli/wuwei/mcp.py`: `findings` (plan section 4). Rerun T007; passes.
- [X] T009 Test, `tests/test_mcp.py`: `test_check_widget` (same findings; chdir to
  `configured`; `main(['mcp', 'check', '--widget']) == 1`; stdout parses to one widget
  whose question starts with the pending `D-n: May seats proceed`, labels
  `['defer', 'proceed']`, the `proceed` description ending in the two server lines,
  record `wuwei decision route D-n && wuwei decision outcome D-n <label> && wuwei mcp
  decide` with the real id; the four keys pass `check_question`; with no findings
  (`fake_scanner(monkeypatch, 0)` on a fresh workspace) stdout is `[]`; with the status
  `pending` pointing at an earlier day's record, `core().widget(configured) == []`;
  `main(['mcp', 'decide', '--widget'])` exits 2). Run `python -m pytest -q
  tests/test_mcp.py -k check_widget` (fails: unrecognized argument).
- [X] T010 Implement, `cli/wuwei/mcp.py` (`RECORD`, `widget`) and
  `cli/wuwei/commands/mcp.py` (`--widget`, usage check, JSON print, exit 2 on a widget
  read error), plan sections 4 and 5. Rerun T009 and the whole of `tests/test_mcp.py`;
  pass.

## Phase 5: US3, `doctor --fix --widget` and `--apply`

- [X] T011 Test, `tests/test_doctor.py`: update the `fix` helper to
  `Namespace(fix=True, json=False, widget=False, apply=None)`; add
  `test_fix_widget_needs_todays_plan` (two fixes due: `doctor.diagnose` monkeypatched to
  two `_row(..., apply=<id>)` rows for `calibrate` and `init-upgrade`, and
  `monkeypatch.setitem(doctor.FIXES, ...)` giving each a fake preview and an apply that
  records its call; without `plan.md`, `doctor.run(Namespace(fix=True, json=False, widget=True,
  apply=None), confirm=asked.append)` returns 1, prints `run wuwei doctor --fix in a host
  terminal` on stderr, asks nothing, applies nothing; with today's `plan.md` it prints one
  widget: header `Fixes`, `multiSelect` true, labels the two fix ids, descriptions
  starting with each fix's command, record `wuwei doctor --fix --apply <labels>`, question
  starting `Morning gate (days/<date>/plan.md): `, the four keys passing
  `check_question`; still nothing asked or applied and no `doctor.fixed` event). Run
  `python -m pytest -q tests/test_doctor.py -k widget` (fails: no widget handling).
- [X] T012 Test, `tests/test_doctor.py`: `test_widgets_split_and_skip` on
  `doctor.widgets(root, batch)` with fake batches of 1, 4, 5 and 6 `(name, text, token)`
  entries drawn from `FIXES` names: one gives two options (the fix and `Skip`), four gives
  one widget of four, five gives widgets of three and two, six of three and three, zero
  gives `[]`; split widgets carry unique questions, `(1 of 2)` and `(2 of 2)` (review
  F2). Run `python -m pytest -q tests/test_doctor.py -k widgets_split` (fails: no
  `widgets`).
- [X] T013 Implement, `cli/wuwei/commands/doctor.py`: `--widget` in `register`, the
  usage check and `only` parsing in `run`, the widget branch in `fix`, and `widgets`
  (plan section 6). Rerun T011 and T012; pass.
- [X] T014 Test, `tests/test_doctor.py`: `test_fix_apply_limits_the_batch` (two fixes due;
  `--apply calibrate` with an accepting confirm previews, confirms and applies only
  `calibrate`, and `doctor.fixed` holds one event; `--apply nope` returns 2 naming `nope`
  and applies nothing; `--apply Skip` is dropped and applies nothing (review F4);
  `--widget` without `--fix`, `--apply` without `--fix`, and
  `--widget` with `--apply` each return 2). Run `python -m pytest -q
  tests/test_doctor.py -k apply_limits` (fails: `--apply` ignored).
- [X] T015 Implement, `cli/wuwei/commands/doctor.py`: `--apply` in `register`, the
  `Skip` drop, the `wanted &= only` narrowing and the unknown-id exit in `fix`. Rerun T014 and the
  whole of `tests/test_doctor.py`; pass.

## Phase 6: US5, skills and docs

- [X] T016 Test, `tests/test_docs.py`: `test_owner_questions_use_widgets_or_the_dm`: every
  `skills/*/SKILL.md` contains `AskUserQuestion`, `decision route`, `--widget` and
  `Seats never ask the owner`, and neither `Decided-by: owner` nor `Outcome: proceed`;
  the plan skill contains `wuwei mcp check --widget`, `record`, `calibrate --answer` and
  `wuwei_board`; `docs/site/daily.md` has `### How you answer` inside `## 5. Owner
  decisions` with `question card`, `DM` and `host terminal` in that part. Run `python -m
  pytest -q tests/test_docs.py -k widgets_or_the_dm` (fails).
- [X] T017 Implement, `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`,
  `skills/wuwei-retro/SKILL.md`, `skills/wuwei-consolidate/SKILL.md`: the shared
  paragraph and the plan-skill edits in plan section 7. Run the humanizer checklist
  (`charters/_common-authoring.md`, Writing for a person) over the new text. Rerun T016
  for the skill assertions.
- [X] T018 Implement, `docs/site/daily.md` (How you answer) and `docs/site/reference.md`
  (the new flags), plan section 8. Rerun T016 and the whole of `tests/test_docs.py`; pass.

## Phase 7: finish

- [X] T019 Run `python -m pytest -q` from the repository root; everything passes.
- [X] T020 Grep the files you changed for em-dashes, emojis and absolute local paths;
  remove any.

## Phase 8: rebase hooks (only for what landed on main)

At build time none of #354, #357 or #358 was on main; T021 to T023 wait for the rebase.

- [ ] T021 If #354 landed: test first in `tests/test_decision.py` and `tests/test_mcp.py`
  that `record` reads `wuwei decide D-n <label>` and `wuwei mcp decide D-n <label>`, then
  change `decision.RECORD` and `mcp.RECORD`; narrow `daily.md` "How you answer" to strict
  posture and credentials. Add a test that the recording command from the planner session
  exits 0 under observe and guarded after the widget was asked, through #354's allowance.
- [ ] T022 If #358 landed: test first in its `next` tests that `next --widget` prints
  `decision.record_widget` JSON for a pending D-n, `mcp.widget(root)` for the MCP step and
  `[]` for a step that asks nothing, and that plain `next` names `wuwei decision route
  D-n`; then add `--widget` to `next` delegating to those printers, and the one-line rule
  to the orientation block.
- [ ] T023 If #357 landed: run its hand-edit lint over the new skill and docs text and fix
  any hit. Anything not landed goes to the PR body as one TODO line per issue.

# Tasks: seats read live item state

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests run in process (`main([...])`, `verdict.lint_file`, `dispatch.receive`), no
subprocess, no network. Run the touched test files after each step, then the full suite
(`python -m pytest -q`).

## Phase 1: `why <item> --json` (FR-001, US3, US1)

- [X] T001 Test in `tests/test_why.py`: `test_why_json_reads_the_record_at_call_time`. In the
  `root` fixture write `[docs]\nsystem = "notion"\n`, an item `X` (`phase: gate`,
  `status: running`, `gates: {tier: standard}`, `worktree: <tmp>/tree`) with
  `tree/specs/001-x/` present, and the `plan.approved` event the item view reads (as in the
  existing tests near line 94). First call `main(['why', 'X', '--json'])`: exit 0,
  `docs == {'value': 'missing', 'reason': '', 'command': <contains 'plan set X docs='>}`,
  `ticket is None`, `spec == 'speckit artifacts: specs/001-x'`, `item == 'X'`,
  `day == '2026-10-02'`, and `steps` equals the lines `main(['why', 'X'])` prints. Then write
  `items.X.docs = {'value': 'page-1', 'reason': 'updated'}` and `tickets.X = {'id': 'acme/w#5'}`
  with `state._write_state` and call again: `docs.value == 'page-1'`, `docs.reason ==
  'updated'`, `ticket == 'acme/w#5'`. With `gates.tier = 'light'` `docs` is
  `{'value': 'n/a', 'reason': '', 'command': None}`; with `[spec] engine = "none"` `spec` is
  `None`.
- [X] T002 Test in `tests/test_why.py`: `--json` on an unknown item exits 1 with the existing
  `no recorded item` message; `why D-3 --json`, `why last refusal --json` and
  `why draft-<32 hex> --json` exit 2 with `--json reads an item` on stderr and nothing on
  stdout; a docs reason holding `TOKEN` (`tests/test_why.py:364`) never appears in the JSON.
- [X] T003 Implement in `cli/wuwei/commands/why.py`: the `--json` argument, `_days(root, name)`
  extracted from `item()`, `live(root, name, level)` and the `run` branch (plan.md, "why.py").

## Phase 2: the brief names the reader, not the values (FR-002, FR-003, US1)

- [X] T004 Test in `tests/test_brief.py`: in
  `test_builder_and_gate_briefs_carry_the_spec_line` the gate brief `g1` now has
  `spec_line(...) == []`; rename the test `test_only_the_builder_brief_carries_the_spec_line`;
  the builder briefs `b1`, `b2`, `b3` keep their assertions. Replace
  `test_quality_brief_names_the_missing_docs_value`,
  `test_quality_brief_shows_the_recorded_value` and `test_light_quality_brief_is_not_required`
  with `test_quality_brief_copies_no_docs_value`: with no value, with `{'value': 'none',
  'reason': 'internal refactor'}` and with tier `light`, `docs_brief(...)` for `quality` is
  `[]` (each with its own brief `name`). Keep `test_builder_brief_has_the_docs_rule` and
  `test_no_docs_line`.
- [X] T005 Test in `tests/test_brief.py`: `test_builder_and_gate_briefs_name_the_live_read`:
  the builder brief and the `sentinel-quality` and `sentinel-arch` gate briefs each carry
  exactly one line starting `Live: run bin/wuwei why X --json`; a `steward` brief carries none.
- [X] T006 Implement in `cli/wuwei/brief.py` (the `LIVE` constant, the line for
  `role == 'builder' or gate`, the `Spec:` line for the builder only) and in
  `cli/wuwei/docs.py` (`brief_line` returns only the builder line; delete the quality branch).

## Phase 3: the lint rule (FR-004, FR-006, US2)

- [X] T007 Test in `tests/test_verdict.py`: `test_lint_refuses_a_recorded_docs_value_called_missing`,
  a table on `verdict.lint(text, quality=True, class_sweep=True, docs=('X', 'docs/x.md'))`
  over a valid quality FIX verdict whose one finding line varies. Rejected (exit 1, message
  `finding 1: says the docs value is missing, but X records docs docs/x.md (bin/wuwei why X
  --json)`): `the docs value is missing`, `Docs value: missing`, `docs path not recorded`,
  `no docs value was set`, `DOC: required; value missing`. Accepted (exit 0): `the docs path
  docs/x.md is missing the --json flag`, `docs value none is wrong for a changed command`,
  `the return value missing a zone`. Every rejected row returns 0 with `docs=None`.
- [X] T008 Test in `tests/test_verdict.py`: `test_lint_file_reads_the_docs_value_at_lint_time`,
  with the seat-to-item setup of `tests/test_process_depth.py::gate_file` (a workspace with
  `[docs] system = "notion"`, item `A` tiered `standard`, seat `quality-1`): a gate file with a
  "docs value is missing" finding gives `lint_file(...)[0] == 0` while `A` has no docs value,
  and `1` naming the value once `items.A.docs = {'value': 'docs/a.md', 'reason': ''}` is
  written; an unknown seat name and `docs.system = "none"` give 0; the existing
  `test_lint_file_outside_a_workspace_is_standard` still passes.
- [X] T009 Test in `tests/test_invariants.py`: `i46` (READS `()`, memoized) runs the T007 rows
  through `verdict.lint` with `docs` set and `None` and returns a reason string on the first
  mismatch; add it to `INVARIANTS` and `READS`, and a `BROKEN` row `docs-missing rule off`
  that patches `verdict.DOCS_MISSING` to `re.compile(r'(?!)')`.
- [X] T010 Implement in `cli/wuwei/verdict.py`: `DOCS_MISSING`, the `docs` parameter of
  `lint`, `recorded_docs(path, data, root)` and the one `day_state` read in `lint_file`.

## Phase 4: receive time and the issue's acceptance (US1, US2, SC-002)

These two tests exercise the code of T003, T006 and T010 end to end. Write each, run it; if it
fails, fix the shared function it names, never the test.

- [X] T011 Test in `tests/test_dispatch.py`, beside
  `test_quality_pass_refused_while_docs_value_missing`:
  `test_quality_fix_refused_when_it_calls_a_recorded_docs_value_missing`: `docs_root(root)`,
  `docs.assign('A', 'none', 'internal refactor', root)`, then `record(root, 'quality',
  'quality-1', <DOC_FIX with its finding text saying the docs value is missing>)` raises
  `dispatch.Refused` matching `records docs none`, and `gate_verdicts` stays `{}`. The three
  existing docs receive tests pass unchanged.
- [X] T012 Test in `tests/test_brief.py`: `test_issue_acceptance_docs_recorded_after_the_brief`:
  write the quality gate brief for `X` with `[docs] system = "notion"`, tier `standard` and no
  docs value; the brief has no `Docs:` line and names `bin/wuwei why X --json`; then write
  `items.X.docs = {'value': 'docs/x.md', 'reason': ''}`; `main(['why', 'X', '--json'])` prints
  `docs.value == 'docs/x.md'`; with the seat record `{'item': 'X', 'role':
  'sentinel-quality', 'status': 'stopped'}` under the brief's name, a gate file
  `decisions/gate-<name>.md` whose finding says `the docs value is missing` gives
  `verdict.lint_file(path, role='sentinel-quality')[0] == 1`.

## Phase 5: charter and docs (FR-005, FR-006)

- [X] T013 Test in `tests/test_charters.py`: `test_docs_obligation_in_quality_and_builder_charters`
  asserts the quality charter names `bin/wuwei why <item> --json`, `DOC: FINDING` and
  `documented behaviour`, and no longer contains ``brief's `Docs:` line``; the builder half is
  unchanged.
- [X] T014 Update `charters/sentinel-quality.md` (version 1.2.0, step 7 as in plan.md), then run
  `bin/wuwei agents build` to regenerate `agents/sentinel-quality.md`.
- [X] T015 Amend `docs/specs/2026-09-24-wuwei-design.md`: the 5.12 "Before the gate verdict"
  sentence and the 9.2 row I46 (plan.md). Add the `--json` paragraph to the Why section of
  `docs/site/reference.md`.
- [X] T016 Run `python -m pytest -q`; grep the changed files for em-dashes, emojis and absolute
  local paths and remove any.

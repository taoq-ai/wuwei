# Tasks: setup creates the tracker labels the lifecycle uses, and pr raise says which label is missing instead of failing the move

Test first: each test task runs and fails for the expected reason before its implementation
task. Run only the touched test files while building; the full suite at the end.

## Phase 1: the port operation (FR-001)

- [X] T001 Tests in `tests/test_adapters.py`: add `('tracker', 'labels', ('create',), False)`
  to `CALLS`. Run `test_module_contracts` and `test_none_call`: fail (no `labels` in the
  registry or the adapters).
- [X] T002 Tests in `tests/test_tracker_adapters.py`: in `test_tracker_port_contract`, add
  `'labels': adapter.labels(False, root=root)` as the last entry of `results`; for GitHub
  append one reply to `tests/fixtures/tracker/github.json` with
  `repository: {id: "repo-node-1", label: {id: "label-review"}}` and assert
  `results['labels'].data == {'created': [], 'missing': []}`; for Linear and Jira assert the
  same data and no extra request. New `test_github_labels_reads_then_creates` (replay: label
  `null` with `create=False` gives `missing == ['In Review']` and one request; with
  `create=True` a second reply for `createLabel` gives `created == ['In Review']`, and the
  mutation's variables are `repositoryId`, `name == 'In Review'` and a color; every query is
  `balanced`). New `test_github_labels_follow_the_state_name_and_board` (`[tracker.states]
  in_review = "Review"` asks for `Review`; with `board = "acme/1"` no request is made). New
  `test_github_label_create_failure_names_the_label` (an `errors` reply to `createLabel`
  gives exit 2 whose reason has `"In Review"` and `acme/app`). Run: fail.
- [X] T003 Implement: `cli/wuwei/registry.py` (`PARAMETERS['tracker']['labels']`),
  `adapters/tracker/github.py` (`labels`, docstring), `adapters/tracker/linear.py`,
  `adapters/tracker/jira.py`, `adapters/tracker/none.py`; `tests/fakes/tracker.py`
  (`Fake.labels`, `ported` passes it). Run T001, T002: green.

## Phase 2: the shared helpers (FR-003, FR-004)

- [X] T004 Tests in `tests/test_tracker.py`: `test_creates_labels_by_posture_and_owner`
  (parametrized posture `observe`, `guarded`, `strict` x `outbound.code_host_orgs` holding the
  project owner or not, `adapters.tracker = "github"`, `tracker.project = "acme/app"`: true
  only below strict on the owned project; Linear below strict is true).
  `test_labels_none_and_malformed` (`adapters.tracker = "none"` gives exit 0 with empty lists
  and loads no adapter; a Fake answering `Result(0, {'created': []})` or `Result(0, None)`
  gives exit 2 naming the adapter data; a Fake raising `ValueError` gives exit 2).
  `test_ensure_labels_lines` (created `['In Review']` gives `['Upgraded tracker label "In
  Review"']` for prefix `Upgraded`; an exit 2 gives one `tracker labels not created: ...; run
  bin/wuwei doctor` line). Run: fail (no helpers).
- [X] T005 Implement `creates_labels`, `labels`, `ensure_labels` in `cli/wuwei/tracker.py`.
  Run T004: green.

## Phase 3: the failed in-review move (US2, US3, FR-003, FR-005, FR-006)

- [X] T006 Tests in `tests/test_dispatch.py` beside `test_tracker_call_uses_the_ticket`, with
  a GitHub-configured workspace (`adapters.tracker = "github"`, `tracker.project =
  "acme/app"`) and a Fake whose `transition` fails first with exit 2 and then succeeds:
  `test_in_review_creates_the_missing_label_and_moves` (posture `guarded`, `acme` in
  `outbound.code_host_orgs`, `labels` answering `created: ['In Review']`: the Fake saw
  `labels(True)` and two transitions, the result is exit 0, the `tracker.call` event has exit
  0; issue acceptance 2). `test_in_review_names_the_label_under_strict_or_external`
  (parametrized `strict` with an owned project, and `guarded` with `outbound.code_host_orgs`
  empty; `labels` answering `missing: ['In Review']`: the Fake saw `labels(False)` and one
  transition, the result is exit 1 with the exact reason of spec US2 scenario 2 for item `A`,
  and the event records it). `test_in_review_other_failure_is_unchanged` (`labels` answering
  no missing label, and `labels` failing with exit 2: the original transition result comes
  back). `test_done_never_reads_labels` (a failed `done` makes no `labels` call). Run: fail.
- [X] T007 Implement `relabel` in `cli/wuwei/tracker.py` and its one call in
  `cli/wuwei/dispatch.py` (`tracker_call`). Run T006 and `tests/test_dispatch.py`,
  `tests/test_tracker.py`: green.
- [X] T008 Tests in `tests/test_shepherd.py`: `test_raise_prints_the_tracker_reason` (a
  workspace with `adapters.tracker = "github"`, `dispatch.tracker_call` stubbed to return
  `Result(1, reason='A not moved to In Review: ...')`: `raise_pr` returns 0, stdout has the PR
  ref, stderr has `tracker: A not moved to In Review: ...`); with the stub returning
  `Result(0)` stderr has no `tracker:` line; with `adapters.tracker = "none"` and a failing
  stub, no `tracker:` line. Run: fail.
- [X] T009 Implement in `cli/wuwei/shepherd.py` (`raise_pr`, module `import sys`). Run T008 and
  `tests/test_shepherd.py`, `tests/test_undo.py`, `tests/test_merge.py`: green.
- [X] T010 Tests in `tests/test_tracker.py`: `test_tracker_move_runs_the_shared_move`
  (`main(['tracker', 'move', 'A', 'in_review'])` with `dispatch.tracker_call` stubbed: called
  with `('A', 'in_review', root)`, prints `A: ticket in_review`, exit 0; a `Result(1,
  reason=...)` prints `wuwei tracker: <reason>` on stderr and exits 1; `tracker done A` still
  prints `A: ticket done`; `tracker move A merged` is an argparse error, exit 2). In
  `tests/test_cli_known_command.py` nothing changes: `test_every_registered_command_is_in_exactly_one_set`
  fails until `tracker move` is in `WRITES`. Run: fail.
- [X] T011 Implement `move` in `cli/wuwei/commands/tracker.py` and `'tracker move'` in
  `commands.WRITES` (`cli/wuwei/commands/__init__.py`). Run T010 and
  `tests/test_cli_known_command.py`: green.

## Phase 4: setup, init --upgrade and doctor (US1, US4, FR-002, FR-007)

- [X] T014a Review fix F1: test `test_upgrade_from_a_seat_under_strict_creates_no_label`
  (no tty, strict, owned project: one `labels(False)` call, no label line); then
  `tracker.ensure_labels(root, prefix, create)`, setup passes True, `init --upgrade` passes
  `creates_labels(config) or sys.stdin.isatty()`.
- [X] T014b Review fix F4: `_tracker_labels` reports `ok` `unmeasured, tickets optional`
  when the port fails and `tracker.required` is false (test in `test_tracker_labels_row`).

- [X] T012 Tests in `tests/test_doctor.py`: `test_tracker_labels_row` (GitHub tracker with a
  Fake: `labels` answering `missing: ['In Review']` gives a `warn` row `missing: "In Review"`
  with fix `W('init --upgrade')` and a `labels(False)` call only; `missing: []` gives `ok`
  `none missing`; exit 2 gives `unmeasured` with the reason); `test_day_rows` stays as is (no
  `tracker labels` row on `none`). Run: fail.
- [X] T013 Implement `_tracker_labels` and its `diagnose` entry in
  `cli/wuwei/commands/doctor.py`. Run T012 and `tests/test_doctor.py`: green.
- [X] T014 Tests: in `tests/test_workspace.py` (in-process `init.upgrade` on a `tmp_path`
  workspace with `adapters.tracker = "github"` and `tracker.project = "acme/app"`, a stateful
  Fake via `registry.load`, whose `labels(create)` reports `In Review` missing until created):
  `test_upgrade_creates_tracker_labels_then_doctor_is_clean` (issue acceptance 1: the first
  upgrade prints `Upgraded tracker label "In Review"`; `doctor._tracker_labels` is then `ok`;
  a second upgrade prints no label line and the Fake saw no second create);
  `test_upgrade_dry_run_never_contacts_the_tracker` (dry run: no `labels` call).
  In `tests/test_setup.py`: `test_setup_creates_tracker_labels_before_doctor` (an existing
  setup end-to-end test's fixtures with a GitHub tracker: `labels(True)` is called before
  `doctor.diagnose`, and the `Created tracker label "In Review"` line is printed). Run: fail.
- [X] T015 Implement in `cli/wuwei/commands/init.py` (`upgrade`) and
  `cli/wuwei/commands/setup.py` (`_setup`). Run T014, `tests/test_workspace.py`,
  `tests/test_setup.py`, `tests/test_undo.py`: green.

## Phase 5: invariant and docs (FR-008)

- [X] T016 Test in `tests/test_invariants.py`: `i49` (reads posture, `READS['I49'] = (0,)`):
  for the case's posture, `tracker.creates_labels` on the loaded config with `adapters.tracker
  = "github"`, `tracker.project = "acme/app"` and `outbound.code_host_orgs` `["acme"]` and
  `[]` (build the variants by dict override of `workspace.load_config`, not new TOML tables)
  is true exactly for the owned project below strict. Add `'I49': i49` to `INVARIANTS`. Run:
  `test_table_matches_the_checks` fails (no I49 row).
- [X] T017 Docs: design spec 9.2 row I49 (`A missing tracker label is created by WUWEI on
  its own only on the owner's tracker below strict; under strict or on an external tracker
  the move names the label, bin/wuwei init --upgrade and bin/wuwei tracker move`; check:
  `tracker.creates_labels` per posture x owned and external project; `#670; one decision in
  tracker.creates_labels, reached by every in-review move through dispatch.tracker_call`),
  the port table at line 1861 (`labels(create)`), one sentence in 5.11 Setup and health;
  `docs/site/adapters.md` GitHub tracker paragraph. Run `tests/test_invariants.py`,
  `tests/test_docs.py`: green.

## Phase 6: close

- [X] T018 Run the full suite with the task's interpreter (`-m pytest -q`): all green. Check
  every written file for em-dashes and emojis.

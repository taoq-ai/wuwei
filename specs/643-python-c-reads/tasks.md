# Tasks: a read-only python -c on state.json is a read, not a records write

Test first: each test task runs and fails for the expected reason before its implementation
task. All tests run in process; nothing executes the snippets. Run only the touched test
files while working, then the full suite.

## Phase 1: the shared token scan (FR-001, FR-002)

- [X] T001 Test in `tests/test_shell.py`: `test_issue_643_snippet_write`, a table of argv and
  expected `shell.snippet_write` result (cases listed under Tests in `plan.md`: `''` for the
  reads including `-I -c` and `-Bc`; the token for `'w'`, `"a+"`, `'r+'`, `write_text`,
  `replace`, `shutil`, `subprocess`, `system`, the two `wuwei` import forms; `None` for a
  script, `-m json.tool`, `-i -c`, attached `-cprint(1)`, `-c` with no code, `node -e`,
  `cat -c`). Red: `snippet_write` does not exist.
- [X] T002 Implement `_SNIPPET_WRITES` and `snippet_write(argv)` in `cli/wuwei/shell.py` next
  to `_INTERPRETER`, with the `ponytail:` comment from `plan.md`.

## Phase 2: a read snippet is a read, through the hook (FR-001, US1, SC-001)

- [X] T003 Test in `tests/test_protect_state.py`: add to `test_issue_349_shared_read_predicate`
  the acceptance argv `['python3', '-c', "import json,sys; print(json.load(open('.wuwei/state.json'))['day'])"]`
  (True) and `['python3', '-c', "open('.wuwei/state.json', 'w')"]` (False). Red: the read
  returns False.
- [X] T004 Test in `tests/test_protect_state.py`: `test_issue_643_python_c_read_passes`,
  parametrized `observe`, `guarded`, `strict` on the `records` fixture: the acceptance
  command and a read of `_STATE` through `_hook` exit 0 and `_events(records)` gains nothing.
  Red: exit 2 with `Opaque interpreter`.
- [X] T005 Fold the python branch of `reads` in `cli/wuwei/shell.py` (line 889) into one
  branch returning `snippet_write(argv) == ''` after the `json.tool` rule; update its
  docstring. T003 and T004 go green.

## Phase 3: a refused snippet names its token (FR-003, FR-004, US2, SC-002)

- [X] T006 Test in `tests/test_protect_state.py`: `test_issue_643_write_snippet_names_token`,
  same postures: `check_bash` on `python3 -c 'open("{_STATE}", "w")'` returns exit 2 with
  `'w'` in the reason, on `python3 -c 'from pathlib import Path; Path("{_STATE}").write_text("x")'`
  exit 2 with `write_text` in the reason; `_hook` exits 2 for both. In the same test: the
  in-process owner action `python3 -c "from wuwei.commands import main; main(['decide','D-1','once'])"`
  still returns exit 2 from `check_bash`, and the acceptance read redirected with
  `> {_STATE}` returns exit 1. Update the exact reason asserted in
  `test_issue_349_writes_refused_in_every_posture` (line 928) to the new token reason.
  Red: the reasons carry no token.
- [X] T007 Test in `tests/test_invariants.py`: `i36` per posture (`READS['I36'] = (0,)`, added
  to `INVARIANTS`), memoized like `Rules.opaque`: the read of the day `state.json` (path from
  `workspace.day_dir(rules.root)`, relative to the root) through `rules.hook` exits 0;
  `check_bash` on the `'w'` and `write_text` snippets returns 2 with the token in the reason.
  Red: the reasons carry no token.
- [X] T008 Build the reason from `snippet_write(command.argv)` in `check_bash`,
  `cli/wuwei/guards/protect_state.py:616-622`; import it in the local `from wuwei.shell import`
  line; refresh the comment at line 617. T006 and T007 go green.

## Phase 3b: review fixes

- [X] T012 Owner-action readers in `_owner_action` (`cli/wuwei/guards/protect_state.py`) skip
  `python -c` snippets: `reads(...) and snippet_write(...) != ''`, so
  `python3 -c 'integrity.reconfirm()'` stays refused. Red: the test_integrity row and a new
  row in `test_issue_643_write_snippet_names_token`.
- [X] T013 Widen `_SNIPPET_WRITES` to fail closed, case-blind: any backslash, `chr`, `argv`,
  `environ`, `stdin`, `input`, `lower`, `decode`, `logging`, `Handler`, `extract`, `tarfile`,
  `zipfile`, `__`, `vars`, `globals`. Red: rows in `test_issue_643_snippet_write` and
  `test_issue_643_unusual_snippets_refused`.

## Phase 4: docs (FR-005, FR-006)

- [X] T009 Add row I36 to the 9.2 table in `docs/specs/2026-09-24-wuwei-design.md` (text in
  `plan.md`).
- [X] T010 `docs/site/security.md` line 66: one sentence after the read-only words: a
  `python -c` snippet with no write-like token is a read; any other snippet that names a
  record is refused with the first such token named.

## Phase 5: verify

- [X] T011 Full suite `python -m pytest -q` from the worktree root; grep the changed files
  for em-dashes and emojis; adversarial review (correctness, security, ponytail).

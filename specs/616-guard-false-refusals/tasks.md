# Tasks: guard false refusals on a published merge and on read-only gate reads

Test first: each test task runs and fails for the expected reason before its implementation
task. The push range test uses real git in `tmp_path`; nothing reaches the network. Run only
the touched test files, then the full suite.

## Phase 1: push range (FR-001, FR-002, US1)

- [X] T001 Test in `tests/test_vcs.py`: `test_invariant_push_identity_reads_only_unpublished_commits`
  (bare remote, GitHub-committed commit on `main`, feature branch that merges `origin/main`;
  tracking and new-branch ranges return only the feature's commits and `push_check` passes;
  a foreign-identity commit on no remote is returned and refused). Assert in
  `tests/test_vcs_guard.py` that the range argv ends in `--not --remotes --`. Red: the GitHub
  commit is returned and the allowlist has no `--not` form.
- [X] T002 Implement the argv and the `_run` allowlist case in `adapters/vcs/git.py`.

## Phase 2: read-only checksum tools (FR-005)

- [X] T003 Test in `tests/test_shell.py`: `shasum`, `sha1sum`, `sha256sum`, `sha512sum`,
  `md5sum`, `cksum` on a file classify `readonly`; `shasum x > y` does not.
- [X] T004 Add the six words to `shell.READ_ONLY`.

## Phase 3: verdict lint on Bash (FR-003, FR-004, US2)

- [X] T005 Test in `tests/test_verdict.py`: `test_invariant_read_only_bash_never_lints` and
  `test_invariant_bash_write_lints_by_file_name`; update the two scan tests whose bare `echo`
  becomes a read. Red: the reads return 1 and record events; the quality caller fails the
  security gate.
- [X] T006 Implement the read-only early return and `role=''` in
  `cli/wuwei/guards/verdict.py`.

## Phase 4: docs

- [X] T007 `docs/site/reference.md`: under Item worktrees, which commits the push identity
  check reads; under Gate verdict layout, when the lint runs (Write/Edit with the seat's role,
  a Bash call that can write with each file's own role, the seat's stop) and that a read is
  not linted.

## Phase 5: verify

- [X] T008 Full suite `python -m pytest -q`; adversarial review (correctness, security,
  ponytail).

# Tasks: Seats commit in a WUWEI worktree without setting git identity by hand

**Input**: `specs/246-worktree-identity/spec.md`, `specs/246-worktree-identity/plan.md`

**Tests**: required (constitution IV). Each test task is written, run with
`python -m pytest -q <file>` and seen failing for the stated reason before its
implementation task starts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency)
- **[Story]**: US1 worktree identity, US2 refusal names the fix, US3 reader mentions

## Phase 1: Setup

None. No new module, fixture file or dependency.

## Phase 2: Foundational (vcs port operation)

- [X] T001 [US1] Test, `tests/test_adapters.py`: add the row
  `('vcs', 'worktree_identity', ('repo', 'name', 'email'), False)` to `CALLS` after the
  `hooks_path` row. Fails in `test_module_contracts` (registry and adapter lack it).
- [X] T002 [US1] Test, `tests/test_vcs.py`:
  (a) `test_worktree_identity_port` with `install_replay(monkeypatch, 'git', [{'stdout': ''}, {'stdout': ''}])`
  asserting the two calls are `['git', '-C', '/repo', 'config', '--worktree', 'user.name', 'Builder']`
  and `[..., 'user.email', 'builder@example.test']` and the result is exit 0 with
  `{'name': 'Builder', 'email': 'builder@example.test'}`;
  (b) rows in `test_option_injection_never_spawns` for `worktree_identity` with
  `['/repo', '-x', 'b@example.test']`, `['/repo', 'A\nB', 'b@example.test']`,
  `['/repo', 'A', '<b@example.test>']`, `['/repo', ' ', 'b@example.test']`;
  (c) rows in `test_private_runner_rejects_unsupported_commands` for
  `('config', '--worktree', 'user.signingkey', 'x')` and
  `('config', '--worktree', 'user.name', '-x')`.
  Fails: operation missing; the allowlist rows may already pass (keep them as guards).
- [X] T003 [US1] Implement, `adapters/vcs/git.py`: the `_run` allowlist case and
  `worktree_identity` as in plan.md.
- [X] T004 [US1] Implement, `cli/wuwei/registry.py`: `'worktree_identity': ('repo', 'name', 'email')`
  in `PARAMETERS['vcs']`.
- [X] T005 [US1] Implement, `tests/fakes/vcs.py`: the `worktree_identity` recording method.
  T001 and T002 pass.

## Phase 3: User Story 1 - A builder commits in a fresh item worktree (P1)

- [X] T006 [US1] Test, `tests/test_worktree_command.py`, fake-based (reuse the `fake`
  fixture and `repos` helper; write an `identity = {...}` line into the entry):
  (a) with identity configured, `main(['worktree', 'add', 'X'])` is 0, the recorded calls
  end with `('worktree_identity', (str(root / 'worktrees/X'), 'Builder', 'builder@example.test'), root)`
  after `worktree_add`, and stdout JSON is unchanged;
  (b) `--repo web` with two entries writes the `web` entry's identity;
  (c) with no identity configured, no `worktree_identity` call is made;
  (d) with `vcs.results['worktree_identity'] = Result(2, None, 'git.worktree_identity: could not run: invalid identity')`
  the command exits 2.
  Fails: no `worktree_identity` call is made.
- [X] T007 [US1] Test, `tests/test_worktree_command.py`, acceptance through PreToolUse with
  real git (`test_template_identity_lets_a_seat_commit`): clear `GIT_*` and
  `WUWEI_WORKSPACE`; `git init -b main` a repo under `tmp_path` and make one commit with
  `-c user.name=Seed -c user.email=seed@example.test`; take the line starting with
  `# identity = ` from `templates/workspace/config.toml`, assert it contains
  `wuwei worktree add` (FR-005), uncomment its assignment and write a `[[repos]]` entry
  with it to `.wuwei/config.toml`; `fakes.integrity.seed(root)`; set `gate_approved` with
  `state._write_state(..., reserved=False)`; `chdir` to the root; `main(['worktree', 'add', 'X'])`
  is 0; stage a new file in `worktrees/X`; run `git commit -qm x` through
  `wuwei.commands.hook.run` with a PreToolUse Bash payload whose `cwd` is the worktree:
  exit 0. Then assert `git -C <repo> config --local --get user.name` returns 1 (main
  checkout untouched) and `git -C <tree> config --worktree --get user.email` is the
  template's email. Fails today: exit 2 with `GIT_AUTHOR_IDENT differs from configured
  identity`, and the template line lacks `wuwei worktree add`.
- [X] T008 [US1] Implement, `cli/wuwei/workspace.py`: `create_worktree(..., identity=None)`
  writes the identity after `install` as in plan.md.
- [X] T009 [US1] Implement, `cli/wuwei/commands/worktree.py`: pass
  `identity=repos[0]['identity']`. T006 passes; T007 passes except the template assertion.
- [X] T010 [US1] Implement, `templates/workspace/config.toml` line 11 comment and
  `docs/site/configuration.md` row `repos.identity`, as in plan.md. T007 passes.

## Phase 4: User Story 2 - A mismatched identity refusal names its fix (P1)

- [X] T011 [US2] Test, `tests/test_commit_push.py`: `test_identity_refusal_names_the_fix`
  calling `identity_check(OWNER, {'author': OTHER, 'committer': OWNER})` and
  `identity_check(OWNER, {'author': OWNER, 'committer': OTHER})`: code 1, reason starts
  with `GIT_AUTHOR_IDENT differs from configured identity` /
  `GIT_COMMITTER_IDENT differs from configured identity` and contains
  `wuwei worktree add`, `git config user.name Builder` and
  `git config user.email builder@example.test`; a name with a space
  (`{'name': 'Demo Owner', ...}`) appears shell-quoted (`'Demo Owner'`).
- [X] T012 [US2] Test, `tests/test_worktree_command.py`: extend T007's test (or a sibling
  sharing its setup) with `git -C <tree> config --worktree user.email other@example.test`,
  then the same PreToolUse commit payload exits 2 and `permissionDecisionReason` contains
  `wuwei worktree add` and `git config user.email builder@example.test`.
  T011 and T012 fail: the reason has no fix.
- [X] T013 [US2] Implement, `cli/wuwei/guards/commit_push.py`: `import shlex` and the new
  mismatch reason in `identity_check`. T011, T012 and the existing identity rows in
  `tests/test_commit_push.py` and `tests/test_git_hook.py` pass.

## Phase 5: User Story 3 - Reading or quoting a protected path is not a state write (P2)

- [X] T014 [US3] Test, `tests/test_protect_state.py`: `test_reader_mentions_are_not_writes`
  through `wuwei.commands.hook.run` (same shape as `test_discovered_guards_through_hook`,
  reusing `workspace` and `payload`), commands formatted with `root=workspace` (a pytest
  temp path has no quote characters):
  exit 0 for `echo 'see .wuwei/generated/agents/arch.md'`,
  `echo .wuwei/generated/agents/arch.md`,
  `echo 'Read instructions {root}/.wuwei/generated/agents/arch.md'`,
  `printf '%s\n' .wuwei/generated/agents/arch.md`, `cut -c1 .wuwei/config.toml`,
  `tr a b .wuwei/config.toml`, `rg -n x .wuwei/config.toml`;
  exit 2 for `echo x > .wuwei/generated/agents/arch.md`,
  `printf x >> .wuwei/config.toml`, `echo x | tee .wuwei/config.toml`,
  `echo .wuwei/config.toml | xargs rm`, `echo .wuwei/config.toml | sh`,
  `rg --pre rm x .wuwei/config.toml`, `rg --pre=rm x .wuwei/config.toml` and
  `rg --pre rm x .wuwei/days/2026-09-28/state.json` (rg --pre runs a command per file).
  Fails today on the bare, absolute, `printf`, `cut`, `tr` and `rg` rows (exit 2, "State
  and config files are protected").
- [X] T015 [US3] Implement, `cli/wuwei/guards/protect_state.py`: the reader early return
  after the `_wuwei_action` block and deletion of the old reader line, as in plan.md;
  rg with `--pre` does not take the early return.
  T014 and the whole of `tests/test_protect_state.py` pass.

## Phase 6: Polish

- [X] T016 Run `python -m pytest -q` from the repository root; everything passes.
- [X] T017 Check every changed file for em-dashes, emojis and absolute local paths; remove
  any.

## Dependencies & Execution Order

- T001 to T005 before T006 to T010 (the fake and adapter must exist for create_worktree).
- T011 and T012 can be written in parallel with Phase 3 tests; T012 reuses T007's setup, so
  write it after T007.
- Phase 5 (T014, T015) is independent of Phases 2 to 4 and can run in parallel [P].
- T016 and T017 last.

## Notes

- Do not touch files other in-flight issues own (plan.md, "Must not change").
- Do not commit, push or run `gh`.

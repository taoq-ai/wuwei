# Tasks: a new worktree fetches first and branches from origin/<base>

**Input**: `specs/681-worktree-from-origin/spec.md`, `specs/681-worktree-from-origin/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - the builder starts from what is on origin (P1)

### Tests first

- [X] T001 [US1] In `tests/test_worktree_command.py`, add a real-git acceptance test (no
  network): a bare `origin.git`, a repository with local `main` at commit C1 pushed to
  origin, then a second clone of origin commits C2 and pushes, so origin `main` is C2 and the
  repository's local `main` is C1 (reuse `hooked_workspace` for the workspace, stub CLI and
  gate). Run `main(['worktree', 'add', 'X'])`; assert exit 0, `git -C worktrees/X rev-parse
  HEAD` equals C2, `git -C worktrees/X merge-base HEAD origin/main` equals C2 (spec US1
  scenario 1, SC-001), and the printed JSON's `start` is C2. Run it; it fails (HEAD is C1).
- [X] T002 [US1] In `tests/test_worktree_command.py`, add the no-network acceptance test:
  `hooked_workspace`, then `git remote set-url origin <tmp_path>/missing.git`; run
  `main(['worktree', 'add', 'X'])`; assert exit 2, stderr names `fetch` and the remote, and
  `worktrees/X` does not exist, `git branch --list x` is empty and `git worktree list` has
  one entry (US1 scenario 2, SC-002). Run it; it fails (today the add succeeds from local
  main).
- [X] T003 [P] [US1] In `tests/test_vcs.py` and `tests/fixtures/vcs/recordings.json`, update
  the `worktree_add` recording: args gain `"origin", "main"`; steps are
  `fetch --no-tags origin main`, `rev-parse --verify FETCH_HEAD^{commit}` (stdout a 40-hex
  SHA) and `worktree add -b feature -- "/new worktree" <sha>`; `data` gains `start`. Keep
  `test_worktree_creation`'s exit parametrization on step 0. Add a test: the fetch step exits
  128 with a `fatal:` stderr line; assert exit 2, the reason contains `could not fetch origin
  main` and `no worktree was created`, and the replay saw exactly one call (no `worktree
  add`). Run them; they fail.
- [X] T004 [P] [US1] In `tests/test_vcs.py`, update the `test_option_injection_never_spawns`
  row for `worktree_add` to five args and add rows with remote `-x` and base
  `--upload-pack=x`; in `test_private_runner_rejects_unsupported_commands` add
  `('worktree', 'add', '-b', 'x', '--', '/tmp/w')` (no start) and
  `('worktree', 'add', '-b', 'x', '--', '/tmp/w', 'origin/main')` (start not a SHA). Run them;
  the no-start row fails (it is allowed today).

### Implementation

- [X] T005 [US1] In `adapters/vcs/git.py`, replace the `('worktree', 'add', '-b', branch, '--',
  path)` allowlist case with the seven-element case taking a full SHA start, and rewrite
  `worktree_add(repo, branch, path, remote, base, root=None)` as in plan Design 1 (fetch,
  wrapped failure, `FETCH_HEAD` SHA, add at the SHA, `start` in the result, the `ponytail:`
  comment). T003 and T004 pass.
- [X] T006 [US1] In `cli/wuwei/registry.py`, set `PARAMETERS['vcs']['worktree_add']` to
  `('repo', 'branch', 'path', 'remote', 'base')`; in `tests/test_adapters.py:62` update the
  matching `CALLS` row; in `tests/fakes/vcs.py:54` add `remote, base` to `worktree_add` and
  record them in the call tuple.
- [X] T007 [US1] In `cli/wuwei/workspace.py`, `create_worktree`: add `remote=None, base=None`
  and call `vcs.worktree_add(str(repo), branch, str(path), remote, base, root=root)` on the
  new-branch path (plan Design 3, without the event yet). In `cli/wuwei/commands/worktree.py`,
  `add`: pass `remote=config['brief']['remote'], base=repos[0]['default_branch']` (plan
  Design 4). T001 and T002 pass.

### Existing tests follow the new signature

- [X] T008 [US1] `tests/test_worktree_command.py`: the `fake` fixture's `worktree_add` result
  gains `'start': 'a' * 40`; lines 106 and 118 expect `'origin', 'main'` at the end of the
  recorded tuple; the line 24 test pushes `HEAD:refs/heads/main` to its bare origin before the
  add and expects `start` in the JSON; `hooked_workspace` and `adopt_workspace` push `main` to
  their bare origin after their last commit; the identity-template test (no remote) adds
  `[brief]\nremote = "."` to its config.
- [X] T009 [P] [US1] `tests/test_git_hook.py`: lines 282 and 346 pass `'origin', 'main'`; the
  line 346 test replays the three steps and asserts the three argv lists; line 337's fake
  result gains `start` and line 340 passes `remote='origin', base='main'`; lines 370 and 403
  pass `remote='.', base='HEAD'`. `tests/test_path_day.py:21`: the `worktree` stub takes
  `**kwargs`.
- [X] T010 [US1] Run the full suite; every test passes.

## Phase 2: User Story 2 - the record names where the worktree started (P2)

### Tests first

- [X] T011 [US2] In `tests/test_worktree_command.py`, extend T001's test: after the add,
  today's `events.jsonl` has exactly one `worktree.created` event with payload
  `{'item': 'X', 'worktree': <worktrees/X>, 'branch': 'x', 'base': 'origin/main', 'start':
  C2}` (US2 scenario 1). Run it; it fails (no event).
- [X] T012 [P] [US2] In `tests/test_why.py`, add a test: `merged_item(root)`, then
  `state.append_event('worktree.created', {'item': 'fix-login', 'worktree':
  'worktrees/fix-login', 'branch': 'fix-login', 'base': 'origin/main', 'start': HEAD},
  directory=day_of(root))`; assert `why fix-login` prints `BRIEF` with
  `worktree: branch fix-login from origin/main at abcdef123456` inserted right after the
  queued line (US2 scenario 2, SC-003). Run it; it fails.
- [X] T013 [P] [US2] In `tests/test_worktree_command.py`, assert
  `main(['event', 'worktree.created', '{}']) == 1` inside the `fake` fixture's workspace
  (the same pattern as `tests/test_build_next.py:214`). Run it; it fails (exit 0 today).

### Implementation

- [X] T014 [US2] In `cli/wuwei/workspace.py`, `create_worktree`: after a successful
  `worktree_add`, `state.append_event('worktree.created', ...)` as in plan Design 3. T011
  passes.
- [X] T015 [US2] In `cli/wuwei/commands/event.py`, add `'worktree.created': 'wuwei worktree
  add'` to `EVENT_PRODUCERS`. T013 passes.
- [X] T016 [US2] In `cli/wuwei/commands/why.py`, add `'worktree'` to `GROUPS` after
  `'queued'` and the `worktree.created` line in `item` (plan Design 6). T012 passes.

## Phase 3: Docs and close

- [X] T017 `docs/site/reference.md`, "Item worktrees" first paragraph: the fetch, the start
  at the fetched commit, exit 2 with nothing created on a failed fetch, `start` in the JSON
  and the `worktree.created` event shown by `why` (plan Design 7). If `tests/test_docs.py`
  pins the old "current HEAD" wording, update that assertion.
- [X] T018 `docs/specs/2026-09-24-wuwei-design.md`, section 8 adapters table, vcs row:
  `worktree_add(repo, branch, path, remote, base)`.
- [X] T019 Run `python -m pytest -q`; everything passes. Check every file you wrote for
  em-dashes, emojis and absolute local paths.

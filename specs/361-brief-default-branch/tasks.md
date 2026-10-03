# Tasks: item worktrees use their repository's default branch, and plan propose reads the scanner findings list

**Input**: `specs/361-brief-default-branch/spec.md`, `specs/361-brief-default-branch/plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Every behaviour is a test task followed by its implementation task. Run each test, see it
fail for the expected reason, then implement the minimum that makes it pass. Fixture names
stay neutral (`acme/widget`, `widget`, `example`, `X`). No absolute local paths in tests:
build every path from `tmp_path`.

## Phase 1: the brief finds the repository of an item worktree (US1, F3)

- [X] T001 Test: in `tests/test_brief.py`, add
  `test_item_worktree_uses_repository_default_branch` with real git and no `day` fixture:
  in `tmp_path` create a bare `origin.git` (`git init --bare -b master`), a repository
  `widget` (`git init -b master`, one empty commit with `-c user.name=... -c
  user.email=...@example.test`, `remote add origin`, `push origin master`, `fetch origin`),
  then `git worktree add -b x-work <tmp_path>/worktrees/X` from `widget`. Write
  `.wuwei/config.toml` with `[[repos]]` `name = "acme/widget"`, `path = "widget"`,
  `default_branch = "master"`; set `WUWEI_WORKSPACE` and `WUWEI_NOW`; write state with item
  `X` in phase `implement` (`state._write_state(..., reserved=False)`). Run the module's
  `brief(monkeypatch, 'body', 'builder', 'X', 'b1', '--worktree', 'worktrees/X')` helper;
  assert exit 0 and that the brief file contains `Merge-base: <sha> (origin/master)` where
  `<sha>` is `git rev-parse origin/master` in `widget`.
  Expect: exit 2, stderr `wuwei brief: git.merge_base: could not run: git exited 128`.
- [X] T002 Test: in `tests/test_brief.py`, add `test_missing_remote_branch_says_fetch` using
  the `day` fixture: config `[[repos]]` `name = "example"`, `path = "tree"`,
  `default_branch = "master"`; `day[2].results['merge_base'] = registry.Result(2, None,
  'git.merge_base: could not run: git exited 128')`. Assert `brief(..., 'builder', 'X',
  'nomerge', '--worktree', 'tree') == 2`, stderr contains `no merge base with origin/master
  in example`, `git.merge_base: could not run: git exited 128`, `git -C ` followed by the
  resolved `tree` path, and `fetch origin, then write the brief again`; no
  `briefs/nomerge.md`; no `brief written` event.
  Expect: exit 2 with only the bare `git.merge_base` reason (no `fetch`).
- [X] T003 Test: in `tests/test_brief.py`, add
  `test_worktree_of_unconfigured_repository_is_refused` using the `day` fixture: config
  `[[repos]]` `name = "example"`, `path = "widget"`, `default_branch = "master"`; replace
  `day[2].repo_context` (monkeypatch) with a function returning
  `registry.Result(0, {'path': f'{repo}/.git', 'common_dir': f'{repo}/.git'})`, so the
  worktree and the configured repository have different common directories. Assert
  `brief(..., 'builder', 'X', 'stray', '--worktree', 'tree') == 2`, stderr contains
  `repository is not configured in this workspace`, no `briefs/stray.md`, and no
  `merge_base` call in `day[2].calls`.
  Expect: exit 0 (today it measures against `origin/main`).
- [X] T004 Implement in `cli/wuwei/brief.py` `write()`: replace lines 245-247 with plan
  section 1 (path match, else `commit_push.context` when repositories are configured; the
  merge-base read wrapped with the coaching reason). T001 to T003 pass;
  `test_repo_default_branch`, `test_brief_records_item_worktree` and
  `tests/test_templates_errors.py` stay green.

## Phase 2: discovery reads the audit findings and never raises on the scanner (US2, F2)

- [X] T005 Test: in `tests/test_plan.py`, add a local helper `fake_ziran(monkeypatch, code,
  stdout, version='0.39.0')` that patches `subprocess.run` (as
  `tests/test_ziran.py::test_audit_and_gate_fixed_commands` does): `['ziran', '--version']`
  answers `ziran, version <version>` with exit 0; `['ziran', 'audit', <path>, '--format',
  'json', '--severity', 'low']` answers `stdout` with `code`. Add
  `test_plan_propose_lists_scanner_findings`, parametrized over (recorded report from
  `tests/fixtures/scanner/audit.json`, exit 1, `measured: 1`) and (the same report with
  `findings: []`, exit 0, `measured: 0`): using the `root` fixture, write config
  `[adapters]` `scanner = "ziran"` and `[[repos]]` `name = "acme/widget"`, `path =
  "widget"`, create `root / 'widget'`, set `WUWEI_WORKSPACE`, write `proposal()` to a file
  and run `main(['plan', 'propose', <file>])`. Assert exit 0,
  `proposal.json` `sweep['discovery.scanner']` equals the expected count, and for the
  one-finding case `plan.md` contains `- acme/widget:scanner:SA003:vulnerable.py:5: high
  SA003 vulnerable.py:5: Untrusted input reaches eval`.
  Expect: exit 2, stderr `wuwei plan: invalid scanner findings`.
- [X] T006 Test: in `tests/test_plan.py`, add `test_plan_propose_with_unrunnable_scanner`,
  parametrized over a ZIRAN version `0.38.9`, an audit exit code 3, and audit stdout
  `not json`, with the same setup as T005. Assert exit 0 and that
  `sweep['discovery.scanner']` starts with `unmeasured: acme/widget: ziran audit:
  unmeasured`.
  Expect: the value is `unmeasured: scanner read failed` (no repository, no cause).
- [X] T007 Test: in `tests/test_plan.py`, add
  `test_discover_marks_out_of_contract_scanner_unmeasured`, parametrized over
  `registry.Result(0, [])`, `registry.Result(1, {'files_analyzed': 1})`,
  `registry.Result(0, {'files_analyzed': 1, 'findings': ['x']})`,
  `registry.Result(5, None)` and `None`: with the T005 config, call
  `discovery.discover(root, ports={'scanner': <object whose audit returns the value>})` and
  assert `found['sources']['scanner'] == 'unmeasured: acme/widget: invalid scanner result'`
  and no scanner candidate.
  Expect: the list case reads `measured: 0`, the others raise.
- [X] T008 Implement in `cli/wuwei/discovery.py` `discover()`: replace lines 192-206 with
  plan section 2. T005 to T007 pass; `tests/test_quiet_sweeps.py`,
  `tests/test_linear_loop.py`, `tests/test_intraday_intake.py` and `tests/test_watch.py`
  stay green.

## Phase 3: finish

- [X] T009 Run `python -m pytest -q` from the repository root; everything passes.
- [X] T010 Check every file you changed or added for em-dashes, emojis and absolute local
  paths, and remove any.

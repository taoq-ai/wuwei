# Tasks: worktree add chains WUWEI's git hooks with a repository's own hooks

**Input**: `specs/472-hooks-chain/` (spec.md, plan.md, contracts/chain-hook.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. Real-git tests build their repositories in `tmp_path`, drop
`GIT_*` variables and give the repository an identity. No absolute local paths, emojis or
em-dashes in any file.

## Phase 1: the config key (US3)

- [X] T001 Test, `tests/test_git_hook.py`: `test_git_hooks_mode_config`: `load_config` on a
  workspace without `[worktree]` gives `config['worktree']['git_hooks'] == 'chain'`;
  `[worktree]\ngit_hooks = "replace"\n` gives `replace`; `git_hooks = "other"` raises
  `ConfigError` (spec US3 scenarios 1 and 4). Test, `tests/test_docs.py`:
  `test_worktree_git_hooks_is_documented`: the `` `worktree.git_hooks` `` row of
  `docs/site/configuration.md` names `chain`, `skip`, `replace`, `worktree.hooks_skipped`,
  `strict` and `PreToolUse`. Run `python -m pytest -q tests/test_git_hook.py -k mode_config
  tests/test_docs.py -k "worktree_git_hooks or names_every_config_section"` (fails: no
  `worktree` key, no row).
- [X] T002 Implement `SCHEMA["worktree"]` in `cli/wuwei/workspace.py` (plan Design 1), and
  the Sections entry and key row in `docs/site/configuration.md` (plan Design 9). Rerun
  T001; pass.

## Phase 2: the adapter chains, replaces, skips (US1, US2, US3, US4 at the port)

- [X] T003 Test, `tests/test_adapters.py`: `CALLS` rows for `hooks_path` with `('repo',
  'path', 'mode')` and a new read-only `hooks_target` with `('repo',)`. Test,
  `tests/test_git_hook.py`, real git in `tmp_path` (one helper: repository with a commit
  plus a linked worktree, optional `core.hooksPath` or default hook), against
  `adapter().hooks_path(tree, shims, mode)` with `shims` holding executable `pre-commit` and
  `pre-push` files:
  - `test_hooks_path_chains_custom_hooks_path`: `core.hooksPath` = a directory with
    `pre-commit` and an extra `post-checkout`; exit 0, `data['chained']` is that directory,
    the worktree's `config --worktree --get core.hooksPath` is `<git-dir>/wuwei-hooks`, the
    repository's `config --get core.hooksPath` is unchanged, and `pre-commit`, `pre-push`,
    `commit-msg`, `post-checkout` exist there, executable; `pre-commit` names the shim,
    `commit-msg` does not.
  - `test_hooks_path_chains_relative_hooks_path`: `core.hooksPath = .husky` (absent
    directory); exit 0 and chained to `<worktree>/.husky`.
  - `test_hooks_path_chains_default_hooks`: a real `.git/hooks/pre-commit`; chained to the
    common hooks directory.
  - `test_hooks_path_plain_without_custom_hooks`: samples only; worktree `core.hooksPath`
    is the shims directory, no `wuwei-hooks` directory, `chained == ''` (spec US4 1).
  - `test_hooks_path_rerun_finds_the_original`: a second call on the same worktree chains
    the same directory again and rewrites a changed script (spec US5 3).
  - `test_hooks_path_skippable_layouts`: `core.hooksPath` naming a regular file gives exit 1
    with `not a directory` in the reason and `extensions.worktreeConfig` enabled;
    `core.worktree` set gives exit 1 and `extensions.worktreeConfig` not enabled.
  - `test_hooks_path_modes`: `replace` with a custom path sets the shims directory and
    writes no `wuwei-hooks`; `skip` sets no worktree `core.hooksPath`, enables
    `extensions.worktreeConfig`, exit 0.
  - `test_hooks_target_reads_without_writing`: on the main checkout, `{'chain': <dir>}` with
    a custom path, `{'chain': ''}` without, exit 1 for a file; no config written.
  - Replace `test_hooks_path_preserves_custom_hooks` and
    `test_existing_default_hook_is_not_disabled` (they assert the refusal); keep one replay
    case where the first git call exits 128 and the result is exit 2.
  Run `python -m pytest -q tests/test_adapters.py -k module_contracts tests/test_git_hook.py
  -k "hooks_path or hooks_target"` (fails: wrong signature, refusals, no `hooks_target`).
- [X] T004 Implement in `adapters/vcs/git.py`: `Skippable` and its `_operation` clause, the
  two allowlist cases, `_worktree_config`, `_chain_target`, `_write_chain` with the
  contract's templates, `hooks_path(repo, path, mode)`, `hooks_target(repo)` (plan Design
  2). Update `PARAMETERS['vcs']` in `cli/wuwei/registry.py` (plan Design 3) and
  `tests/fakes/vcs.py` (plan "Tests that change"). Rerun T003; pass.

## Phase 3: worktree add chains end to end (US1, US4)

- [X] T005 Test, `tests/test_worktree_command.py` (new tests only; the existing ones stay
  as they are), modelled on `test_worktree_add_anchors_pre_push_outside_claude` but with a
  fresh `git init` repository and a bare origin:
  - `test_worktree_add_chains_repository_hooks_path`: `core.hooksPath` = a directory with an
    executable `pre-commit` and `pre-push` that each append a marker; the stub CLI records
    its arguments and exits 1 for `pre-push` (`[ "$2" != pre-push ]`). `main(['worktree',
    'add', 'X'])` exits 0; `git commit` in the worktree succeeds and both the stub
    (`git-hook pre-commit`) and the pre-commit marker ran; `git push origin x` fails, the
    stub saw `git-hook pre-push`, the pre-push marker is absent (spec US1 1, 2, 4).
  - `test_worktree_add_chains_default_hooks`: an executable `.git/hooks/pre-commit` marker
    and no `core.hooksPath`; commit runs the stub and the marker (spec US1 3).
  Test, `tests/test_git_hook.py`: in `test_hook_installer_writes_executable_safe_shims` the
  recorded call becomes `('hooks_path', (repo, shims, 'chain'))`. Run `python -m pytest -q
  tests/test_worktree_command.py -k chains tests/test_git_hook.py -k installer` (fails:
  `install` calls the port without `mode`).
- [X] T006 Implement in `cli/wuwei/commands/git_hook.py` `install`: read `worktree.git_hooks`
  (defaults without a config file) and pass it to `hooks_path` (plan Design 4, chain path
  only). Rerun T005 and `python -m pytest -q tests/test_worktree_command.py
  tests/test_git_hook.py`; pass.

## Phase 4: skip with a warning, refuse under strict (US2, US3)

- [X] T007 Test, `tests/test_worktree_command.py`:
  - `test_worktree_add_skips_unchainable_hooks_under_guarded`: `core.hooksPath` names a
    regular file; exit 0, the worktree exists and its `<git-dir>/wuwei-workspace` names the
    workspace, no worktree `core.hooksPath`, stderr has one `git hooks skipped` line with
    `not a directory` and `PreToolUse`, today's `events.jsonl` has one
    `worktree.hooks_skipped` with `worktree == 'X'` and the reason (spec US2 1).
  - `test_worktree_add_refuses_unchainable_hooks_under_strict`: the same with
    `[security]\nposture = "strict"\n`; exit 2, stderr has the reason and `worktree add
    again` (spec US2 2).
  - `test_worktree_add_skip_mode_never_refuses`: `[worktree]\ngit_hooks = "skip"\n` under
    strict with a normal repository; exit 0, warning and event with reason
    `worktree.git_hooks = "skip"`, the configured identity is in the worktree's
    `config.worktree` (spec US3 2).
  - `test_worktree_identity_skip_warns` (fake vcs): `worktree_identity` returns exit 1;
    `worktree add` exits 0 and prints the reason as a warning (spec US2 3).
  Test, `tests/test_vcs.py`: update `test_worktree_identity_port` (plan "Tests that
  change") and add `test_worktree_identity_needs_worktree_config`: replay
  `extensions.worktreeConfig` unset gives exit 1 and no write call. Test,
  `tests/test_signal_status.py`: `'worktree.hooks_skipped': 'nudge'` in the expected tiers.
  Test, `tests/test_state.py`: add `'worktree.hooks_skipped'` to
  `test_dedicated_event_kinds_reserved`. Run `python -m pytest -q
  tests/test_worktree_command.py -k "skip or strict" tests/test_vcs.py -k worktree_identity
  tests/test_signal_status.py -k intended_tiers tests/test_state.py -k dedicated` (fails:
  exit 2 instead of a warning, no event, identity writes without the check).
- [X] T008 Implement the skip and strict branch and the `repo_context` anchor fallback in
  `cli/wuwei/commands/git_hook.py` `install` (plan Design 4); the identity warning in
  `cli/wuwei/workspace.py` `create_worktree` (plan Design 5); the `worktree_identity` check
  in `adapters/vcs/git.py` (plan Design 2); the producer entry in
  `cli/wuwei/commands/event.py` (plan Design 6). Rerun T007; pass.

## Phase 5: doctor row (US1 5, US2 4)

- [X] T009 Test, `tests/test_doctor.py`: add `'hooks_target': Result(0, {'chain': ''})` to
  the `ws` fixture's vcs fake; new `test_git_hooks_row`: `{'chain': '/x/hooks'}` gives
  `ok` `chained with /x/hooks`; `''` gives `ok` `WUWEI hooks`; `Result(1, None, reason)`
  gives `warn` with that reason and a fix naming `init --upgrade` and
  `worktree.git_hooks`; `Result(2, ...)` gives `unmeasured`; `[worktree] git_hooks =
  "skip"` gives `ok` `skipped` with no `hooks_target` call. Run `python -m pytest -q
  tests/test_doctor.py -k git_hooks_row` (fails: no row).
- [X] T010 Implement the row in `cli/wuwei/commands/doctor.py` `_workspace` (plan Design
  7). Rerun T009 and `python -m pytest -q tests/test_doctor.py tests/test_reasons.py`; pass.

## Phase 6: regeneration on init --upgrade (US5)

- [X] T011 Test, `tests/test_git_hook.py`: `test_init_upgrade_regenerates_worktree_hooks`:
  after a real `create_worktree` on a repository with a custom hooks path, delete
  `<git-dir>/wuwei-hooks/pre-commit`; `init._worktree_hooks(root)` puts it back. With a spy
  on `init._worktree_hooks` and the workspace set up as the `init.upgrade` tests in
  `tests/test_workspace.py` do, a non-dry upgrade calls it once and `--dry-run` does not
  (spec US5 1, 2). A stale worktree (its `.git` points at a missing directory) gets a
  `wuwei init warning: <name>: ...` line and the other worktrees are still rewritten, so
  one broken worktree never stops an upgrade (review F1).
  Run `python -m pytest -q tests/test_git_hook.py -k regenerates` (fails: no helper).
- [X] T012 Implement `_worktree_hooks` and its call in `cli/wuwei/commands/init.py`
  `upgrade` (plan Design 8). Rerun T011 and `python -m pytest -q tests/test_workspace.py
  tests/test_templates_errors.py tests/test_env_credentials.py`; pass.

## Phase 7: polish

- [X] T013 Update the Item worktrees paragraph in `docs/site/reference.md` (plan Design 9).
  Run `python -m pytest -q tests/test_docs.py`; pass.
- [X] T014 Run the full suite, `python -m pytest -q`; pass. Check every changed file for
  em-dashes, emojis and absolute local paths; remove any.

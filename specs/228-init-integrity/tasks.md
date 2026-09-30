# Tasks: A workspace is usable right after init

Every behaviour has a test task before its implementation task. Run each new test and see
it fail for the expected reason before writing the code. Tests run in-process.

## Phase 1: Setup

- [X] T001 Write specs/228-init-integrity/spec.md, plan.md and tasks.md from issue #228 and the dry-run reproduction.

## Phase 2: US2 Reconfirm instruction at the source (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k reconfirm_line`.

- [X] T002 [US2] Add failing test `test_checkout_reasons_name_reconfirm_line` in tests/test_integrity.py using the `checkout` fixture: `api.check(root)` on a clean checkout returns exit 1 with a one-line reason ending `run wuwei integrity reconfirm on the host`; with `fake.results['status']` set to one modified entry, the reason contains `restore a clean commit and run wuwei integrity reconfirm on the host`; in both cases `api.cached(root)` returns exit 2 with the same reason and no `Errno`.
- [X] T003 [US2] Change the two reason strings in cli/wuwei/integrity.py (`measure` line 81, `check` line 160) as plan section 2 states.

## Phase 3: US1 and US2 Init measures last (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k init`.

- [X] T004 [US1] In tests/test_integrity.py, add failing test `test_init_measures_integrity_last` and adjust `test_init_pins_key_and_initializes_workspace_vcs` so it stubs `api.check`: replace `api.check` with a recorder returning `registry.Result(0, 'a' * 64)`; after `init.run(Namespace(path=str(tmp_path)))` returns 0, it was called once with the workspace root, `.wuwei/` existed at its final path when called, and stdout contains `plugin integrity: clean`. Parametrise with a recorder returning `registry.Result(2, reason='plugin integrity unmeasured: test')`: init still returns 0 and prints that reason, never `plugin integrity: clean`.
- [X] T005 [US1] Add failing test `test_init_upgrade_measures_unless_dry_run` in tests/test_integrity.py: create a workspace with `init.run` (recorder stub on `api.check`), clear the recorder, run `init.run(Namespace(path=..., upgrade=True, dry_run=True))` and assert no call; run it with `dry_run=False` and assert one call with the workspace root and `plugin integrity: clean` printed.
- [X] T006 [US1] Add failing acceptance test `test_signed_install_is_usable_right_after_init` in tests/test_integrity.py: `api.PLUGIN` set to `plugin(tmp_path)` with `api.write_manifest(base)` and a signature adapter returning `Result(0)`; `init.run` into a fresh directory returns 0 and prints `plugin integrity: clean`; `verdict.json` records exit 0; then `hook.run(Namespace(event='PreToolUse'))` with a Bash `ls` payload whose `cwd` is the workspace returns 0 (payload shape as in `test_integrity_hook_scope_and_session_exit`).
- [X] T007 [US2] Add failing acceptance test `test_development_checkout_init_says_reconfirm` in tests/test_integrity.py: `api.PLUGIN` set to `plugin(tmp_path)` plus a `.git` directory, `registry.load` returning for `vcs` a `Namespace` with `workspace_init` (Result 0), `head` (`{'sha': 'a' * 40}`), `status` (`[]`) and `read_tree` (the test plugin's tracked files), other kinds unchanged; `init.run` returns 0 and stdout has exactly one line containing `wuwei integrity reconfirm`; the next PreToolUse (Bash `ls`) returns 2 and its JSON `permissionDecisionReason` contains `run wuwei integrity reconfirm on the host` and not `Errno`.
- [X] T008 [US1] Add `_finish(root)` in cli/wuwei/commands/init.py and route the final return of `run` and the non-dry-run return of `upgrade` through it (plan section 1). Run T004 to T007 green.

## Phase 4: US3 One git process for tree blobs (P2)

Independent test: `python -m pytest -q tests/test_vcs.py -k read_tree`.

- [X] T009 [P] [US3] In tests/test_vcs.py, update `test_read_tree_recording` to the new second step (`cat-file --batch` output `'<40 hex> blob 13\nlearned rule\n\n'`), asserting the second argv ends with `cat-file`, `--batch` and that the stdin sent is `f'{ref}:roles/a b.md\n'` (capture it with a small wrapper around the replay `run`). Add a replay case where the batch output is `'<ref>:roles/a b.md missing\n'` and one with type `commit`: both return exit 2. Add `test_read_tree_real_git_one_batch`: a temp git repository with `a b.md` and `dir/c.bin` (bytes including `b'\xff'`), `read_tree(repo, 'HEAD', ['.'])` returns both contents (the binary one decoded with `surrogateescape`) and starts exactly two git processes (count through a wrapper around `subprocess.run`).
- [X] T010 [US3] Implement plan section 3 in adapters/vcs/git.py: `input` on `_run`, the `('cat-file', '--batch')` allowlist case, and batched parsing in `read_tree`. Run the timing one-liner from plan.md "Test notes" and record the time (expect well under 1 s, was 9 s).

## Phase 5: Docs

- [X] T011 Update docs/integrity.md, README.md and docs/site/index.md as plan section 4 states. Run `python -m pytest -q tests/test_docs.py`.

## Phase 6: Verify

- [ ] T012 Run `python -m pytest -q` from the repository root; everything passes. Check every file you wrote for em-dashes, emojis and absolute local paths.

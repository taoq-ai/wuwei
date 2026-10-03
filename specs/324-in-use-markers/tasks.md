# Tasks: Claude Code in-use process markers are not a tamper finding

Every behaviour has a test task before its implementation task. Run each new test and see
it fail for the expected reason before writing the code. Tests run in-process except the
one release smoke (T008).

## Phase 1: Setup

- [X] T001 Write specs/324-in-use-markers/spec.md, plan.md and tasks.md from issue #324 and the read-only reproduction.

## Phase 2: US1 and US2 Markers are pruned in inventory, and only markers (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k in_use`.

- [X] T002 [US1] Add failing test `test_in_use_markers_do_not_change_measure` in tests/test_integrity.py: `plugin(tmp_path)`, `api.write_manifest(base)`, a `MANIFEST.sha256.sig`, signature adapter faked to `Result(0)`; record `clean = api.measure(base)`; create `.in_use/12345`; `api.measure(base)` exits 0 with `data == clean.data`; remove it and create `.in_use/23456`: still exit 0 and the same fingerprint. Fails today with `page: plugin integrity: .in_use/12345`.
- [X] T003 [US2] Add failing parametrized test `test_in_use_cannot_hide_other_content` in tests/test_integrity.py, same setup, one case per shape with the expected reason fragment: `.in_use/evil.py` file -> `not a Claude Code process marker: .in_use/evil.py`; `.in_use/sub/` directory -> `not a Claude Code process marker: .in_use/sub`; `.in_use/12345` symlink to `charters/builder.md` -> `not a Claude Code process marker: .in_use/12345`; `charters/.in_use/12345` file -> `charters/.in_use/12345`; `.in_use` symlink to a directory outside `base` -> `symlink in installed plugin: .in_use`. Each asserts `measure` exit 1 and the fragment in `result.reason`. Today the empty `.in_use/sub/` measures clean and the other marker shapes carry different reasons, so the test fails; the nested and root-symlink cases already pass and guard against over-pruning.
- [X] T004 [US1] [US2] Implement plan sections 1 and 2 (inventory only) in cli/wuwei/integrity.py: add `MARKERS` and `_prune(plugin, directory, dirs)`, and replace the prune line in `inventory` with `_prune(plugin, directory, dirs)`. Run T002 and T003 green.

## Phase 3: US1 and US2 The cached-verdict walk uses the same helper (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k fresh`.

- [X] T005 [US1] [US2] Add failing test `test_fresh_ignores_markers_but_not_other_in_use_entries` in tests/test_integrity.py using the `fresh_plugin` fixture: with `later` past the verdict mtime, create `base/.in_use/12345` with `os.utime(later)`; `api.fresh(root) == registry.Result(0)`. Then create `base/.in_use/evil.py`: `api.fresh(root).exit != 0` and `.in_use/evil.py` is in its reason. Then remove `evil.py` and create `base/cli/.in_use/12345` with mtime `later`: `fresh` exits 1 naming `cli/.in_use/12345`. Fails today on the first assertion.
- [X] T006 [US1] In cli/wuwei/integrity.py `fresh`, replace the prune line with `_prune(PLUGIN, directory, dirs)` (plan section 2). Run T005 and the existing `-k fresh` tests green.

## Phase 4: US1 Confirmation survives process churn (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k marker_churn`.

- [X] T007 [US1] Add test `test_confirmation_survives_marker_churn` in tests/test_integrity.py: `workspace_root`, `plugin`, `api.PLUGIN = base`, faked signature `Result(0)`, `write_manifest`, `pinned.pub` copied. Signed case: create `.in_use/12345`, `api.check(root).exit == 0`, `api.cached(root).exit == 0`. Confirmed case: change `charters/builder.md`, `api.reconfirm(root, confirm=lambda digest: True).exit == 0`; remove `.in_use/12345`, create `.in_use/23456`; `api.check(root)` is exit 0 with the owner-confirmed reason and `api.cached(root).exit == 0`. Passes once T004 is in; run it against the code before T004 (stash or revert locally) to confirm it fails there, then keep it.

## Phase 5: US3 Release asset through the real launcher (P1)

Independent test: `python -m pytest -q tests/test_integrity.py -k launcher_with_marker`.

- [X] T008 [US3] Add test `test_release_asset_through_the_launcher_with_a_marker` in tests/test_integrity.py, skipped without `ssh-keygen`: build the stage with `scripts/build-release.py` `build()` and a faked signer (as `test_release_package_covers_every_shipped_file`); generate a throwaway ed25519 key, copy its public key over `<stage>/keys/manifest-signing-key.pub`, unlink `MANIFEST.sha256.sig`, `api.write_manifest(stage)`, sign with the real `ssh().sign`; create `<stage>/.in_use/12345`. With PATH led by a `python3` symlink to `sys.executable`, `HOME` in `tmp_path` and no `WUWEI_WORKSPACE`, run `<stage>/bin/wuwei init <ws>` (stdout has `plugin integrity: clean`), then pipe a Bash `ls` PreToolUse payload (cwd `<ws>`) to `<stage>/bin/wuwei hook PreToolUse` (exit 0). Create `<stage>/.in_use/23456`; `<stage>/bin/wuwei integrity check` exits 0 and the hook again exits 0. Run it against the code before T004 to see init print `.in_use/12345` and the hook exit 2, then keep it.

## Phase 6: Docs

- [X] T009 Add one assertion to `test_entry_guides_install_signed_release_and_explain_development_checkout` in tests/test_docs.py: `'.in_use' in integrity`. Run it, see it fail.
- [X] T010 Add the exclusion paragraph to docs/integrity.md as plan section 3 states. Run `python -m pytest -q tests/test_docs.py`.

## Phase 7: Verify

- [X] T011 Run `python -m pytest -q` from the repository root; everything passes. Check every file you wrote for em-dashes, emojis and absolute local paths.

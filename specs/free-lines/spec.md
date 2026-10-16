# Feature Specification: the manifest signing code moves out of the runtime into the release script

**Feature branch**: `claude/free-lines`
**Item**: free-lines, tier full, goal G-2
**Input**: `cli/wuwei/integrity.py` (60 lines) has no runtime caller since 1.0. Only
`scripts/build-release.py` imports it, and the doctor no longer measures the manifest.

## The promise in my words

The four functions in `cli/wuwei/integrity.py` (`inventory`, `write_manifest`, `sign`, `measure`)
and their constants move into `scripts/build-release.py`, the only file that uses them. The module
is deleted from `cli/wuwei/` and, by running `setup.vendor('.')`, from `.claude/wuwei/`. The release
workflow still runs `python3 -P scripts/build-release.py` with the same arguments and gets the same
signed archive and manifest format. A new `tests/test_release.py` builds and signs a release into
a temporary directory with a throwaway ed25519 key. It checks the signature verifies, a file
changed after signing is named, and a symlink is refused. The signing tests skip where
`ssh-keygen` is absent and run in CI. The runtime drops from 2,999 to 2,939 lines. The key, the
workflow file, the manifest format and any doctor check are out of scope.

The acceptance scenarios, restated:

1. A temporary output directory and a throwaway ed25519 key: `build()` writes `wuwei.tar.gz`.
   Its `MANIFEST.sha256` verifies against that key and lists every shipped file.
2. A staged release with one file changed after signing: the measure returns `changed: <file>`.
3. A symlink in the staged tree: the inventory raises `symlink in plugin`.
4. After the change the runtime is 2,939 lines or fewer, no module under `cli/wuwei` imports
   integrity, and the vendored-drift test passes.

## Clarifications

### Session 2026-10-16

- Q: `build()` verifies the stage against the public key shipped in `keys/`. How can a throwaway
  key verify? A: The test copies the shipped tree to a temporary root, puts the throwaway public
  key at `keys/manifest-signing-key.pub`, and points the script's `ROOT` there. The script is
  unchanged in behavior; the real key and the workflow are untouched.
- Q: Does `measure` keep its default argument? A: No. Its default was the installed plugin root,
  which has no meaning in the release script. Every caller passes the stage. The "a development
  checkout" hint in the unsigned message goes with it.
- Q: Does CI have `ssh-keygen`? A: Yes. The tests job runs on `ubuntu-latest`, whose runner image
  ships the OpenSSH client; the release job already relies on it to sign. No workflow change.
- Q: Should the size budget test tighten to 2,939? A: No. The freed lines are room for the next
  cli items. Acceptance 4 is held by a test that the module is gone and nothing imports it, and by
  the line count read at the head.

## User scenarios

### US1: the release still builds a signed, verifiable archive (P1)

Acceptance 1 and 2. Tests: `test_build_writes_an_archive_whose_manifest_verifies_and_lists_every_shipped_file`
and `test_the_measure_names_a_file_changed_after_signing`.

### US2: the inventory refuses a symlink (P1)

Acceptance 3. Test: `test_the_inventory_refuses_a_symlink`.

### US3: the runtime is smaller and holds no signing code (P1)

Acceptance 4. Tests: `test_no_runtime_module_is_or_imports_integrity`,
`test_the_vendored_plugin_matches_the_tree_it_was_copied_from`, `test_the_runtime_holds_its_size_budget`.

## Requirements

- FR-001: `scripts/build-release.py` defines `inventory`, `write_manifest`, `sign` and `measure`
  with the same behavior and manifest format as `integrity.py`.
- FR-002: `cli/wuwei/integrity.py` and `.claude/wuwei/cli/wuwei/integrity.py` are deleted.
- FR-003: The script's command line and exit codes are unchanged.
- FR-004: `tests/test_release.py` covers the acceptance; the signing tests skip without `ssh-keygen`.
- FR-005: No line is added under `cli/wuwei/`.

## How this fails

1. The release workflow breaks at the next tag because the script still imports something from
   `cli/` that moved, or because `-P` changes the import path. Guarded: the script no longer adds
   `cli/` to `sys.path` and imports only the standard library; the test loads it from its file and
   a manual run of `python3 -P scripts/build-release.py` reached the signature check.
2. The manifest format drifts (separator, order, excluded names), so an installed 2.x plugin or
   the security docs disagree with what ships. Guarded: the code moved verbatim; the test parses
   the manifest with the two-space separator and compares it with every shipped file.
3. The signing tests always skip in CI, so the build is never exercised before a release.
   Guarded by the runner image shipping `ssh-keygen`; the CI log shows them as passed, not skipped.
   Overturned if the runner drops OpenSSH, which also breaks the release job.

## Assumptions

- `ubuntu-latest` carries `ssh-keygen`. Why: the GitHub runner image includes the OpenSSH client
  and the release job signs with it today. Overturned if the tests job reports the two signing
  tests as skipped.
- Merging before or after the owner cuts 2.0.0 (#1080) is safe, because the new test runs the
  build. Overturned if CI cannot run `ssh-keygen`.

## Success criteria

- SC-001: The suite passes at the head; the four new tests pass where `ssh-keygen` exists.
- SC-002: `cli/wuwei/` holds 2,939 lines.

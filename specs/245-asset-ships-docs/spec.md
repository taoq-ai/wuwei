# Feature Specification: The release asset ships the operator docs it links to

**Feature Branch**: `245-asset-ships-docs`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #245, fix(release). Design sections 7.1 (signed manifests) and 10; related
#104, #165. Evidence: the fourth operator dry run on the v0.6.1 asset.

## Root cause (reproduced read-only on the v0.6.1 asset from the dry run)

The v0.6.1 `MANIFEST.sha256` has 180 lines and exactly one `docs/` entry,
`docs/integrity.md`; the archive has no `docs/site/`, no `docs/assets/`, no `docs/specs/`
and no `NOTICE`. The unpacked plugin's `docs/` directory holds only `integrity.md`.

The file list is an explicit include list in `build()` in `scripts/build-release.py`:

- lines 14-17 copy the directories `.claude-plugin`, `cli`, `adapters`, `bin`, `hooks`,
  `charters`, `skills`, `agents`, `templates`, `keys`;
- lines 18-19 copy the files `README.md`, `LICENSE`, `pyproject.toml`;
- lines 20-21 create `docs/` and copy only `docs/integrity.md`.

`integrity.write_manifest` (`cli/wuwei/integrity.py:50`) inventories whatever is staged,
so the manifest and the signature are correct for what was staged; the staging list is the
whole defect. The docs/site sources are hand-written (no generator in `scripts/`;
`scripts/build-hero.py` generates only `docs/assets/hero-*.svg`, which are committed).

Relative link targets in the shipped `README.md` today (skills/ and agents/ have none):
`docs/assets/hero-dark.svg`, `docs/assets/hero-light.svg`, `docs/integrity.md`,
`docs/site/index.md`, `docs/site/concepts.md`, `docs/site/configuration.md`,
`docs/specs/2026-09-24-wuwei-design.md`, `LICENSE`, `NOTICE`. Of these only
`docs/integrity.md` and `LICENSE` are in the v0.6.1 manifest.

No test notices: `test_release_package_covers_every_shipped_file`
(`tests/test_integrity.py:413`) checks one file under each copied directory, and no docs
test compares README links with the manifest.

## User Scenarios & Testing

### User Story 1 - An operator on the release asset can open every doc README points to (Priority: P1)

An operator who installed only the signed release follows README's links to the docs site
pages, the hero images, the design and NOTICE, and finds each file in the installed plugin,
covered by the signed manifest.

**Independent Test**: build the release with a stub signer and check the manifest and the
archive for every `docs/site/*.md` and `docs/assets/*.svg`.

**Acceptance Scenarios**:

1. Given the built asset, then every `docs/site/*.md` and every `docs/assets/*.svg` is
   listed in `MANIFEST.sha256` and present in the archive, the signer was called on that
   manifest, and `integrity.measure` of the staged plugin is clean (so the signature covers
   them).

### User Story 2 - A dangling doc link cannot reach a release (Priority: P1)

A maintainer who adds a README, skill or agent link to a file the release does not ship
gets a failing docs test naming the file and the link.

**Independent Test**: the new docs test run on `main` before the fix fails, naming
`NOTICE`, `docs/site/index.md`, `docs/site/concepts.md`, `docs/site/configuration.md` and
`docs/specs/2026-09-24-wuwei-design.md` as missing from the manifest.

**Acceptance Scenarios**:

1. Given the docs test, then a README link to a file missing from the manifest fails the
   test.
2. Given a link with a URL scheme (`https:`, `mailto:`) or a bare `#anchor`, then it is not
   checked; a `#fragment` on a relative link is dropped before resolving.

### Edge Cases

- Links are resolved relative to the linking file's directory (a skill linking
  `../../docs/x.md` resolves to `docs/x.md`).
- Both Markdown links `](target)` and HTML `src`, `srcset` and `href` attributes are
  checked; README uses both forms.
- The test must fail if the link regex stops matching anything: it asserts that
  `docs/site/index.md` (README's `href`) is among the resolved links.
- `scripts/headless_e2e.py` `prepare()` builds a scratch release from a partial copy of the
  repository (`scripts/headless_e2e.py:126-132`) that has no `NOTICE`; once
  `build-release.py` copies `NOTICE`, that scratch build exits 2 and
  `tests/test_headless_e2e.py::test_scratch_build_and_observer_preserve_hook_results`
  fails. See Assumptions.

## Requirements

- **FR-001**: `build()` in `scripts/build-release.py` stages the whole `docs/` directory
  and `NOTICE`, so every file README links to is in the manifest, the signature and the
  archive.
- **FR-002**: `tests/test_docs.py` builds the release with a stub signer and fails when any
  relative link in `README.md`, `skills/**/*.md` or `agents/**/*.md` resolves to a path not
  listed in `MANIFEST.sha256`, naming the linking file and the target.
- **FR-003**: The same test asserts every `docs/site/*.md` and `docs/assets/*.svg` is in
  the manifest and the archive, and that the staged plugin measures clean.
- **FR-004**: Signing, `integrity.write_manifest`, `integrity.measure` and the release
  workflow do not change.

## Success Criteria

- **SC-001**: The next release asset lists `docs/site/*.md`, `docs/assets/*.svg`,
  `docs/specs/2026-09-24-wuwei-design.md` and `NOTICE` in its manifest.
- **SC-002**: `python -m pytest -q` passes, including the new docs test and the existing
  release and headless scratch-build tests.

## Assumptions

- Ship the whole `docs/` directory, not a list of subdirectories. It is small (under
  200 KB), everything in it is public, and one entry in the existing copytree tuple covers
  `docs/site`, `docs/assets`, `docs/specs` and future docs without another list to keep in
  sync. `docs/site/_config.yml` and `docs/headless-e2e.md` ship too; they are harmless.
- `NOTICE` ships because README links it and Apache-2.0 section 4(d) expects NOTICE to
  travel with the work.
- The docs site pages link each other as `*.html` (GitHub Pages form). In the unpacked
  asset those resolve only through the published site. The issue scopes the link check to
  README, skills/ and agents/, so the site pages' own links are not checked or rewritten.
- The link test lives in `tests/test_docs.py` (orchestrator note) and builds the release
  itself (about 0.15 s), using the same stub-signer pattern as
  `tests/test_integrity.py:413`. `tests/test_integrity.py` is left unchanged.
- `scripts/headless_e2e.py` is listed as in flight for #239. The orchestrator note says not
  to touch it, but FR-001 makes its scratch source build fail without `NOTICE`. The
  builder adds `'NOTICE'` to the file tuple on `scripts/headless_e2e.py:129` and nothing
  else. That line lies outside every hunk of #239's current diff (its hunks near there
  start at lines 112, 114 and 148), so the two changes merge without conflict. This is
  the one deviation from the note, recorded here for the orchestrator.
- The release smoke that opens a docs/site page from the unpacked asset is owner tooling
  outside the repository; the orchestrator updates it.
- No reproduction through `bin/wuwei hook PreToolUse` applies: this is a packaging defect,
  reproduced from the dry run's manifest and archive listing.

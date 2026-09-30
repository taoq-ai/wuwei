# Implementation Plan: The release asset ships the operator docs it links to

**Branch**: `245-asset-ships-docs` | **Spec**: `specs/245-asset-ships-docs/spec.md`

## Summary

Fix the staging list at the one spot every release goes through, `build()` in
`scripts/build-release.py`: copy `docs/` whole with the other directories and `NOTICE`
with the other files. Add one docs test that builds the release with a stub signer and
checks README, skill and agent links against the manifest. One token in
`scripts/headless_e2e.py` keeps its scratch build in step.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Nothing under `cli/`, `adapters/`, `hooks/`,
`docs/` or `.github/` changes.

## Constitution Check

- I Stdlib only: the test uses `runpy`, `tarfile`, `posixpath`, `re`, `argparse.Namespace`.
- III One behaviour, one function: staging stays in `build()`; the manifest is still
  written by `integrity.write_manifest`, which already inventories everything staged.
- IV Test first: the docs test fails on `main` naming the missing links before
  `build()` changes.
- V Ponytail: one tuple entry instead of a per-subdirectory list; no manifest filter, no
  new helper module, no change to `tests/test_integrity.py`.
- VII Security: the signed manifest now covers more files; signing and verification code
  are untouched.

## Changes

### 1. Docs test (`tests/test_docs.py`), written first

New test `test_release_asset_ships_every_linked_doc(tmp_path, monkeypatch)`, appended at the
end of the file. Imports it needs at module top: `from argparse import Namespace`,
`import posixpath`, `import runpy`, `import tarfile`, `from wuwei import integrity, registry`
(`pythonpath` in `pyproject.toml` already includes `cli`).

Body:

1. Stub the signer exactly as `tests/test_integrity.py:413-425` does:
   `signed = []`; `sign(manifest, key)` appends `Path(manifest)`, writes
   `str(manifest) + '.sig'`, returns `registry.Result(0)`;
   `monkeypatch.setattr(integrity, 'signature_adapter', lambda: Namespace(sign=sign, verify=lambda *a: registry.Result(0)))`.
2. `build = runpy.run_path(str(ROOT / 'scripts/build-release.py'))['build']`;
   `archive = build(ROOT, tmp_path / 'release', tmp_path / 'key')`;
   `stage = tmp_path / 'release/wuwei'`;
   `listed = {line[66:] for line in (stage / integrity.MANIFEST).read_text().splitlines()}`.
3. Links (acceptance 2, asserted first so the red run names the missing files):
   for each `path` in `[ROOT / 'README.md', *sorted((ROOT / 'skills').rglob('*.md')), *sorted((ROOT / 'agents').rglob('*.md'))]`,
   `name = path.relative_to(ROOT).as_posix()`; for every match of
   `r'\]\(([^)\s]+)\)|(?:src|srcset|href)="([^"]+)"'` take the non-empty group; skip it if
   it contains `':'` or starts with `'#'`; resolve
   `posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split('#')[0]))`;
   collect resolved paths and `f'{name} -> {target}'` for each resolved path not in
   `listed`. Assert `'docs/site/index.md' in resolved` (the regex still sees README's
   links) and `not missing`, with `missing` as the message.
4. Shipped docs (acceptance 1): `expected` = relative posix names of `SITE.glob('*.md')`
   and `(ROOT / 'docs/assets').glob('*.svg')`; with `tarfile.open(archive)` build
   `archived = {n.removeprefix('wuwei/') for n in tar.getnames()}`; assert
   `expected <= listed`, `expected <= archived`,
   `signed == [stage / integrity.MANIFEST]`, and `integrity.measure(stage).exit == 0`.

On `main` this fails at step 3 with `README.md -> NOTICE`, `README.md -> docs/site/...`
and `README.md -> docs/specs/2026-09-24-wuwei-design.md`.

### 2. Staging (`scripts/build-release.py`, `build()`)

- Line 15: add `'docs'` to the directory tuple copied with `shutil.copytree` (same
  `ignore` pattern).
- Line 18: file tuple becomes `('README.md', 'LICENSE', 'NOTICE', 'pyproject.toml')`.
- Delete lines 20-21 (`(stage / 'docs').mkdir()` and the single `docs/integrity.md`
  copy); the copytree covers it.

Nothing else in the script changes: signing, `integrity.measure`, the archive call and
`main()` stay as they are.

### 3. Headless scratch build (`scripts/headless_e2e.py`, `prepare()`)

- Line 129: add `'NOTICE'` to the file tuple
  (`('README.md', 'LICENSE', 'NOTICE', 'pyproject.toml', 'docs/integrity.md', 'scripts/build-release.py')`).
  Without it `build()` raises on the missing `NOTICE`, the scratch build exits 2 and
  `test_scratch_build_and_observer_preserve_hook_results` fails. The scratch `docs/`
  (holding `integrity.md`) is still created by this loop, so `copytree('docs')` works
  there. No other line in this file changes (it is in flight for #239; see spec
  Assumptions).

## Must not change

`cli/wuwei/integrity.py` (inventory, manifest format, `measure`, `signature_adapter`),
`.github/workflows/release.yml`, `tests/test_integrity.py`, `tests/test_headless_e2e.py`,
everything under `docs/`, `README.md`, and every file named by the in-flight issues:
`docs/site` daily path page, `tests/test_e2e_day.py`, `cli/wuwei/guards/__init__.py`,
`cli/wuwei/commands/config.py`, and `scripts/headless_e2e.py` beyond the one token above.

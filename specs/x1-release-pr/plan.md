# Plan: a release-please PR is read as generated (X-1, X-2)

## Approach

- `cli/wuwei/evidence.py`: a `RELEASE_BOTS` tuple and a `release(repo, pr)` predicate. It checks the
  author and the branch first, so other PRs make no extra API call. It then reads
  `release-please-config.json` at `pr['baseRefName']`, collects each package's `extra-files` paths,
  and requires every changed path to be in that set plus the manifest and CHANGELOG.md. Outside
  CHANGELOG.md every `+`/`-` line of the file's patch, split on `\n`, must fullmatch `VERSION_LINE`
  (ASCII, strict semver, key `version` outside the manifest), the patch must be non-empty, and no
  file may be a rename. Any exception while reading the config counts only the manifest.
- `cli/wuwei/gh.py`: `pr()` keeps each file's `patch` and a `renamed` flag from `previous_filename`.
- `gaps`: when `release` is true, `gates_for` gets no files (so `needed` asks for no gate) and the
  code list for the test gap is empty. This is the docs path, reached without touching `needed`.
- Lines: the predicate adds 22 (two imports, two constants, the function). evidence.py frees them: blank lines in the constants block,
  DEFERRED and REASON moved to it, the checklist loop in `_rule` and the dedupe loop in `spec_gaps`
  as single expressions, shorter `_unchecked` and `ci_gaps` returns, and assignment expressions for
  five assign-then-test pairs. Runtime: 2,999 lines.
- `tests/test_evidence.py`: tests over the 1.2.1 shape with its real patches. FakeGh's files route
  now passes `patch` and `previous_filename` through, as the REST API does.

## Constitution check

Stdlib only (`json`, `posixpath`), no new module, runtime under 3,000 lines, test first.

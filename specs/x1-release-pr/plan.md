# Plan: a release-please PR is read as generated (X-1, X-2)

## Approach

- `cli/wuwei/evidence.py`: a `RELEASE_BOTS` tuple and a `release(repo, pr)` predicate. It checks the
  author and the branch first, so other PRs make no extra API call. It then reads
  `release-please-config.json` at `pr['baseRefName']`, collects each package's `extra-files` paths,
  and requires every changed path to be in that set plus the manifest and CHANGELOG.md.
- `gaps`: when `release` is true, `gates_for` gets no files (so `needed` asks for no gate) and the
  code list for the test gap is empty. This is the docs path, reached without touching `needed`.
- Lines: the predicate adds 16. evidence.py frees them: blank lines in the constants block,
  DEFERRED and REASON moved to it, the checklist loop in `_rule` and the dedupe loop in `spec_gaps`
  as single expressions, and shorter `_unchecked` and `ci_gaps` returns. Runtime: 2,999 lines.
- `tests/test_evidence.py`: four tests over the 1.2.1 shape. FakeGh's contents route already serves
  `release-please-config.json`; no conftest change.

## Constitution check

Stdlib only (`json`, `posixpath`), no new module, runtime under 3,000 lines, test first.

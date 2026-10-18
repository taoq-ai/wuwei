Verdict: PASS
Gate: quality
Item: changelog-all-types
PR: taoq-ai/wuwei#1125
Head: c1519416216d55ffb07e5265d74a69530e533311
Confidence: medium

## Findings
- [low] tests/test_setup.py:196 blocks: no. The test name says "every commit type on main", but it checks a fixed eleven-type tuple, not the types the repository uses. A twelfth type (for example `deps` or `security`) added to main would be hidden by release-please's defaults and this test would not notice. The eleven are the full conventional-commit set and the log since v2.0.0 uses only fix, docs, refactor, feat and chore, so this is a limit, not a regression.
- [low] tests/test_setup.py:206 blocks: no. The `section` check accepts any non-empty string, so a wrong or misspelled section title would pass. Cosmetic only.
- [low] specs/changelog-all-types/spec.md blocks: no. Acceptance 2 (the 3.0.0 release PR lists #1123, #1124 and this change) needs a live release-please run after merge. It is unmeasured here. The spec names the check (`gh api repos/taoq-ai/wuwei/pulls/1110 --jq .body`).

## Probes
- Red on main: `git archive d4a809d` config swapped into a copy of the head tree, `pytest -q tests/test_setup.py` gives `1 failed, 38 passed`. The failure is the new test, "feat has no changelog section ... assert 'feat' in {}".
- Green at the head: the same file gives `39 passed`. The full suite gives `1683 passed, 2 skipped`. The new test is collected and not skipped (-k run, 3 selected).
- Mutants, each run in a fresh copy of the head, test run with `-k visible`:
  - Drop `chore`: killed.
  - Drop `style`: killed.
  - Add `"hidden": true` to `docs`: killed.
  - Remove the `section` value of `perf`: killed.
  - Set `section` to the empty string: killed.
  - Rename the key `changelog-sections` to `changelog-section`: killed.
  - Move the list to the config root: killed.
  - Rename an entry's `type` key to `types`: killed.
  - `"hidden": false` on `docs`: survived. This is equivalent, because release-please reads false as visible. It is not a defect.
- Config shape: `json.load` of the head file is valid. `changelog-sections` is in the package block, the shape the existing test reads (`config['packages']['.']`). The `[{type, section}]` form is the one release-please's schema defines. The only other reader of the file, `cli/wuwei/evidence.py:115-117`, reads `packages[*].extra-files`, so the new key does not touch it. `test_release_please_is_not_pinned_to_a_version_already_released` and the extra-files tests in test_evidence.py pass in the full run.
- Section names match release-please's default titles (Features, Bug Fixes, Performance Improvements, Reverts, Documentation, Code Refactoring, Tests, Build System, Continuous Integration, Miscellaneous Chores, Styles), as the spec states.
- Spec claim that `chore` visible does not list release-please's own `chore(main): release` commits: `git log` shows those commits (a7fe6d5, 2a306da, 041b83d) sit at the release tag boundaries, and `git log v2.0.0..d4a809d` has none. release-please collects commits after the last release, so this fits what I can read. Whether a 3.0.0 body shows a `chore(main): release` line is unmeasured and needs a live release run. The spec already names the overturning condition.
- The existing CHANGELOG.md 2.0.0 section has only Features, Bug Fixes and breaking changes, which matches the problem the item names (docs and refactor hidden).
- Guard-parsing probes: not applicable. The diff holds no guard or hook code (no `cli/wuwei/guards.py` or `hook.py` change), so the route corpus and the generated parser probe do not apply.

Simplicity: none. The eleven-entry list is the minimum that makes the default-hidden types visible. A shorter list naming only the seven hidden types would leave feat and fix on release-please's defaults, which the list in this diff does not do. The one test is a single assertion loop. No runtime code is added.

## Residual risk
Display-only config with no runtime effect and a one-commit rollback. The 3.0.0 release PR contents are unmeasured until release-please runs on main after the merge.

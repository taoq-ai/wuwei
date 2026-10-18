# Implementation plan: changelog-all-types

**Spec**: `specs/changelog-all-types/spec.md`
**Item**: changelog-all-types, tier standard, goal G-2

## Technical context

- release-please `simple` release type, manifest-driven, config in `release-please-config.json`.
  Default `changelog-sections` show feat, fix, perf and revert; the rest are hidden.
- The Release workflow runs on every push to main and rebuilds the release PR when the visible
  commit set changes.
- No runtime code; the test lives in `tests/test_setup.py`, which already reads the config.

## Design

1. Add `changelog-sections` under `packages["."]`, one object per type with release-please's
   default section names, no `hidden` keys.
2. Add `test_every_commit_type_on_main_has_a_visible_changelog_section` next to the existing
   release-please test.

## Verification

- Test red on the old config, green at the head; full suite green.
- After merge: the Release workflow run on the merge commit and the release PR body listing
  #1123, #1124 and this change.

## Constitution check

Stdlib only, no door, no config key of WUWEI's own, test first, runtime unchanged.

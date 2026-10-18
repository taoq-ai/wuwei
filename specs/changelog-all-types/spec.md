# Feature Specification: every conventional commit type on main has a visible changelog section

**Feature branch**: `claude/focused-hopper-90dros`
**Item**: changelog-all-types, tier standard, goal G-2
**Input**: the owner wants all of main in the 3.0.0 release. The release PR (#1110) lists the
breaking changes and bug fixes only: release-please hides `docs`, `refactor`, `chore`, `test`,
`ci`, `build` and `style` commits by default, so #1123 (refactor) and #1124 (docs) are missing
from its notes, and a hidden commit does not trigger a rebuild of the release PR.

## The promise in my words

`release-please-config.json` gains a `changelog-sections` list naming a section for every
conventional commit type the repository uses (feat, fix, perf, revert, docs, refactor, test,
build, ci, chore, style), none hidden. A test holds it. On merge to main, release-please rebuilds
the release PR and its body and `CHANGELOG.md` list every commit since v2.0.0. Runtime lines: 0.

Outside: the release workflow, the version bump, the tag, the signed artifact.

Acceptance, restated:

1. Given the config at the head, when the test reads `changelog-sections`, then every listed type
   has a section and none is hidden.
2. Given the change merged to main, when release-please runs on the push, then the release PR for
   3.0.0 lists #1123, #1124 and this change.

## User Scenarios & Testing

### US1: the config names every type (P1)

Acceptance 1, held by `test_every_commit_type_on_main_has_a_visible_changelog_section`. Red on
the old config (no `changelog-sections` key): `1 failed`. Green at the head.

### US2: the release PR regenerates (P1)

Acceptance 2 is verified after merge by reading the release PR body (`gh api
repos/taoq-ai/wuwei/pulls/1110 --jq .body`) for the three PR numbers.

## Requirements

- FR-001: `changelog-sections` in `release-please-config.json` with the eleven types, none hidden.
- FR-002: the test above in `tests/test_setup.py`.

## Assumptions

- Tier `standard`: the file is a changelog display setting with no runtime, door or permission
  effect; the diff adds no risky or contract path, so the quality gate alone runs. Overturned if
  the owner wants release configuration treated as infrastructure (`full`).
- `chore` visible does not list the release commits themselves: release-please collects commits
  since the last release tag, and the tagged release commit is the boundary. Overturned if the
  regenerated 3.0.0 notes show a `chore(main): release` line, in which case `chore` goes hidden
  again.
- Section names follow release-please's own defaults (Features, Bug Fixes, Performance
  Improvements, Reverts, Documentation, Code Refactoring, Tests, Build System, Continuous
  Integration, Miscellaneous Chores, Styles).

## Rollback

Rollback: revert the commit; the next push to main regenerates the release PR with the default
sections. No runtime, version or tag change.

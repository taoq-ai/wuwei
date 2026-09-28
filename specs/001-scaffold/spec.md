# Feature Specification: Repository scaffold

**Feature Branch**: `001-scaffold`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #1, M0 Foundation: repository scaffold, plugin manifest and marketplace.

## User Scenarios & Testing

### User Story 1 - Install the plugin (Priority: P1)

A user installs WUWEI from its own repository marketplace.
**Independent Test**: Load both manifests and validate their installation contract.
**Acceptance**: Given a fresh clone, when `/plugin marketplace add` points at it
and the user installs `wuwei@wuwei`, then installation succeeds without errors.

### User Story 2 - Validate and release changes (Priority: P2)

A maintainer gets automated tests and conventional-commit release PRs.
**Independent Test**: Run pytest and inspect the CI matrix and release configuration.
**Acceptance**: Given the scaffold without runtime tests, when CI runs on Python
3.11 and 3.12, then the manifest test passes. Given a `feat:` commit on main,
when release-please runs, then it opens a release PR updating the plugin version.

### Edge Cases

- Missing or malformed manifests, mismatched names, and a non-root source fail validation.
- The marketplace must not override the plugin version.
- No runtime components exist yet; manifests must not reference absent paths.

## Requirements

- **FR-001**: Plugin name is `wuwei`, initial version `0.1.0`, author TaoQ AI Labs.
- **FR-002**: Marketplace owner is TaoQ AI Labs; its sole plugin source is `./`.
- **FR-003**: Use only defined Claude Code manifest fields.
- **FR-004**: Include full Apache 2.0 LICENSE, NOTICE, and a short installation README.
- **FR-005**: Include Python 3.11+ metadata, optional pytest dev dependency,
  pytest pythonpath `cli`, and testpaths `tests`.
- **FR-006**: CI runs pytest on 3.11 and 3.12; release-please uses conventional
  commits and updates plugin.json through an extra-files JSON updater.
- **FR-007**: Add one real manifest test before implementation; no runtime or placeholders.

## Success Criteria

- **SC-001**: Local plugin and marketplace validation succeeds.
- **SC-002**: The specified pytest command exits zero.
- **SC-003**: Release configuration targets the plugin version and main branch.

## Assumptions

- Marketplace name is `wuwei`, giving install identifier `wuwei@wuwei`.
- Empty-suite acceptance means no runtime suite yet; the required manifest test
  prevents pytest exit 5 without suppressing failures.
- GitHub Actions is enabled and allows GITHUB_TOKEN to create pull requests.
- RELEASE_PAT, when configured, lets release PRs trigger Tests; GITHUB_TOKEN is
  the fallback and does not trigger those runs.
- Match ZIRAN's simple release strategy and conventional commits, without its
  separate publishing pipeline or release-branch gate, which would block feat commits.
- plugin.json starts at 0.1.0; release-please's manifest starts at 0.0.0 because
  nothing is released yet, so the first feat release is 0.1.0. Python packaging
  and its version source are deferred to issue #2.

## Deferred

- `cli/wuwei/` and executable packaging: issue #2.
- Agents, skills, hooks, adapters, charters, templates and full documentation:
  later issues. No placeholder directories are tracked.
- Hosted CI and actual release PR creation require merging and GitHub execution.

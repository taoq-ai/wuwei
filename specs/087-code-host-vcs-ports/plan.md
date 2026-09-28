# Implementation Plan: Code host and VCS ports

**Branch**: `087-code-host-vcs-ports` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing registry and workspace schema. Add plain GitHub, unavailable code host and git modules. Preserve Result and root conventions. Record port parameters alongside operation names in the registry without replacing the existing INTERFACES API. Extend tests/test_adapters.py, including order-independent none imports.

## Technical Context

Python 3.11+, stdlib only; pytest is development-only. External subprocesses use argv lists and fixed timeouts. Git commands always start with git -C repo. GitHub reads use gh api, JSON decoding and explicit error/shape checks. REST collections use pagination with slurped JSON. Thread GraphQL uses the supplied harness field set with completeness checks. Merge uses the issue's exact constrained CLI command. No runtime dependencies, persistent caches or new config knobs.

## Constitution Check

Passed before and after design: shared results, fail-closed reads, test-first batches, existing module discovery, least-privilege writes, no new policy in adapters. No exceptions needed. Tests use in-process replay plus one PATH-stub smoke test per adapter. A local git regression verifies that inherited GIT_DIR cannot redirect the requested repository. No commits, pushes or live gh calls.

## Project Structure

- cli/wuwei/registry.py and workspace.py: declarations and defaults.
- adapters/code_host/github.py and none.py: normalized GitHub operations and unavailable behavior.
- adapters/vcs/git.py: normalized repository operations.
- tests/test_adapters.py and test_stdlib.py: extend existing contracts and boundaries.
- tests/test_code_host.py and test_vcs.py: fixture replay and failure cases.
- tests/fakes/: recording port fakes and shared replay support.
- tests/fixtures/code_host/ and tests/fixtures/vcs/: sanitized replay cassettes.
- contracts/ports.md: parameters, inputs and normalized results.

## Implementation sequence

1. Write and run failing registry, configuration and module contract tests; add declarations, defaults and unavailable module.
2. Write and run GitHub replay, failure and write-safety tests; implement its adapter.
3. Write and run git replay and failure tests; implement its adapter.
4. Write and run fake tests; implement recording fakes. Add boundary scan and its positive detection cases.
5. Run the supplied full pytest command, inspect changes and scan authored files for prohibited characters.

Independent port test batches can be developed separately; this seat executes them sequentially. MVP is read evidence, followed by constrained writes and reusable fakes.

## Verified API details and review

The supplied charter harness established REST PR/review/comment fields and GraphQL thread resolution fields. GitHub's [revert mutation contract](https://docs.github.com/en/graphql/reference/pulls#revertpullrequest) distinguishes the original pullRequest from the newly created revertPullRequest; the adapter returns the latter. The [CLI environment contract](https://cli.github.com/manual/gh_help_environment) permits GH_HOST overrides, so every API call pins github.com to match accepted references.

Independent correctness/security review found host selection and git newline conversion issues. Regression tests reproduced both before fixes. Git output now decodes captured bytes without universal newline conversion; all API fixture steps assert the pinned host. Delta review reported no remaining blockers.

# Tasks: 104 integrity

## Setup
- [X] T001 Read design and existing ports, hooks, protection and promotion code; write specs/104-integrity/spec.md and plan.md.

## US1: Release verification and guards
- [X] T002 [US1] Add failing signature, inventory, missing-tool and port tests in tests/test_integrity.py and tests/test_adapters.py.
- [X] T003 [US1] Implement adapters/integrity and cli/wuwei/integrity.py verification and inventory.
- [X] T004 [US1] Add failing cached verdict, hook scope, confirmation and protected-state tests in tests/test_integrity.py.
- [X] T005 [US1] Implement cli/wuwei/commands/integrity.py, hook/sweep integration and producer-only protection.

## US2: Workspace history
- [X] T006 [US2] Add failing workspace history and promotion tests in tests/test_integrity.py and tests/test_adapters.py.
- [X] T007 [US2] Extend adapters/vcs, init and promotion to initialize, inspect and commit workspace history.

## US3: Release packaging
- [X] T008 [US3] Add failing package inventory coverage test in tests/test_integrity.py.
- [X] T009 [US3] Add release packaging/signing CI and docs/integrity.md with owner setup.

## Validation
- [X] T010 Run full pytest suite, review security boundaries, scan changed files for forbidden characters and local paths, and record results here.
- [X] T011 Reproduce main's ten integration failures, add both integrity guard mutation probes and seed the harmless-command shim fixture.
- [X] T012 Reproduce unnecessary SSH execution and unrelated reconfirm refusals; remove the redundant subprocess and require an integrity mention.
- [ ] T013 Rebase onto main. Blocked by the sandbox's read-only Git metadata; validate the combined tree in a temporary copy instead.
- [X] T014 Validate the combined tree against main 9025a30 in a temporary copy, preserving both sides of the protected-state overlap.

## Dependencies and execution
T002 before T003; T004 before T005; T006 before T007; T008 before T009.
Run sequentially because integrations share registry and integrity core.

## Validation evidence
Signature/inventory tests failed on the absent core and port, then passed. Cache,
confirmation and producer-protection tests failed before integration, then passed.
Workspace history/init/promotion tests failed before extending the VCS port, then
passed. Packaging coverage failed before adding the release builder, then passed.
Security regressions were reproduced before fixes: quoted confirmation commands,
stale clean caches, prior hand edits absorbed by promotion, parent repository
fallback, dishonest sweep summaries, missing SSH with an invalid pin, and a
non-seekable host terminal. Dedicated regressions now pass.

Existing policy fixtures explicitly seed measured integrity or use fakes so their
assertions continue to exercise their own guards and sweep policies. No runtime
bypass was added for tests or unsigned source checkouts.

Original full-suite result: 4383 passed, 3 skipped in 51.67s. The three existing
load-sensitive performance checks skipped on this busy host; the dedicated cached
integrity latency test passed. Git diff whitespace checks and scans for em dashes,
emojis and machine-local paths passed. All changes remain in the working tree.

Review fixes: main's mutation and harmless-command tests first reproduced all ten
reported failures, then passed (38 passed). Five new cases reproduced both small
findings before their fixes. The targeted integrity, mutation and state-protection
suite passed (563 passed). The requested full worktree command passed:
4426 passed, 3 skipped in 51.23s. The skips are the existing load-sensitive checks.

The branch remains at 65e7231; main was 9025a30 during this fix round.
`git rebase --autostash main` failed with `could not write index` and
`Cannot autostash`. Main's two relevant test files were brought into this working
tree so the regression fixes are reviewable here. During the eventual rebase,
retain both the integrity/.git protection and main's memory/goals.md protection
in protect_state.py, and retain the seeded shim fixture.

The temporary main overlay passed: 4505 passed, 3 skipped in 50.05s. Its shell
PATH used the same Python environment as the requested interpreter, and it had
temporary Git metadata for repository-dependent tests. No commits were created.

Deferred owner steps: replace keys/manifest-signing-key.pub with the real public
key, provision WUWEI_MANIFEST_SIGNING_KEY, and verify the signed release artifact.
CI itself was not run. Existing workspace history requires owner review before
initialization; hard owner identity remains external control-plane/OS isolation work.

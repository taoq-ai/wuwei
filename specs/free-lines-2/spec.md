# Feature Specification: the test-only replay helper leaves the runtime and two cache copies fold into evidence._cached

**Feature branch**: `claude/free-lines-2`
**Item**: free-lines-2, tier full, goal G-2
**Input**: `cli/wuwei` holds 2,996 of 3,000 lines on main 8ea4192, so draft-raise (the fix for
bug #1074) cannot land.

## The promise in my words

Four edits free 34 runtime lines and change no behaviour:

1. `replay.replay(directory, scratch, monkeypatch)` has no runtime caller and takes pytest's
   monkeypatch. It moves into `tests/test_replay.py` as the module helper `replay_case`, and
   `replay.py` drops its now unused `import datetime`. `replay.record` and
   `wuwei evidence --record DIR` stay as they are.
2. `board._list` is `evidence._cached` with `max_age=TTL`. Its one caller calls `evidence._cached`
   with the same cache name and `TTL`.
3. `evidence.items_named` has one caller, `board.names`, which reads
   `evidence.ITEM.findall(pr.get('body') or '')` in place.
4. `guards._default` reads through `evidence._cached` with the same cache name
   (`default-<owner>__<repo>`) and the same 86,400 s age. It still answers `{'main', 'master'}` with
   no repository and on `gh.GhError`, and caches nothing on an error.

The runtime drops from 2,996 to 2,962 lines. No CLI flag, output, replay case format or guard
route changes. The larger option (moving all of `replay.py` and `--record` into `scripts/`) is
out: it removes a documented CLI flag, a breaking change the owner has not approved.

The acceptance scenarios, restated:

1. After the change the runtime is 2,962 lines or fewer and the whole suite passes, the
   vendored-drift test included after re-vendoring.
2. The recorded case `tests/replay/standard-pr-with-owner-paths` still gives its recorded gaps
   through the test-module helper, and record-then-replay round trips.
3. No module under `cli/wuwei` defines `replay(`, `_list(` or `items_named(`, and
   `wuwei evidence --record DIR` still writes `DIR/case.json`.
4. When the default-branch lookup raises `GhError`, `git push origin main` is refused as on main.
   With `trunk` cached as the default branch, `git push origin trunk` is refused with no gh call.
5. A PR body naming `WUWEI-Item: X-1` and `WUWEI-Item: X-2` links the PR to both items.

## Clarifications

### Session 2026-10-16

- Q: Does `evidence._cached` keep the old `_default` behaviour on a lookup error? A: Yes.
  `_cached` calls `ws.cache_put` only after `read()` returns, so a `GhError` escapes before
  anything is written; `_default` catches it and answers `{'main', 'master'}`. A new test pins
  that the cache stays empty.
- Q: Does the board TTL survive the fold? A: Yes. `_cached` takes `max_age` and the caller passes
  `TTL` (60 s), the same age `_list` used.
- Q: Should the helper keep the name `replay`? A: No. In the test module it would shadow the
  imported `replay` module, which `record` is still called through. It is named `replay_case`.
- Q: Is acceptance 5 already pinned? A: Yes, by
  `tests/test_watch.py::test_a_pr_naming_two_items_links_both_and_closes_both_once_merged` (items
  A and B). No new test is needed; a mutant that keeps only the first named item fails it.
- Q: Should the size budget test tighten to 2,962? A: No. The freed lines are room for
  draft-raise. Acceptance 1 is held by the existing 3,000 budget test and the line count at the head.

## User scenarios

### US1: the runtime has room for draft-raise (P1)

Acceptance 1 and 3. Tests: `tests/test_setup.py::test_the_runtime_holds_its_size_budget`,
the vendored-drift test, `tests/test_replay.py::test_no_runtime_module_defines_the_moved_or_folded_helpers`,
`tests/test_replay.py::test_evidence_record_writes_the_case`.

### US2: recorded cases still replay (P1)

Acceptance 2. Tests: `tests/test_replay.py::test_a_recorded_case_gives_the_same_gaps`,
`tests/test_replay.py::test_record_then_replay_round_trips`.

### US3: the push door reads the default branch as before (P1)

Acceptance 4. Tests:
`tests/test_guards.py::test_a_push_to_main_is_refused_when_the_default_branch_lookup_fails_and_nothing_is_cached`,
`tests/test_guards.py::test_a_cached_default_branch_refuses_its_push_with_no_gh_call`, and every
route in `tests/fixtures/routes.json`.

### US4: a PR naming two items links both (P2)

Acceptance 5. Test: `tests/test_watch.py::test_a_pr_naming_two_items_links_both_and_closes_both_once_merged`.

## Requirements

- FR-001: `cli/wuwei/replay.py` defines `record` only; `tests/test_replay.py` defines `replay_case`
  with the body of the old `replay.replay`.
- FR-002: `board.py` has no `_list`; `compute` reads open PRs through `evidence._cached(..., TTL)`.
- FR-003: `evidence.py` has no `items_named`; `board.names` uses `evidence.ITEM.findall`.
- FR-004: `guards._default` uses `evidence._cached` with the same cache name and age, the same
  fallback, and caches nothing on `GhError`.
- FR-005: `.claude/wuwei/cli/wuwei/` is rewritten by `setup.vendor('.')`.
- FR-006: No CLI flag, output, config key or replay case format changes.

## How this fails

1. The push door stops refusing pushes to the default branch when the lookup fails, because the
   fold lets `GhError` escape or caches a wrong value. Guarded: a test makes the lookup raise and
   checks the deny and the empty cache; a mutant that returns an empty set on error is killed.
2. `_default` reads a different cache name, so a cached default branch is ignored and every push
   makes a gh call, or a cached `trunk` is no longer protected. Guarded: a test caches `trunk`
   under the old name and checks the deny with `fake.calls == []`; a renamed-cache mutant is killed.
3. The board loses its 60 s TTL and either hammers the code host or shows PRs a day stale.
   Guarded by passing `TTL` explicitly; the existing board tests that reset `prs-acme__app` still
   pass. Residual: no test measures the age itself; the diff shows the argument.

## Assumptions

- Tier full because `guards.py` is door code, as for free-lines. Overturned if the owner rates a
  behaviour-neutral change in `guards.py` as standard.
- `replay_case` as the helper name. Why: avoids shadowing the `replay` module in the test file.
  Overturned by a reviewer preferring another name; cheap to change.

## Success criteria

- SC-001: The suite passes at the head.
- SC-002: `cli/wuwei/` holds 2,962 lines.

## Rollback

Revert the commit. No data, config or CLI changes; the cache names and ages are unchanged.

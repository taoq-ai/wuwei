# Implementation Plan: Adopt Existing Starts

**Branch**: `950-start-adopts` | **Spec**: `specs/950-start-adopts/spec.md`

## Technical Context

Python 3.11 stdlib runtime. `derive.offers` is the shared planned-item decision used by `next` and the parallel launch set. The PR listing, day events and Git worktree registry supply evidence without subprocesses on the hook-safe path. `dispatch.launch_set` refreshes repositories of imminent planned starts whose cached read is due. `next.run` keeps its existing recorded-PR polling.

## Constitution Check

Use existing readers and item states. Write the regression tests first. Reuse the Owner step card format. No new module or adapter. The design spec remains owner-only.

## Design

1. Read events once per `derive.offers` call. Resolve an item's repository using the proposal with the same damaged-record tolerance as dependency lookup. Check ad-hoc links even when no repository resolves.
2. Match open PRs by branch final segment, case-insensitively, only when that repository's cached read is fresh. A stale cached PR row cannot suppress an imminent start before `dispatch.launch_set` refreshes it. Skip a failed repository listing, leaving a note on any offered start. Discover worktrees through `.git/worktrees/*/gitdir`, use the item's `worktree.created` start, its first `logs/HEAD` creation commit, or the readable remote default branch ref, and skip commit detection for a WUWEI builder brief or build record.
3. Give each held evidence row one Owner step card with the exact reconcile or park command. Check combined PR and worktree, worktree, then seat evidence. A No answer suppresses only that candidate and exposes the next one. Include both PR and worktree in one reconcile command when both are found. Quote worktree paths and name the ad-hoc seat in park commands.
4. Register case-sensitive ad-hoc item links from Agent name, description, or explicit `Item:` and `Item X.` lines only for WUWEI or recorded builder and spec roles. Keep the unbriefed-seat refusal's prompt prose lookup in both guard modes.

## Tests

Focused red tests cover the reported field case, remote default branch ahead of the main checkout, registered worktree paths, failed listings, exact item boundaries, ad-hoc links and event reads. Run every test file importing changed modules plus `tests/test_signal_status.py` with explicit file arguments.

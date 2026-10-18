# Feature Specification: the PR standard says the PR opens as a draft and the shepherd requests the reviewer

**Feature branch**: `docs/pr-draft-text`
**Item**: pr-draft-text, tier full, goal G-2, issue #1132
**Input**: the PR standard note (`charters/_pr.md`), which a seat sees once per session before
`gh pr create`, said the gates passed before the PR opened and told the body writer to request a
reviewer. The builder charter says the opposite: open a draft, never request reviewers, and the PR
turns ready once the gates pass at the draft head.

## The promise in my words

Charter and test text only. Runtime lines: 0 (2,976 before and after, `wc -l cli/wuwei/*.py`).

The closing paragraph of `charters/_pr.md` (lines 20 to 22) now says four things: the PR opens as
a draft so CI runs; the gates the diff needs read the draft head; it turns ready once they pass,
and the shepherd requests the reviewer then; before merge CI is green and every review thread is
answered. It no longer tells the body writer to request a reviewer, and it no longer says the
gates passed before the PR opened. The vendored copy `.claude/wuwei/charters/_pr.md` matches.
`guards.PR_STANDARD` reads the plugin's `_pr.md`; no generated agent includes it, so `agents/` do
not change.

Outside: `charters/shepherd.md`, which already says this; runtime code; the PR body template above
the paragraph.

The acceptance scenarios, restated:

1. Given the head, when `guards.bash` reads `gh pr create --draft` for the first time in a session,
   then the note it returns says the PR opens as a draft, and nowhere says "Request a reviewer".
2. Given the suite at the head, when it runs, then the test that holds `.claude/` to the tree
   (`test_the_vendored_plugin_matches_the_tree_it_was_copied_from`) passes.

## How this fails

1. A seat working alone (no shepherd in the session) reads that the shepherd requests the reviewer
   and leaves the ready PR with none. Held: a requested reviewer is process fit and never holds a
   merge (`_common.md` Done); the planner runs the shepherd, whose step 2 requests reviewers after
   the flip to ready.
2. A non-draft `gh pr create` that `create_door` lets through at a gated head shows the same note,
   which says the PR opens as a draft, and the seat closes and reopens it as a draft. Held in part:
   the note is the standard, shown once per session as advice, not a refusal; the create already
   succeeded. The builder and shepherd charters name the draft route as the normal path.
3. The vendored copy lags the tree and cloud sessions keep showing the old text with "Request a
   reviewer". Held: `setup.vendor('.')` re-ran and the drift test fails on any difference; the new
   guard test reads the plugin's own `_pr.md`, so a stale charter fails it too.

## Clarifications

### Session 2026-10-18

- Q: The promise lists four things the paragraph says; the old paragraph also ended with "A delta
  after review fixes is re-read when it needs it." Keep it? A: Keep it. It agrees with `_common.md`
  Done and the builder charter, and the promise does not name it for removal. Recorded under
  Assumptions.
- Q: Which words does the test hold? A: Three whole sentences, matched after whitespace is
  collapsed, so a negation ("does not open as a draft") or a dropped clause ("and the shepherd
  requests the reviewer then") fails it, not only a missing word. It also refuses "request a
  reviewer" in any case and the old "before it opened".
- Q: Are the terms new? A: No. "draft head" and "turns ready" are the builder charter's words
  (`charters/builder.md:70-73`); "requests reviewers" after the flip is `charters/shepherd.md:14-19`
  (read with `grep -n "draft\|ready\|reviewer" charters/shepherd.md charters/builder.md`).
- Q: Does open PR #1138 (models-table) conflict? A: No shared file. Its diff
  (`git diff --name-only origin/main...origin/pr-1138`) touches `planner.md`, `steward.md`,
  `agents/steward.md`, docs and `tests/test_charters.py`; this item touches `_pr.md`, its vendored
  copy, `tests/test_guards.py` and this spec.

## User Scenarios & Testing

### US1: the PR standard note matches the draft route (P1)

Acceptance 1. `tests/test_guards.py::test_the_pr_standard_note_opens_a_draft_and_leaves_the_reviewer_to_the_shepherd`
reads `gh pr create --draft` through `guards.bash` in a fresh session, holds the three sentences,
refuses "request a reviewer" and "before it opened", and checks the note is not shown a second time
in the same session.

Red first, against the old charter (`pytest -q tests/test_guards.py -k pr_standard_note`):
`1 failed, 1 passed, 1192 deselected`, failing on the first sentence. Green after the edit:
`2 passed, 1192 deselected`.

### US2: the vendored copy matches (P1)

Acceptance 2. `tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from`
passes at the head after `setup.vendor('.')`. The existing
`test_the_pr_standard_note_is_the_charter_with_the_plugin_version` still holds the note to the
charter byte for byte.

## Requirements

- FR-001: `charters/_pr.md` lines 20 to 22 say the PR opens as a draft so CI runs, the gates read
  the draft head, it turns ready once they pass and the shepherd requests the reviewer then, and
  before merge CI is green and every review thread is answered.
- FR-002: the paragraph no longer says "Request a reviewer" or that the gates passed before the PR
  opened.
- FR-003: `.claude/wuwei/charters/_pr.md` matches `charters/_pr.md`; `agents/` unchanged
  (`bin/wuwei agents build` reports "agents match the charters").
- FR-004: a guard test holds FR-001 and FR-002 against negation and clause removal.

## Assumptions

- The delta sentence stays: it is true and the promise does not ask to remove it. Overturned if the
  owner wants the paragraph cut to the four named points.
- The same note serves a non-draft create at a gated head; the standard describes the normal route,
  not every route the guard allows. Overturned if seats reopen ready PRs as drafts because of it.

## Rollback

Rollback: revert the commit, then run `setup.vendor('.')`. Charter, test and spec text only; no
runtime, config, ledger or file format change.

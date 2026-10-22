# Feature Specification: a base merge into an open PR is measured on the PR's own diff

**Feature branch**: `leone/1230`
**Item**: 1230 (taoq-ai/wuwei#1230), tier full, goal G-2
**Input**: the owner, 2026-10-22: "WUWEI counts a merge of main as that kind of change. It compares the
old head to the new head, so everything main gained since then counts too." `evidence.gate_gaps`
measured the delta after a pass as `compare(last gated head, head)`. On A-Teams-Network/ai-stacks,
#3374, #3377 and #3523 (all approved) each waited 2 to 12 seat-minutes for a delta gate that found
only renumbers.

## The promise in my words

After a gate passes, the code it has not read is the change in the PR's own diff: the PR's diff
against its base at the gated head, set beside its diff against its base at the new head, file by
file. A file whose patch is the same at both heads (hunk line numbers and headings aside) is not in
the delta, whatever a merge of the base brought into the branch. A file whose patch moved is
measured as before (its lines in the head-to-head compare, or its own diff when that compare does
not list it). Over 20 such non-prose lines, or a risky path, owes the one gate `wuwei evidence`
names. Files the workspace declares generated are left out of the delta.

The acceptance scenarios, restated:

1. A PR has every gate passed; main is merged in and the PR's own diff does not change. `wuwei
   evidence` shows no owed gate, and the merge door lets `gh pr merge` through.
2. A main merge whose conflict resolution adds 30 code lines to the PR's own diff owes the gate
   `wuwei evidence` names (quality for a plain path, security for a risky one).
3. A main merge that changes, in the PR's own diff, only files a dated `Generated` line of
   `.wuwei/standards.md` declares for the repository carries the passes.

Outside: a rebase or force push (the passes then sit on no ancestor of the head, as today); the
gates' own reading of a delta.

## How this fails

1. GitHub's PR `base.sha` is older than the main commit merged into the head. The three-dot
   compare from it then reads main's commits between them as the PR's own diff, so a re-read is
   owed that the PR did not need. This fails safe (today's behaviour). Read on 2026-10-22: on four
   open taoq-ai/wuwei PRs, `base.sha` was the base tip at the PR's last push, at or after the merge
   base (`gh api repos/taoq-ai/wuwei/pulls/<n>` against `compare/main...<head>`).
2. A merge commit moves a PR hunk to a place with the same three context lines on each side. The
   patch, line numbers aside, reads the same, so the move carries. A move with other context is
   caught (the "moves 12 PR lines" test, the probe's classes). A hunk moved between identical
   contexts stays a residual risk.
3. A `Generated` line names a hand-written file (a contract, a risky path). A hand edit to it after
   a pass then carries. The line is the owner's, dated, in the workspace standards that the
   steward's 30-day rule reviews; the generator's own inputs are still measured.

## Clarifications

- Q: Which base? A: in `wuwei evidence` and the merge door, the PR's `base.sha` from the REST PR
  read (the base tip at the PR's last push). At the create and ready doors, the compare's
  `merge_base_commit`. Both are shas, so each compare is cached a day (`evidence.compare`), and the
  board adds no uncached host call (#1191).
- Q: What is "the same patch"? A: the patch GitHub's compare gives per file, with each `@@` line
  reduced to `@@`. Context lines stay, so main's edit within three lines of a PR hunk moves the
  file (it fails safe: the file is measured as before).
- Q: A file with no patch (binary, or too long for GitHub)? A: it moves.
- Q: GitHub's compare lists at most 300 files. A: when either own diff reaches 300 files, the
  delta is the head-to-head compare, as today.
- Q: How many lines does a moved file count? A: its lines in the head-to-head compare, as today,
  so main's lines in that file count too (safe). A moved file that compare does not list (a merge
  that reverts main's change) counts its own diff at the head, or at the gated head when gone.
- Q: Where is "generated" declared, with no new config key? A: a dated standards line,
  `- Generated (<owner/repo>, <YYYY-MM-DD>): <glob> <glob>`, in `.wuwei/standards.md`, matched
  case-insensitively on the repository; globs split on spaces, commas and backticks and match with
  `fnmatch`, as `owner_paths` do. Chosen over `.gitattributes` `linguist-generated`, which would
  need a host read per head and a parser.

## Requirements

- FR-001: with a base sha, the delta after a pass is the files whose own patch moved between the
  gated head and the head; files whose patch did not move are out.
- FR-002: a moved file counts its head-to-head lines; one missing there counts its own diff.
- FR-003: a file with no patch moves; an own diff at 300 files falls back to the head-to-head
  compare; with no base sha the delta is the head-to-head compare.
- FR-004: files a dated `Generated (<repo>, <date>):` standards line names are out of the delta.
- FR-005: `wuwei evidence`, the merge door, and the create and ready doors read the same delta.
- FR-006: the gate owed, and the 20-line and risky-path rules, are unchanged.

## Assumptions

- The `Generated` standards line, not `.gitattributes`: no host read, three lines of runtime. A
  team that wants `linguist-generated` read would overturn it.
- `base.sha` from the PR read is at or after the merge base (read on four PRs). A host that keeps
  it at the PR's creation would overturn it; the result is then today's behaviour, not a miss.
- Patches are kept in the compare cache (a day per sha pair). A workspace whose cache grows too
  large would overturn it.

## Rollback

Revert the squashed commit. The delta is again the head-to-head compare; no data, config or
ledger format changes, and cached compares with patches still read.

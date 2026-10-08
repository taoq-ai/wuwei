---
version: 1.0.1
---
# Shepherd charter

Read `_common.md` and `_common-authoring.md` before PR work. Own PR raise, reviewer requests, thread replies and the obligation ledger. Use the configured repository, owner, review bot and chat adapters.

## PR raise

1. Verify required pre-PR verdicts pass at the current head, required tests ran, and every PR body claim has current evidence. Put residual non-blocking findings in review notes. Refresh the open-PR collision survey.
2. Raise the PR through the configured adapter. Select reviewers from changed source files, excluding lockfiles, specs and generated files, then rank authors over the past 90 days and choose the top two, excluding the PR author and bots. If fewer than two remain, widen to 180 days, then to all time. Verify each reviewer's login before first use. Honor repository review policy and request the same people named in any review request message. Pass outward-text lint before posting.
3. Record each sent request and reply id. Recheck live PR obligations immediately. A failed post remains owed; do not record a draft as sent.

## Review and merge

1. Follow gate step zero in `_common.md` for CI checks and test tiers, then read review summaries, PR comments, inline threads and configured chat replies. Rebuild obligations from the full current PR state; a watcher delta only wakes the check. Read each thread's last word before replying.
2. Classify each finding against the item promise using `_common.md`. Fix blocking regressions within the cycle budget, answer every owed thread with evidence, and refresh checks at the new head. Do not claim an unpushed fix is present.
3. Before merge, read every review body and PR comment for pre-merge conditions; "before X" blocks until X is met. Count each reviewer's latest review separately. An approval covers its `commit_id` only; compare it with the current head. Never run `wuwei merge` while a fix round is in flight or a reply promises one. Merge only through `wuwei merge <pr>` when `wuwei merge check <pr>` clears the fresh head under the configured repository policy. If it does not clear, route the merge to the owner with the decision record and the failed precondition. Write that record with `Question: Merge <owner>/<repo>#<number>?` and one option whose description starts with `Merge`, so the retro can count merges the owner decided against the policy. Follow `_common.md` for approval, deployment and overrides.
4. After merge, track base-branch checks and report a red check for the configured revert and breaker path. Close only after thread, review and outward obligations are answered and the merge evidence is recorded.

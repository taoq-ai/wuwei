# Shepherd charter

You own open PRs until they merge or the owner parks them.

## Raise

1. A pushed branch opens as a draft PR (the builder opens it; open it yourself when it has none):
   `gh pr create --draft`. In a cloud session `gh pr create` fails because it needs GraphQL, so open
   it by REST:
   `gh api -X POST repos/<owner>/<repo>/pulls -f head=<branch> -f base=<base> -f title=<title> -F body=@<file> -F draft=true`.
   A PR that is not a draft waits for its gates (WUWEI refuses it and names what is missing).
   The body says what changed and why, the assumptions, the tests, and review notes for residual
   non-blocking findings, and ends with the WUWEI footer naming its item.
2. Once CI is green and the gates the diff needs passed at the draft head, mark it ready with
   `gh pr ready <n>` (in a cloud session `gh api -X POST repos/<owner>/<repo>/pulls/<n>/ccr/ready_for_review`).
   WUWEI refuses the flip and reviewer requests on a draft before. Then request reviewers: the top
   two authors of the changed source files over the past 90 days (widen to 180 days, then all
   time), excluding the PR author and bots. In a cloud session:
   `gh api -X POST repos/<owner>/<repo>/pulls/<n>/requested_reviewers -f 'reviewers[]=<login>'`.
   Honour the repository's review rules.
3. Ask for review where the team asks (the `Review requests:` line in `.wuwei/standards.md`): one
   post with the PR link once it is ready, not a draft. A post made outside the session is recorded
   with `wuwei sent owner/repo#n <link>`, never posted twice.
4. A PR raised by hand, without a plan link, is yours too: the board lists it as `unplanned`.

## Follow

The watch pass (`/wuwei-watch`) is when you follow: no PR waits for the owner to ask.

1. Read the PR once per event: CI, conflicts, reviews, threads. Rebuild what is owed from the
   current PR state, not from memory.
2. For each unanswered thread: a fix request inside the item's promise becomes a fix for the
   builder; a question gets an answer with evidence; a request outside the promise is a scope
   change for the owner. Never claim an unpushed fix is present.
3. A red check that also fails on the base branch is the base's: say so on the PR once and wait.
   Any other red check is this PR's to fix.
4. A PR open three days or more is stale: finish it, rebase it or close it with a reason.
5. A conflict: merge the base into the branch and resolve; never rewrite published history.

## Merge

A breaking change merges only with its evidence: an `Announcement: <url>` line, then the owner's
confirmation at the head. The line holds one http(s) URL and nothing else. The client communication
must exist at the head: a PR or issue comment, or a release note or migration guide already
published. A changelog entry the release will write later does not count. Ask once the
announcement exists: `breaking: owner/repo#n at <sha7>: <what breaks>. Announced at
<link>. Proceed?`.

1. Merge with `gh pr merge <number> --squash` (or the repository's method) when the board shows no
   safety gaps, in the order that keeps the base green. Where GraphQL is refused (Claude Code cloud
   sessions), merge with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/merge -f merge_method=squash`.
   While only CI is still running, arm auto-merge (`gh pr merge <n> --auto`) instead of waiting.
   WUWEI refuses a merge only on safety gaps and lists them; process fit never holds a merge.
   Merging and its order are yours, never an owner question.
2. Before merging, add a short evidence comment to the PR: the gates and the head they passed, CI,
   threads, and any exception the owner accepted. The audit then lives next to the code.
3. After the merge, watch the base branch's checks once; a red base after your merge is a revert
   PR and a note to the owner.

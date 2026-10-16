Verdict: PASS
Gate: security
Item: draft-raise
PR: taoq-ai/wuwei
Head: d485ba8e186600331d864dccf7e37db02fb3e210
Confidence: high

## Findings
- [low] blocks: no. My 02be6b9 blocking finding is closed. The routes on lines 32 and 33 use `[^/0-9]*([0-9]+)[^/]*`, so `pulls/7٣/requested_reviewers`, `7%D9%A3` and `7%EF%BC%97/ccr/ready_for_review` now reach the ready door for PR 7 (the PR GitHub reads), even with older PRs 73 and 77 that are not drafts present. `pulls/5%D9%A3/merge` checks PR 5's evidence, where it checked PR 53 at 02be6b9.
- [low] blocks: no. The line-163 note is closed. `gh pr ready ５`, `gh pr ready ７`, `gh pr ready 7٣`, `gh pr edit ５ --add-reviewer bob` and `gh pr merge ７` now get "name the PR by number or URL", which fails closed. gh reads these words as branch names (real5.sh: `headRefName: "５"`), so no PR is checked in place of another. The PR URL takes `pull/([0-9]+)`, and an MCP pullNumber string needs ASCII digits (line 363).
- [low] blocks: no. In the sweep of guards.py, no PR, number or id input still parses non-ASCII digits. Line 216's `int(m[2])` reads the ASCII route group. The remaining `\d` on lines 344 and 349 shape-check owner questions, not a door. Outside guards.py and this item, evidence.py:52, hook.py:249 and 281, and verdict.py:45 still use `\d`. A classed owner question naming `#７` would be recorded for PR 7, as the owner reads it, so this is a consistency note for a later item.
- [low] blocks: no. Carried unchanged from earlier rounds: the `--input` draft trusts the hook's cwd and assumes the file is not rewritten between the hook and gh; `repositories/<id>/...` paths (refused by this session's proxy, served by github.com directly); `gh api graphql --input` carrying markPullRequestReadyForReview; a `?draft=false` query beside a draft body is unmeasured; `--auto` and `--admin` are read from raw argv; the fork head is compared by branch name.

## Probes
Corpus (probe/test_sec_draft.py with cmds1.txt to cmds4.txt, 218 commands and 19 MCP payloads, with older PRs 53, 73 and 77 that are not drafts, draft PR 7 with no gates and ready PR 5) run through archive copies of main 034d067, 02be6b9 and d485ba8. The only moves from 02be6b9 to d485ba8 are the six Unicode-digit routes going from pass to a door. Nothing moved from a door to pass, and every earlier closure still holds (dot segments, wrapped or expanded `--input`, the brace and backtick forms, the ASCII lenient numbers, flag-value PR words, `--repo=`).
probe/real5.sh, real gh 2.89.0 against the local logging server: gh reads `７` and `7٣` as branch names (`headRefName`) and sends a raw `7٣` path as `7%D9%A3`. The head guard now agrees with both.
Mutants (probe/mutate5.py, 5): all killed. They put `\d` back in the merge route, the ready route and the URL, and drop `isascii()` on the argv and MCP number checks.
Suite at d485ba8 in an archive copy: 930 passed, 2 skipped. Runtime is 3,000 lines, and the vendored guards.py is identical (cmp).
Confidence is high because every finding from rounds 1 to 4 was re-run against this head with the real gh binary and the corpus, and all moved to their doors.

## Residual risk
GitHub's POST routing of lenient and escaped path forms is inferred from measured GETs. The `--input` draft relies on the hook seeing the shell's cwd and an unchanged file. Neither is measured.

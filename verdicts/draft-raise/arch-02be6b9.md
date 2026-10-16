Verdict: PASS
Gate: arch
Item: draft-raise
PR: taoq-ai/wuwei
Head: 02be6b9d05864d882c0e21f0c7a5b5fbef2e0bed
Confidence: high
Breaking: yes: on a draft PR, gh pr ready, POST pulls/<n>/ccr/ready_for_review, MCP update_pull_request with draft false or reviewers, request_copilot_review, gh pr edit --add-reviewer and POST pulls/<n>/requested_reviewers wait for the gates; GraphQL markPullRequestReadyForReview and requestReviews and any gh api write through a .. segment are refused; gh api endpoints spelled with //, %xx or . segments, or with characters around the PR number (pulls/5x/merge, pulls/%205/...), meet the doors their plain spelling meets; gh pr merge reads the PR and repository as gh does. All declared in spec.md Breaking and the commits' BREAKING CHANGE lines, with the migration (open as draft, gate, gh pr ready, spell endpoints plainly)

## Findings
- [low] cli/wuwei/guards.py:32 blocks: no. The lenient PR segment also reads segments GitHub does not route (abc7 reads as PR 7, a non-ASCII digit prefix such as %D9%A57 reads as PR 57 because Python's \d and int() accept Unicode digits). Measured: GitHub answers 404 for pulls/abc1096 and pulls/%D9%A51096, so these only hold or check a PR the call never reaches; no input lets a write through.
- [low] cli/wuwei/guards.py:209 blocks: no. The plain-word allowlist holds an --input draft whose other words carry a space or other punctuation (-f title="My PR"); a false hold the refusal explains, recorded in spec.md beside the redirect case.
- [low] cli/wuwei/guards.py:1 blocks: no. The runtime is exactly 3,000 of 3,000 lines (cat cli/wuwei/*.py | wc -l); this round replaced lines in place, and the next runtime change must shed lines first.

## Probes
- git diff f1ca82b 02be6b9: guards.py changes 4 lines in place (two route rows, the alone test); spec, SECURITY.md, the commit text, tests and routes.json follow.
- probe4.py in my scratch folder: pulls/5x/merge, pulls/%205/merge and pulls/5x7/merge reach the merge door as PR 5; abc7 reaches the ready door as PR 7; %D9%A57 reads as PR 57.
- Read-only GETs: gh api repos/taoq-ai/wuwei/pulls/abc1096 and pulls/%D9%A51096 both return 404, so the over-reading cannot act on another PR.
- spec.md Breaking gains the PR-segment "Newly held" line, and commit 02be6b9's BREAKING CHANGE text says the same with the same migration; SECURITY.md describes the allowlist and the leading-digit reading. All three match the code.
- pytest -q in an archive copy at 02be6b9: 918 passed, 2 skipped; cli/wuwei matches the vendored copy (diff -r).
- Confidence high: a small in-place delta, its over-reads measured harmless, and the declaration matches; it would drop if GitHub read a PR number from a spelling the leading-digit rule misses.

## Residual risk
PR-segment spellings were measured only by read-only GETs; writes are assumed to route the same way. No runtime headroom remains.

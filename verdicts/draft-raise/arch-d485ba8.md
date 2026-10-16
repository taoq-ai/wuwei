Verdict: PASS
Gate: arch
Item: draft-raise
PR: taoq-ai/wuwei
Head: d485ba8e186600331d864dccf7e37db02fb3e210
Confidence: high
Breaking: yes: on a draft PR, gh pr ready, POST pulls/<n>/ccr/ready_for_review, MCP update_pull_request with draft false or reviewers, request_copilot_review, gh pr edit --add-reviewer and POST pulls/<n>/requested_reviewers wait for the gates; GraphQL markPullRequestReadyForReview and requestReviews and any gh api write through a .. segment are refused; gh api endpoints spelled with //, %xx or . segments, or with characters around the ASCII PR number (pulls/5x/merge, pulls/5%D9%A3/merge), meet the doors their plain spelling meets; gh pr merge, ready and edit read the PR and repository as gh does and name no PR for a non-ASCII digit. All declared in spec.md Breaking and the commits' BREAKING CHANGE lines, with the migration (open as draft, gate, gh pr ready, spell endpoints plainly, name PRs with ASCII digits)

## Findings
- [low] cli/wuwei/guards.py:1 blocks: no. The runtime stays exactly 3,000 of 3,000 lines (cat cli/wuwei/*.py | wc -l); the fix is in place, and the next runtime change must shed lines first.
- [low] charters/_gate.md:46 blocks: no. The verdict template still says "<owner/repo> alone before the PR opens", as do docs/site/reference.md line 79 and cli/wuwei/verdict.py; still valid, carried from earlier rounds.

## Probes
- git diff 02be6b9 d485ba8 -- cli/wuwei/guards.py: three in-place edits; the ready, reviewer and merge routes and the PR URL match [0-9], and the gh pr and MCP numbers need isascii() and isdigit(). This also covers my round-4 note: a non-ASCII prefix (%D9%A57) now reads as PR 7, and GitHub answers 404 for that spelling, so the door can only over-hold.
- A gh pr ready, merge or edit given a fullwidth digit now names no PR, and ready_door and merge_door refuse with "name the PR"; fails toward holding.
- spec.md Breaking and commit d485ba8's BREAKING CHANGE text both state the ASCII rule with the migration "name PRs with ASCII digits"; they match the code.
- Merge with #1101 (034d067): git diff 034d067 d485ba8 -- skills charters shows only this item's draft-first lines, now in skills/wuwei-rules/SKILL.md and skills/wuwei-watch/SKILL.md; the skills tree matches main (wuwei-close, wuwei-plan, wuwei-rules, wuwei-run, wuwei-watch), and wuwei-run and wuwei-plan carry no gate-order text to update.
- Copies: cli/wuwei, charters and skills match .claude/wuwei/cli/wuwei, .claude/wuwei/charters and .claude/skills (diff -r); the agents drift test passes.
- pytest -q in an archive copy at d485ba8: 930 passed, 2 skipped.
- Confidence high: a small in-place fix that only narrows what counts as a number, a clean merge, and a declaration that matches the code.

## Residual risk
PR-number spellings were measured with read-only GETs, not writes. No runtime headroom remains.

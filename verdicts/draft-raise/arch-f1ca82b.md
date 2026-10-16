Verdict: PASS
Gate: arch
Item: draft-raise
PR: taoq-ai/wuwei
Head: f1ca82b2a9570af2f02f8f4a2a38d6f161a3a73d
Confidence: high
Breaking: yes: on a draft PR, gh pr ready, POST pulls/<n>/ccr/ready_for_review, MCP update_pull_request with draft false or reviewers, request_copilot_review, gh pr edit --add-reviewer and POST pulls/<n>/requested_reviewers wait for the gates; GraphQL markPullRequestReadyForReview and requestReviews and any gh api write through a .. segment are refused; gh api endpoints spelled with //, %xx or . segments meet the doors their plain spelling meets; gh pr merge reads the PR and repository as gh does. All of it is declared in spec.md Breaking and in the commits' BREAKING CHANGE lines, with the migration (open as draft, gate, gh pr ready, spell endpoints plainly)

## Findings
- [low] cli/wuwei/guards.py:1 blocks: no. The runtime is exactly 3,000 of 3,000 lines (cat cli/wuwei/*.py | wc -l). The budget holds, but the next runtime change of any size must shed lines first; queue a free-lines item ahead of it.
- [low] cli/wuwei/guards.py:373 blocks: no. The MCP ready check now uses 'copilot' in tool instead of tool.endswith('copilot_review'), so an MCP server whose name contains copilot sends every update_pull_request to the ready door, holding a plain title edit on a draft until the gates pass. It fails toward holding, never toward passing.
- [low] charters/_gate.md:46 blocks: no. The verdict template and cli/wuwei/verdict.py lines 12 and 49 still say "<owner/repo> alone before the PR opens"; still valid, carried from my first note.

## Probes
- Previous finding (dot segments) closed: probe3.py in my scratch folder shows ./, %2E and %2F spellings normalise to repos/o/r/pulls/7/requested_reviewers and meet the ready door; x/../ and %2E%2E reach the new dots row and are refused for every write method.
- Previous finding (--input behind a wrapper) closed: the alone test now asks for gh as the first shlex word, one segment and no ~ $ * ? [; env -C, env --chdir=, /usr/bin/gh, GH_REPO=... and ~/d.json all read as not alone, so their create meets the create door. shlex.split raising on bad quotes fails closed through hook.handle.
- The dots row sits after the create, merge, ready, push and delete rows. A .. endpoint that fullmatches an earlier row only does so with .. inside the repository capture, where create_door or merge_door then fails to read the repository and refuses.
- Breaking section and commit 25479bf3 now list the normalisation, the .. refusal and the gh pr merge reading, and the migration adds "spell gh api endpoints plainly".
- Merge with #1100 (7f31a51): git diff 7f31a51 f1ca82b shows hook.py and plan.py identical to main, and _gate.md and planner.md differ only by this item's draft-first lines, so both sides are kept. charters/ and .claude/wuwei/charters match, cli/wuwei and the vendored copy match (diff -r), and the agents drift test passes.
- pytest -q in an archive copy at f1ca82b: 901 passed, 2 skipped.
- Confidence high: both earlier blockers are closed and probed on the new code, the declaration matches the behaviour, and the merge is clean; it would drop if GitHub routed a path spelling not covered by //, %xx, . and .. handling.

## Residual risk
Path spellings beyond //, %xx, . and .. (for example a backslash or a case variant of the repository) were not measured. The runtime has no headroom left.

Verdict: PASS
Gate: arch
Item: 1221
PR: taoq-ai/wuwei#1247
Head: f54dda2a37161a911bd0415c16b5e9b7aef9a943
Confidence: high
Breaking: no (minor, feat: the ready door now waits for green CI, which the base shepherd rule 2 already ordered ("Once CI is green and the gates the diff needs passed at the draft head, mark it ready"); merge already needed green CI, so no client gives a new input; an owner exception for the exact printed gap opens it; the release notes name the stricter door)
Supersedes: 1221/arch-ceb9c45.md

## Findings
- [low] cli/wuwei/guards.py:331 blocks: no. On a draft, ready_door reads `gh.pr` and then `evidence.gaps` reads the PR again (threads, required checks, spec artifacts), so a `gh pr ready` costs the merge door's full read plus one more PR read. This is acceptable on a door and keeps one CI reader.
- [low] blocks: no. The plan promise says "while a check fails"; the delta also holds the door while CI runs or has not started, following the owner's issue ("gh pr ready and merge still require green CI at the head"). Whether the promise text should be updated to match is the goal gate's to weigh.

## Probes
- closed: guards.py:330, where the ready door read CI without review contexts, at f54dda2. ready_door (guards.py:329-333) now takes its CI gaps from `evidence.gaps`, the reading the merge door and the board use, so there is one CI reader. Owner exceptions go through the same `excepted` at the end of `evidence.gaps`.
- Delta read: `git diff e1fccf96 f54dda2` (the fix commit; e1fccf96 merges origin/main 8c38073). Runtime changes only guards.py ready_door, 9 lines. The `plan` import and the pre_tool hunk in `ceb9c45..f54dda2` are main's #1239, merged in.
- Re-ran my probe (tests/test_probe_arch.py, the review_gate status on a draft, in a `git archive f54dda2` copy). FAILURE: evidence gives `change request outstanding: Review Gate`, and both `gh pr ready 7` and `gh pr edit 7 --add-reviewer bob` now pass. PENDING and SUCCESS pass. 3 passed.
- Mutants, applied to both runtime copies, one at a time, each in a fresh archive. All 3 were killed:
  - dropping `'required check'` from the CI prefixes: killed by test_a_required_check_not_run_or_unreadable_evidence_holds_the_ready_door.
  - dropping `'evidence unreadable'`: killed by the same test (unreadable evidence fails closed).
  - removing the isDraft early return: killed by test_every_route_reads_as_recorded[gh pr ready 5] and others.
- Targeted tests at the head: test_guards, test_charters and test_watch with `-k "draft or ready or merge or exception or charter or gates or owed or review"` gave 693 passed. The full suite was not run (the builder reports 3,637 passed).
- Charters as the one source: `bin/wuwei agents build` in a copy printed "agents match the charters". The charter text now says `gh pr ready` waits for both the gates and green CI, which agrees with design section 7 and doors.md.
- Runtime budget, measured with `cat cli/wuwei/*.py | wc -l`: head 3,585, main 3,581 (+4), under the 3,800 limit from #1246. Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows none.
- Fail-closed paths match the merge door: `required checks unreadable` and `evidence unreadable` hold the ready door as they hold a merge. The thread reader falls back from GraphQL to the CCR route and then to review comments, so a cloud session is not stuck.
- Confidence high: the closing probe and the three mutants were re-run at this head. What would lower it is a full-suite failure I did not run.

## Residual risk
A flaky or slow check now holds ready as well as merge, which costs one wait per round (named in the spec's How this fails). A host whose branch-protection read is refused keeps drafts shut, as it already keeps merges.

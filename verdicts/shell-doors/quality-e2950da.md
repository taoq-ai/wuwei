Verdict: FIX
Gate: quality
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: e2950da5161b00957693c299082f50c17259480d
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/guards.py:81 blocks: yes. Failure: no test uses a multi-digit file descriptor. Reversing the fd-number drop `[0-9]+(?=[<>])` to a single digit `[0-9](?=[<>])` leaves the suite green. `10>x git push origin main` and `true;12>x git push origin main` then reach segments as argv `['10', 'git', 'push', ...]`, so the program is `10` and the push door never fires, although bash runs the push. Probe: on head segments gives `[['git','push','origin','main'], ['x']]`; with the mutant it gives `[['10','git','push','origin','main'], ['x']]`. Add `10>x git push origin main` and `true;12>x git push origin main` to test_a_push_after_any_redirect_meets_the_push_door.
- [low] cli/wuwei/guards.py:81 blocks: no. The lookbehind `(?<![^\s;&|()<>])` of the fd-number drop has no test (surviving mutant: removing it). Without it a digit ending a word, as in `git push origin ma2>x`, is stripped to `ma`. The branch is misread, which fails open for a word whose digits hide nothing, but a pass row such as `echo a2>x` would pin it.

## Probes
- Suite at head: `pytest -q` gave 1157 passed, 2 skipped. cli/wuwei/guards.py and .claude/wuwei/cli/wuwei/guards.py are identical. Runtime is 2998 lines (`cat cli/wuwei/*.py | wc -l`).
- Mutants on the changed and new clauses, each applied to both the cli and vendored copies and run against the full suite (34 run):
  - Killed: the fd drop removed entirely; the fd lookbehind narrowed to whitespace only; the fd lookahead removed; the UNREAD marker off or always on.
  - Killed: each of the redirect tuple entries `&>>`, `<`, `<>`, `>&`, `<&`, `<<<` and `>|`; `>>` in OPS.
  - Killed: the ledger `(\.?/)*` in the middle, on the children and on the tail (three variants); `=` on the first alternative and on the children; the start anchor; `.jsonl`; the bare `.wuwei`; the `ledger/` children.
  - Killed: the DOOR_WORDS `[/.]*` (three variants), the lookahead characters (`-`, `.`, `/`, `\w`) and the `/ledger` alternative.
  - Survivors, re-run in fresh copies: the single-digit fd mutant (blocking, above) and the removed fd lookbehind (note).
- Prior findings are closed. `dd of=.wuwei/ledger/x` now has a test and its `=` mutant is killed. `rm foo.wuwei`, `ls .wuwei-old\nls` and `\$'main'` have cases and their mutants are killed.
- Simplicity: none to delete. `OPS` `&&`, `\|\|`, `;;`, `\|&` and `&>` are still equivalent to the single-character fallback, as noted at 67b367a, but the comment now says longest first, so it only costs length.

## Residual risk
The behaviour is correct on every probe. The one blocking item is a missing multi-digit fd test, a one-line addition. I did not re-run the stub-git acceptance under bash at this head.

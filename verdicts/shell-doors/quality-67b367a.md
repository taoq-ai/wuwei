Verdict: FIX
Gate: quality
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: 67b367ae51e6d4c111b50aa3b74d8df270130b1e
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/guards.py:31 blocks: yes. Failure: the `=` prefix on the ledger-children alternative (`(^|[/=])\.wuwei/ledger/`) has no test. Reversing it to `(^|/)` leaves the whole suite green, and `dd of=.wuwei/ledger/x` (argv word `of=.wuwei/ledger/x`, checked at guards.py:314) then passes as no ledger write, so a ledger child file can be overwritten. Add `dd of=.wuwei/ledger/x` to test_a_ledger_path_without_a_trailing_slash_is_a_ledger_write; the vendored copy then stays in step.
- [low] cli/wuwei/guards.py:31 blocks: no. Surviving mutant: dropping `(^|[/=])` from the first alternative (bare `.wuwei...$`, unanchored at the start) survives. It only over-refuses a path like `rm foo.wuwei`; add a pass row for it.
- [low] cli/wuwei/guards.py:28 blocks: no. Surviving mutant: the `-` in the DOOR_WORDS lookahead `(?![\w./-])` is untested; a multi-line command naming `.wuwei-x` is refused falsely. Add a case to the multi-line tests.
- [low] cli/wuwei/guards.py:86 blocks: no. Surviving mutant: removing the `\\[\s\S]` alternative from the `$'` check survives. A command like `git push origin \$'main'` (an escaped dollar) is then refused as unreadable instead of passing. That is a false refusal on a door command and no bypass, so it fails closed. Add a case.
- [low] cli/wuwei/guards.py:17 blocks: no. Surviving mutants: dropping `&&`, `|&` or `&>` from OPS survives. They are equivalent, because the `[();<>|&]` fallback yields the same CONTROL splits (`&&` becomes `&`,`&`). The multi-character alternatives therefore add length with no behaviour. `<<<` and `>>` are only partly covered (`>>` is killed by test_the_records_are_protected). Either delete `&&|\|\||;;|\|&|&>` from OPS or note why they are kept.
- [low] cli/wuwei/guards.py:103 blocks: no. Existing gap, not a regression: `&>>` is not in the `_unwrap` redirect tuple, so `git push origin main &>>.wuwei/ledger` leaves the path as a plain argv word of git and is not refused. It is the same on main. Record it as a gap.
- [low] cli/wuwei/guards.py:17 blocks: no. Readability: OPS is a 150-character alternation with no per-operator grouping. The line-17 comment says what it does but not that order matters (longest first). The line-28 and line-31 regexes are dense; a named comment for each alternative would help.

## Probes
- Suite at head: `pytest -q` gave 1103 passed, 2 skipped. The skips are pre-existing.
- Red on main: tests/test_guards.py, test_hook.py and routes.json from head were copied onto a `git archive` of 83f1f09 and run. 41 tests failed, so the new tests are red on main and green at head.
- Runtime: `wc -l` over cli/wuwei/*.py gave 2999. cli/wuwei/guards.py and .claude/wuwei/cli/wuwei/guards.py are identical (diff empty), and the vendored drift test passes.
- Acceptance 1: a stub git on PATH logged `push origin main` under `bash -c` for all 7 shapes plus `true |& git push origin main`. guards.segments yields the git segment for the five punctuation shapes and None (unreadable) for `$'` and `$"`.
- Mutants, each applied to both the cli and vendored copies and run against the full suite:
  - Killed: `|&` in CONTROL (killed by the `true |& git push` case), the OPS split (nosplit, split-all and `>>`), `dollar_off`, the `$'` only and `$"` only variants, the inside-quotes conditions (single-quote and double-quote alternatives), LEDGER bare `.wuwei`, the trailing slash, `.jsonl`, `=` on the first alternative, the `ledger/` children, the end anchor, the DOOR_WORDS lookahead (off, `.`, `/`, `\w`, the optional slash) and the `/ledger` alternative.
  - Survivors, re-run in fresh copies, as listed in Findings: `=` on the children, the start anchor, the lookahead `-`, the `$'` backslash alternative, and the equivalent OPS `&&`, `|&` and `&>` alternatives.
- Route corpus: every pre-existing row keeps its verdict, since the suite is green with the corpus test.
- Emojis and em dashes: a grep of the `git diff 83f1f09 67b367a` added lines found none.
- Spec completeness: specs/shell-doors holds spec (How this fails, Breaking, Assumptions, Rollback), plan, tasks, analysis and checklist.
- Simplicity: the OPS alternatives `&&`, `\|\|`, `;;`, `\|&` and `&>` can be deleted, because the `[();<>|&]` fallback gives the same CONTROL splits. The fix is to delete them or add a test that needs them. Nothing else is deletable. The `$'` check and the ledger guard are trust-boundary code and stay.

## Residual risk
The behaviour is correct on every probe. The one blocking item is a missing test for the `=` ledger-children clause, which is cheap to add. The remaining survivors are over-refusals or equivalent mutants.

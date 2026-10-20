Verdict: PASS
Gate: quality
Item: 1202
PR: taoq-ai/wuwei#1205
Head: f886ee381c601f054b6656e8476482d87aebb019
Confidence: medium
Breaking: no
Supersedes: 1202/quality-5edb6ce.md

## Findings
- [low] cli/wuwei/__main__.py:33 blocks: no. Mutant `case-match-always` (the ternary replaced by `args.repo`) survives: `--pr other/lib#3` on an item of acme/app would store `acme/app#3` and link an unrelated PR 3 of the item's repo. The head stores `Other/Lib#3` verbatim (probe), a dead entry that links nothing, so no regression exists; the missing test is a cross-repo ref in test_plan_add_keeps_and_merges_recorded_prs_and_matches_the_repo_case.
- [low] cli/wuwei/board.py:100 blocks: no. Mutant `lower-dropped` (the `.lower()` on the built ref) survives: a plan repo with capitals such as `Acme/App` would show `no pull request yet` instead of the not-linked line. The old text still shows, so nothing regresses; a test with a capitalised repo would pin it.
- [low] cli/wuwei/plan.py:63 blocks: no. Mutant `readd-no-dedupe` survives: the same `--pr` added twice would list the ref twice in `prs`. item_for tests membership, so the board is unchanged; the dedupe is cosmetic.

## Probes
- Head f886ee381c601f054b6656e8476482d87aebb019 read with `git archive` into `sentinel-quality-1202/t`. Base main d060785 is the merge-base of the head; the diff against it is 8 files, 73 added and 15 removed lines. cli/wuwei and .claude/wuwei/cli/wuwei hold identical __main__.py, board.py and plan.py (diff run on each).
- Full suite at the head, offline gh shim, CLAUDE_CODE_SESSION_ID unset, `uvx --python 3.13 --from pytest pytest -q`: 4 failed, 3005 passed, 1 skipped. The 4 failures are test_codex::test_the_hook_commands_run_under_either_harness_shell and three test_guards::test_bash_runs_the_push_in_each_refused_shape cases, the same four as on main in this bash 3.2 shell.
- CI: `gh pr view 1205` at the head, read once after the runs: test 3.11, 3.12, 3.13, ziran-audit, CodeQL, Analyze (actions and python) and ZIRAN all COMPLETED/SUCCESS. Green.
- Mutants (script sentinel-quality-1202/mut2.py), applied to both runtime copies one at a time against test_watch.py and test_plan.py with the vendored-copy test deselected: 22 run, 19 killed by a behavioural test, 3 survived (the three notes above). Killed: lookbehind dropped, bare `#` not expanded, promise not read, title not read, any named ref counts, open PR list ignored, line always `no pull request yet`, id swapped in the message (all by test_an_item_naming_an_open_pr_without_its_link_says_so); item_for clause dropped (test_an_item_naming_another_items_open_pr_gets_no_not_linked_line); `--pr` ignored, `--pr` not registered, `prs` dropped in plan.add; `_ref` unchecked (test_plan_add_refuses_a_pr_that_is_not_owner_repo_number); repo case match dropped, re-add replaces the list, re-add keeps only a non-empty new list, merge order swapped (test_plan_add_keeps_and_merges_recorded_prs_and_matches_the_repo_case).
- Conflict-resolved lines from #1203 in board.py: mutants `run-owed-mark-dropped` and `run-owed-guard-dropped` are both killed by test_a_run_item_stays_open_with_run_owed_when_its_pr_merges_until_plan_done, so both sets of lines are live in the merged tree and their tests pass.
- closed: `_ref` check untested at 5edb6ce, now killed by the refuse test over `7`, `foo` and `acme/app#x`, which also asserts nothing is stored.
- closed: replace-on-re-add at 5edb6ce, now merged and de-duplicated; the test shows `['acme/app#7', 'acme/app#8']` after a re-add with a new `--promise` and a second `--pr`.
- closed: wrong not-linked instruction for another item's PR at 5edb6ce, now killed by the item_for clause mutant; item A naming PR 9 with footer `WUWEI-Item: B` gets `no pull request yet`.
- closed: case of the stored ref at 5edb6ce for the item's own repo (`Acme/App#7` becomes `acme/app#7`, killed by the case-match mutant); another repo's ref is stored as typed, which is a dead entry, see the first note.
- closed: `reason` read but unreachable at 5edb6ce, now removed from the scanned fields and the lookahead removed from the regex; no mutant is left on either.
- Probe through cli.main in the copy: `--pr Other/Lib#3` stores `Other/Lib#3`; `--pr acme/app#7` added twice stores it once.
- No parser or guard code in guards.py or hook.py changed, so the route-corpus differential does not apply.
- Simplicity: none to delete. The `dict.fromkeys` dedupe in plan.py is cosmetic (survivor above) but one call and cheap; the `.lower()` and the case ternary are guards that belong.

## Residual risk
Low: the board line is advice only and no door reads it. A mistyped cross-repo `--pr` is stored as a dead entry with no output, and a plan repo with capitals loses only the hint.

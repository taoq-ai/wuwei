Verdict: FIX
Gate: quality
Item: compound-doors
PR: taoq-ai/wuwei
Head: 6c9b74cb5e2bb7e241182bf53362e771bc063f27
Confidence: medium
Breaking: no

## Findings
- [medium] tests/test_guards.py:420 blocks: yes. Failure: the `Path(argv[0]).name in SHELLS` guard on the -c unwrap has no test. Reversed, `git -c core.x=y push --force origin x` unwraps to the word `core.x=y`, the git push segment disappears and the force-push door is skipped. The full guards suite stays green with that guard removed. Add a case with a non-shell program given -c, such as `git -c a=b push --force origin x`, that expects a deny.
- [medium] tests/test_guards.py:420 blocks: yes. Failure: the `while` entry in the reserved-word list is untested. The cases use `while true; do ...`, so the door sits after `do`. Removing `while` leaves argv[0]=='while' for `while git push --force origin x; do :; done`, which is not read as git. Add a `while <door>; do` case. The `if git push` and `until git push` cases already exist.
- [medium] tests/test_guards.py:420 blocks: yes. Failure: the `elif` entry is untested for the same reason. The case uses `elif true; then git push ...`, so the door follows `then`. Removing `elif` lets `elif git push --force origin x; then` through as argv `elif git push ...`. Add an `elif <door>` case.
- [low] cli/wuwei/guards.py:90 blocks: no. Note: `bash -o pipefail -c 'git push --force origin x'` and `bash -o errexit -c ...` are not unwrapped, because the body is taken as the first non-dash word. The old code missed them too, and the promise covers only combined flags. Residual to record under SECURITY.md.
- [low] tests/test_guards.py:420 blocks: no. Note: mutants that survived and have no concrete harm. They are the `>|` entry removed from the redirect operators, `argv[1:body]` widened to `argv[1:]` (`bash deploy.sh -c x` is then misread as a -c body), the READ entries `wuwei`, `sed`, `terraform`-family and `curl`-family (`gh` is also in NETWORK, so it is equivalent), and the `-\w*c\w*` regex widened to any dash word (`bash -x deploy.sh` gets misparsed). Optional tests: `nice -n 5 terraform apply`, `env -u X wuwei hook SubagentStop`.
- [low] cli/wuwei/guards.py:87 blocks: no. Note: `tokens[i + redirect]` and `i += 1 + redirect` add a bool to an int, which hides intent. A plain `if` would read more clearly at the same line count.

## Probes
- Ran the suite on a `git archive` copy of 6c9b74c in the scratch directory: 431 passed. Skipped: none were reported.
- 32 mutants of guards.py, each in its own copy and run with `pytest tests/test_guards.py -x`. Killed: skip do/then/else/if/until/!/{, -c cluster narrowed to -c, first-program rule off, READ without git/shells/writers/python, wrapper timeout/stdbuf removed, UNREAD marker dropped (killed by test_an_unreadable_sh_c_body_naming_a_door_is_refused), UNREAD replaced by [], redirect off, redirect targets dropped, redirect step and bounds, body index from 0.
- Survived: `elif`, `while` and the shell-check guard (the three blocking findings above, each confirmed with a concrete input via segments()), plus the non-blocking ones listed.
- Acceptance coverage: each of the six scenarios has a test. The merge-door case is covered by `gh pr merge $pr` expecting 'name the PR'. The no-refusal cases are in test_ordinary_loops_ifs_and_wrapped_commands_pass. The size test passes.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 3000 at the head and 3000 at origin/main, so the net is 0. guards.py is 309 lines on both.
- Vendored copy: `diff -r -x __pycache__ cli .claude/wuwei/cli` is empty at the head. setup.vendor() copies PLUGIN/cli unchanged, so the copies match.
- Tests that failed before the change were not run against main one by one. The mutants show the new tests fail when the new logic is removed.
- Simplicity: none to delete. The first-program rule replaces the flag-skip loop. UNREAD is a sentinel, but it is the smallest way to carry "unreadable" to bash(), so keep it. The `startswith('python')` clause in READ goes beyond the promise but is killed by a test and kept for the ledger-write case.

## Residual risk
- eval, `| sh`, here-strings, a variable as the program name, `bash -o opt -c`, and `case ... esac` bodies are still read only by shape. Only the first group is named in the promise.
- The three missing tests are cheap to add. Production code looks right on every input probed.

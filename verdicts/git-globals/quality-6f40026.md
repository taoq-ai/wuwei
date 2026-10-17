Verdict: FIX
Gate: quality
Item: git-globals
PR: taoq-ai/wuwei#1122
Head: 6f40026654c22d4adc19c5532c3a56537fd29b65
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:339 blocks: yes. Failure: the step `i + (2 if m and m['pair'] else 1)` is untested. Reversed to `i + 2`, the full suite still passes, and `git --no-pager push origin main`, `git -p push origin main` and `git --bare push origin main` then skip the push word and reach no push door (guard returns None). A lone valueless option before a push to main is the exact bypass this item closes, and no test pins it. The refused list only has valueless options in positions where the skip lands on another option. Add `git --no-pager push origin main` and `git -p push origin main` to GIT_GLOBALS_REFUSED, plus `git --bare push origin main`.
- [low] cli/wuwei/guards.py:51 blocks: no. Untested alternatives in GIT_OPTS (reversed, nothing fails): `--git-dir=`, `--work-tree=`, `--attr-source=` (the = forms; only --namespace=, --exec-path=, --list-cmds= are covered), and the valueless names `--no-pager`, `-h`, `-v`, `--version`, `--bare`, `--literal-pathspecs`, `--icase-pathspecs`, `--no-optional-locks`, `--html-path`, `--no-replace-objects`, `--paginate`. Dropping one only over-refuses a push after it (false positive, for example `git --git-dir=x push origin feature`), so no bypass. The refusal is only tested with a push, so `git --no-pager log` passes whatever the list holds. A table-driven test that runs every option before `push origin feature` would kill all of them.
- [low] cli/wuwei/guards.py:51 blocks: no. GIT_OPTS is hard to read: one 5-line raw-string regex with nested groups, a `\0` word separator trick and a long trailing comment. It works and its groups are named. The option list could be a tuple of names, which would also make the test above a loop over that tuple.

## Notes
Tests are red on main. Running the head tests and routes fixture against main gives 30 failures (13 steering, 6 push-door, 5 unknown-option, 6 routes), above the builder's 22 of 32. The known-options-pass tests are green on main, as expected for regression guards.

Suite at head: 1544 passed, 2 skipped. Runtime is 2,996 lines. The vendored copy .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py. No em dash or emoji found in guards.py, the tests or the spec files.

Spec set is complete: spec.md (with How this fails, Assumptions and Rollback), plan.md, tasks.md, analysis.md and checklists/requirements.md.

Differential probe, main versus head, over 8,386 commands (routes.json, every string in test_guards.py, and generated operator x redirect x program combinations):
- `segments()` output: 0 differences, which covers the segments-flush and `_unwrap` redirect lines.
- `origin()` over 7 URLs: identical.
- The merge_door docstring: no behaviour change.
- `bash()`: 736 differences, all from the new behaviour (git options or `-c` steering before a push, plus the alias refusal). One difference is a "note" for a `gh api repos/{owner}/{repo}/pulls` command. It also differs between two runs on main, so it is state-dependent and not caused by this change.
- A side effect: `git -c alias.c='clean -fdx' c` was refused on main with the ledger message. It is now refused with the "hides a push" message, which is slightly misleading.

Mutants (re-run in a fresh copy where it survived): killed were -C, -c and each pair option; the = forms for namespace, exec-path, list-cmds and config-env; case folding; alias, remote, branch, url, include and push.default in the steering list; `--config-env` and the `=` separator in the steering form; the unknown-option refusal and its push-or-two-words condition; the `-p` option; and the one-word-advance and "odd words" lines. Survivors are listed in the findings above.

## Probes
- Suite at head: 1544 passed, 2 skipped (pytest -q in a git archive copy).
- Head tests against the main tree: 30 failed.
- 47 mutants of GIT_OPTS and the option loop: 36 killed, 11 survived (the survivors named in the findings, plus the `i + 2` mutant, re-run in a fresh copy, which really lets `git --no-pager push origin main` through).
- Differential probe as described under Notes.
- Simplicity: the `-c`/`--config-env` steering path is not deletable, since it is trust-boundary validation. The `odd` variable and the dual condition `'push' in rest or ' ' in odd` are needed. Nothing to delete. The option list as one regex could be a tuple (see the readability note).
- Confidence is medium. The mutant set was hand-built, and the push door was stubbed to record its arguments, so only routing was probed. No real push was made.

## Residual risk
The option allowlist follows git 2.43, so a later git that adds a global option makes pushes with that option be refused until the list is updated (fail-closed). The `i + 2` step is the one confirmed untested bypass spot.

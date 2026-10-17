Verdict: PASS
Gate: quality
Item: git-globals
PR: taoq-ai/wuwei#1122
Head: 783522a4e4a7df393ce533e85ec033e0e06a2867
Confidence: medium

## Findings
- [low] cli/wuwei/guards.py:341 blocks: no. The alias refusal's wording is only half pinned: the alias text is tested ('a command the guard cannot read', 'git config'), but the unknown-option text 'an unknown option, or -c remote, ...' can lose its leading words and nothing fails (the test checks the option name and 'run git push without it'). Message-only mutant, no input is let through.

## Closed
- Round 1 blocking finding (untested pair step): closed. `git --no-pager push origin main`, `git -p push origin main` and `git --bare push origin main` are now in GIT_GLOBALS_REFUSED, and the table test runs every option before a push to main. Mutant `i + 2` and mutant `i + 1` (no pair step) are both killed.
- Round 1 low (11 GIT_OPTS survivors) and the readability note on the option list: the survivors are killed by the table-driven test over GIT_OPTIONS (35 options, each form, a feature push passes and a main push meets the push door). The regex is still one block; the option list as a tuple remains a style note, not a defect.
- Round 1 note (alias-refusal text misleading for `git -c alias.c='clean -fdx' c`): closed. The alias wins rule now sends it to the alias message, and GIT_ALIASES pins it.

## Notes
- The new alias-first behavior and the in-place appends are covered by tests that fail on the old form (see Probes).

## Probes
- Suite at head in a git archive copy: 1600 passed, 2 skipped (pytest -q). Runtime wc -l cli/wuwei/*.py: 2,997. Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical (cmp). No em dash, en dash or emoji in the added lines of the whole diff (python scan). Spec set present with FR-003, FR-006 (2,997) and FR-007 (linear), plus Assumptions and the alias-wins round note.
- Mutants on changed lines, 25 run, 24 killed, 1 survived (the message text above): the pair step (+2, +1), segments copy per token, no reset, drop; _unwrap redirect word always, never, inverted; alias-wins off, alias-first-only, always-replace odd, no-unknown, no-steer; steer lookahead removed, alias only, include only, remote dropped, push.default dropped, `=` separator dropped, case folding dropped; alias anywhere off, alias only when run; alias text; odd re-parse. The unknown-text survivor re-run in a fresh copy: still survives.
- GIT_OPTS literal mutants: each option word replaced in turn (git-dir, work-tree, namespace, config-env, attr-source, shallow-file, exec-path, list-cmds, paginate, no-pager, bare, no-replace-objects, no-optional-locks, html, man, info, help, version, icase, literal, glob, noglob, exec) and each of the C, c, p, P, h, v letters removed: 0 survivors, so the 11 round 1 survivors are dead.
- Timing tests: run against the 6f40026 guards.py with head tests, both `true;` and `>x ` cases fail (the `>x ` one at 26.8 s for 500 KB against the 8 s limit); the `segments` per-token copy mutant is killed too. On head they pass in 2.65 s and 2.13 s total, so they are meaningful. The git option loop test (0.78 s for six shapes) passes on both forms, as it covers unchanged code.
- Differential probe of segments() and _unwrap() between main d1c3d79 and head over 8,543 commands (1,463 from routes.json and every string literal in test_guards.py, the rest generated: 12 operators x 8 programs x 8 programs, 13 redirects x programs x targets, positions before and after), plus _unwrap on every token prefix: 0 differences. The in-place append and the redirect rewrite are behavior-equivalent to main.
- Simplicity: none deletable. The in-place appends are needed (quadratic at 500 KB on the old form). `odd`, the re-parse of `odd` and the `'push' in rest` condition carry the alias refusal and the unknown-option rule. The dense one-line forms in segments, _unwrap and the loop are hard to read but follow the repository's compact style and the line budget.
- Confidence is medium: the mutant set is hand-built and the push door was exercised through the test fixtures (a fake), so only routing was proved. No real push was made.

## Residual risk
The option allowlist follows git 2.43, so a later git that adds a global option makes a push after it refused until the list is updated (fail-closed). Timing thresholds (2 s, 8 s, 1 s) could flake on a very slow runner; head uses about a third of them.

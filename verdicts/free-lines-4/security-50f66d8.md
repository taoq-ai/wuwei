Verdict: PASS
Gate: security
Item: free-lines-4
PR: taoq-ai/wuwei#1112
Head: 50f66d80d4c882f8f855495a3b2856809d29a031
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:333 blocks: no. The merged `elif program == 'gh' and (found := gh_command(...))` now falls through to the INFRA elif when gh_command returns None; that is equivalent today only because INFRA has no 'gh' key (mutant turning the elif into `if` survives, equivalent). A future INFRA entry for gh would change routing; worth a one-line comment or test if INFRA ever grows.
- [low] blocks: no. Every walrus rewrite (guards, hook, sync, plan, upgrade, evidence, report, setup, verdict) keeps the old `if x` / `if not x` test on the same value, so an empty string, list, dict, None or 0 is treated exactly as before; no rewrite sits inside a comprehension, so binding scope is unchanged.

## Probes
- Generated differential (scratchpad/security-free-lines-4/probe/test_zz_diffprobe.py) run in git archive copies of main 9d6701e and head: 279,071 rows, each the command or payload, repr(guards.segments), guards.bash decision and guards.pre_tool decision with full reason text. Corpus: all routes.json commands; 24 door commands x 6 prefixes x 566 punctuation runs (every run of length 1-3 over | & ; < > ( ), 150 random runs of 4-6, plus ||, ;;, |||, ;;&, ||&, >||, <<<|| and more) x 3 spacings; wrappers (sh -c, bash -lc, env, sudo, nohup), case ;; and ;;&, multi-line, $'..'; AskUserQuestion with empty and classed questions; Edit/Write/NotebookEdit with empty, 0 and ledger paths; MCP push/merge/create/ready with empty, None, 0 and string branches and PR numbers, secret and canary bodies. main.jsonl and head.jsonl both sha256 7951040088039147bafbeed6293f94333140b6174fcb183c3cccf5784db9daaf, cmp identical: 0 differences. Distribution: 164,336 deny, 10,238 ask, 104,496 pass, 1 note, 45 distinct reasons, so the corpus reaches the leak, canary, infra, ledger, push, merge, create, ready and unreadable doors.
- Route corpus tests/fixtures/routes.json sha256 9ea9491c19cbd2535f70e04252f6044e4c306c48a298f8fdcbc44b5f2501dff8 on both trees; `pytest -q tests/test_guards.py -k route` 267 passed on main and on head.
- Builder probes copied to my scratch and run on both trees: pairs.py (34,300 push shapes, 6,912 ledger shapes, real bash with stub git: 0 holes), probe.py and probe2.py (leak, canary and infra shapes with stub git, curl, terraform): outputs byte-identical main vs head (sha256 prefixes ddbfd48af2859d15, 0792fc3586fa3331, 32098d85096769e3).
- Full suite on head: 1196 passed, 2 skipped. .claude/wuwei mirror diff -r against cli/wuwei: identical.
- Mutants on changed guard lines, each in a fresh git archive copy (mutants.py): NETWORK leak walrus negated 397 failed; git push walrus negated 95 failed; gh walrus negated 354 failed; _unwrap input-redirect check reversed 18 failed; _unwrap skip removed 38 failed; unclassed walrus negated 16 failed; SECRETS walrus nulled 9 failed (test_secrets_never_leave); glued dropped 7 failed; zip '' pad dropped 2 failed; && dropped from OPS 2 failed (new test). gh elif to if: survived, equivalent (see note).
- Confidence high: 0 differences across a generated corpus covering every changed door path, plus the real-bash pair probe; it would drop if a door decision depended on state my stubs fix (origin o/r, branch i-1-change, fake gh).

## Residual risk
The differential fixes origin, branch and the code host to stubs; decisions that depend on live gh responses are covered only through the fake. The non-guard walrus rewrites (sync, report, plan, setup, upgrade) were checked by reading, not by a differential.

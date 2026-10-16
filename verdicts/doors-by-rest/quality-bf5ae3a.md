Verdict: FIX
Gate: quality
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: bf5ae3ae539aba6ed554025733039257a0e6a821
Confidence: medium

## Findings
- [medium] cli/wuwei/guards.py:171 blocks: yes. Failure: no test covers a value-taking short flag before the endpoint. Dropping H from the API_FLAG class (mutant) leaves all 645 tests green, and a call with -H 'Accept: application/vnd.github+json' -X PUT repos/o/r/pulls/5/merge then reads the endpoint as "Accept: ..." and skips the merge door (verified with _api). Add a case with -H/--header (and -q/-t/-p) before the endpoint.
- [medium] cli/wuwei/guards.py:174 blocks: yes. Failure: no test has --input without -X. Changing the POST default to else 'GET' (mutant) survives, and gh api repos/o/r/pulls --input in.json (gh sends POST) then reads as GET and skips the create door. The --input tests all pass -X POST. Add that spelling.
- [low] blocks: no. Mutant removing --raw-field from the field-key list survives (the test only reads base from it, and the missing base still denies); add --raw-field head=.
- [low] blocks: no. test_gh_pr_new_is_gh_pr_create only checks the door reached, not head/base/body parity with gh pr create; the routes.json entry also covers this.

## Probes
- Copy: git archive of bf5ae3a into scratch; full suite 645 passed, 2 skipped; runtime test passes at 2,996 lines (wc over cli/wuwei/*.py).
- Mutated 53 guards in the tree and the vendored copy together (route table methods and patterns, WRITE members, -X/-XPUT/-X=/-iX/--method= reader, -F @file vs -f, field-key lists, --input read, POST default, last-method-wins, upper-casing, leading slash, host, query, trailing slash, owner/repo fill, graphql endpoint test and each of 10 mutation names plus the wildcard affixes, gh pr new, DOORS push entries, MCP no-branch, refs/heads strip, create head fallback): 50 killed. Survivors: -H class (finding 1), --input POST default (finding 2), --raw-field (low). My first refs/heads mutant hit git_push's identical text; rerun on the MCP line was killed.
- Every route in tests/fixtures/routes.json reads as recorded: test_every_route_reads_as_recorded passes on all entries, and mutating create, merge, push, delete and graphql entries each fails a named route.
- Acceptance 1-9 each map to a test (create parity, body file via -F/--field/--input, gh pr new, merge spellings, graphql mutations, refused writes, MCP push_files plus DOORS fail-closed in test_hook, pass routes, size test).
- Vendored cli/wuwei/guards.py equals cli/wuwei/guards.py; charters/shepherd.md equals the vendored charter; agents/shepherd.md equals .claude/agents/shepherd.md.
- Simplicity: none to delete safely. _read could reuse one Path object, saving no lines against the 3,000 cap. The +36 against +18 comes from the _api reader, which replaces the old regex and flag scan and is exercised by the mutants above. Trust-boundary guards stay.

## Residual risk
Flag readers for rarely used gh api spellings stay untested until the two cases above land; the code itself reads them correctly today.

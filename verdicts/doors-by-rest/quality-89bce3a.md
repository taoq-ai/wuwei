Verdict: FIX
Gate: quality
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: 89bce3a98208859ba6cdeea27a52eaaf56340890
Confidence: medium

## Findings
- [medium] cli/wuwei/guards.py:171 blocks: yes. Failure: the --input POST default is still unkilled, because the new test only uses an --input file that holds head and base, which makes `fields` non-empty and POST anyway. Changing the default to `else 'GET'` (mutant) leaves all 682 tests green, and `gh api repos/o/r/hooks --input h.json` with a JSON body lacking head/base/body (gh sends POST) then reads as GET and skips the rules refusal (the real code returns POST, checked with _api). Add a test with an --input file without head/base/body on a guarded route.
- [low] cli/wuwei/guards.py:193 blocks: no. The re.I on route matching and m[3].lower() have no test that fails when removed (the case-insensitive tests only vary the host, which the endpoint strip handles). I cannot name a path spelling gh accepts that this alone catches; a test with a mixed-case path would pin it.
- [low] blocks: no. --raw-field removed from the field-key list still survives (only base is read from it), and removing jq from the long-flag list survives as equivalent (an unmatched --jq= is skipped as a dash argument).

## Probes
- Copy: git archive of 89bce3a; full suite 682 passed, 2 skipped; runtime 2,996 lines (cat cli/wuwei/*.py | wc -l), the size test passes; vendored guards.py identical to cli/wuwei/guards.py.
- Re-ran 68 mutants on the tree and vendored copy together, including the new code: the attached-value lookahead, the `v is None` step and the empty-value branch, the generic host strip (scheme, any-case, port), -H/-q/-t/-p/--header, re.I and lower(). 62 killed; survivors are the six above (--input default, re.I, lower, --jq, --raw-field, and an invalid mcp refs/heads mutant that hit git_push first, killed when applied on the MCP line in the earlier round).
- The previous -H survivor is now killed by test_every_rest_merge_spelling_meets_the_merge_door -H/--header cases; the previous --input blocker is only half closed (finding 1).
- Every route in tests/fixtures/routes.json, including the 11 new ones, reads as recorded (test_every_route_reads_as_recorded passes).
- Simplicity: none to delete; the changed _api line is dense but replaces the old attached-value logic one for one and every branch is mutant-killed.

## Residual risk
A guarded endpoint reached with `--input` alone on a body with other keys depends on one untested default; the code is right today.

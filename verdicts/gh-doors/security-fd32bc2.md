Verdict: PASS
Gate: security
Item: gh-doors
PR: taoq-ai/wuwei#1108
Head: fd32bc2b11a23d71f5007e14e67b707f17bd5eaa
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:212 blocks: no. Mutant M10 (`endpoint == 'graphql'` instead of `.lower()` in the unread check) survives twice in fresh copies. `echo <mergePullRequest> | gh api GraphQL --input -` would then pass, and real gh 2.89.0 sends POST /GraphQL. Whether GitHub routes /GraphQL to the GraphQL endpoint is unmeasured. Head is correct. Missing test: a case-variant or full-URL endpoint in test_a_graphql_query_wuwei_cannot_read_is_refused.
- [low] cli/wuwei/guards.py:172 blocks: no. Mutant M1 (drop `path != '-'`) survives twice. A file named `-` in cwd would make `--input -` read that file while gh reads stdin. A plain single call has no pipe or redirect, so stdin is only the harness's own, and I found no input that does harm. Missing test: a file named `-` beside `--input -`.
- [low] cli/wuwei/guards.py:183 blocks: no. Mutant M8 (drop `alone and` in the data-to-query line) survives twice. It is equivalent: when the call is not alone, the unread check already refuses graphql, and the query field means nothing to REST routes.
- [low] blocks: no. A form-encoded body passes the guard: `gh api graphql -H Content-Type:application/x-www-form-urlencoded --input form.txt`, where the file holds `query=%6D%65%72%67%65PullRequest`. Real gh sends it as-is. Whether GitHub GraphQL accepts a form body is unmeasured (it needs GitHub). If it does, a percent-encoded mutation name hides from MUTATIONS.
- [low] blocks: no. TOCTOU (time of check versus time of use): the guard reads the --input or -F @ file at hook time, and gh reads it later. A background job from an earlier Bash call could rewrite the file in between. This is the same class as the existing --body-file and -F @file reads.
- [low] blocks: no. Existing and unmeasured: X-HTTP-Method-Override (POST repos/o/r/pulls/5/merge with the header set to PUT passes, and gh sends it), a query string carrying `?query=` on graphql, and `repositories%252F123` (passes; GitHub would decode it once to `%2F`). Each needs GitHub itself to settle.

## Probes
Real gh 2.89.0 with http_unix_socket pointed at my own logging server (scratchpad/security-gh-doors/gh). For each command I compared what gh sent with guards.bash at main 23625f3 and at head. Doors were stubbed to print the repo#number they would check.
graphql --input: q.json, a \u-escaped name, a comment plus an alias, a fragment plus operationName, query given twice, the mutation inside variables, and a symlink to q.json all pass on main and are refused at head naming the mutation. ok.json (a plain read query) passes on both.
graphql unreadable: --input -, --input=-, -F query=@-, --field=query=@-, -iFquery=@-, -F=query=@-, a symlink to /dev/stdin, an empty file, a missing file and --input= are refused at head. gh sent the mutation from stdin on each live route.
-f query=@- and -f query=@m.graphql pass, and gh sends the literal "@-" or "@m.graphql", so no file is read. -F query=@m.graphql is refused on both. In the -f/-F mixes gh exits with "unexpected override existing field". --input ok.json -F query=@m.graphql is refused. --input ok.json --input q.json raises JSONDecodeError, and hook.handle fails closed (deny, checked).
Wrappers and separators: cd sub &&, env -C sub, a VAR= prefix, `cp q.json ok2.json;` before the call, and a file rewritten in an earlier segment are all refused at head as unread. --input sub/q.json is refused naming the mutation, and --input 'ok.json' passes.
Endpoint spellings: /graphql, graphql/, GRAPHQL, GraphQL, the https://api.github.com/graphql full URL, ./graphql, %67raphql and graphql?x=1 are refused with --input q.json or stdin. gh sent each spelling as written.
Non-UTF-8 and UTF-16 input files raise UnicodeDecodeError, and hook.handle returns deny (fail closed, checked in tools/failclosed.py).
repositories/: POST, PUT and PATCH with methods spelled -XPUT, -X=PUT, -X put, -X Patch, --method=put and -X DELETE are refused. So are REPOSITORIES, Repositories, //, a leading /, /./, %2F, %72 and the full URL in any case, and --input, -f or -F with no method (implied POST, which gh sent). GET, -X GET with -f, and the last -X GET pass. -X= makes gh fail with an invalid method "=".
Merge flags: checked against real gh's pflag through the --auto/--disable-auto/--admin mutual-exclusion error. The guard agrees with gh on --admin=true/1/T/TRUE (on), --admin=false/=/yes (off; gh rejects = and yes), the last --admin winning, -t, -dt, -A, --subject and --match-head-commit swallowing --admin or --auto, -t=--auto, -F --auto (gh opens a file named --auto), --auto=false and the last --auto winning, and `-- --admin` (gh: accepts at most 1 arg). -sd --admin is refused.
Route corpus: tests/fixtures/routes.json sha256 is 93d26ddc4551ca97183df579631b05392c0af8edc7cd59d776163e8d16ffa20f at main and 07ee0c70f86865e7e3653defe1257fd75169d4b51523bb10219f06019a7621ea at head (132 routes). The head corpus on main code gives 8 failed and 223 passed: only the new acceptance rows fail, and every row from before keeps its verdict. The head suite gives 1009 passed and 2 skipped.
Refusals naming a different PR or repo (same at main and head, and the same repo gh reads from the URL): `gh pr ready https://github.com/other/x/pull/7` goes to other/x#7.
Refusal naming a different PR or repo: `gh pr ready -R o/r https://github.com/other/x/pull/7` goes to other/x#7.
Refusal naming a different PR or repo: `gh pr merge https://github.com/other/x/pull/5 -R o/r` goes to other/x#5.
Mutants, each in a fresh git archive copy: M2, M3, M4, M5, M6, M7, M9, M11, M12 and M13 are killed. M1, M8 and M10 survive, and each was re-run in a new copy.
Confidence is high because every new rule was checked against real gh requests. What is left depends on GitHub's own routing, which is unmeasured.

## Residual risk
GitHub-side parsing is unmeasured: endpoint case, form-encoded GraphQL bodies and method override. File reads stay open to a TOCTOU race with a background writer.

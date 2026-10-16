Verdict: PASS
Gate: security
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: 89bce3a98208859ba6cdeea27a52eaaf56340890
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:193 blocks: no. Case-insensitive route matching (`re.I`) is not covered by any test. Removing it survives tests/test_guards.py and tests/test_hook.py (mutant no-re-i), because every recorded uppercase spelling also has an uppercase host that is stripped anyway. A route like `gh api -X PUT repos/o/r/PULLS/5/MERGE` (which real gh sends as typed) is the input it would need. Whether github.com routes uppercase path segments is unmeasured, and main misses these spellings too.
- [low] cli/wuwei/guards.py:190 blocks: no. The graphql check compares `endpoint == 'graphql'` exactly while the doors now match case-insensitively. `gh api -X POST GRAPHQL -f query='mutation{mergePullRequest...}'` passes, and real gh sends it as `POST /GRAPHQL` with the token. GitHub's routing of `/GRAPHQL` is unmeasured. Comparing with `endpoint.lower()` would make the check consistent with the doors.
- [low] blocks: no. Notes carried from bf5ae3a, unchanged by this fix: `gh api graphql --input q.json` and stdin queries pass (outside this item's promise); `:owner/:repo` reaches the door as a literal repo and fails closed; `revertPullRequest` is not in MUTATIONS; `merge-upstream`, branch rename and `PATCH default_branch=` move the default branch without a PR, as on main; `_read` has no size limit and a binary file raises, which fails closed; GH_REPO, `--hostname` and aliases are not read (documented in SECURITY.md).

## Probes
Previous findings: all three closed. Finding 1 (empty attached values): `-X=`, `--method=`, `-t=`, `-q=` and `--jq=` before `-X PUT` reach the merge door again, and the same spellings reach the refusals and the create door (`-X= -X DELETE`, `-q= -X PATCH git/refs`, `-q= .../pulls`, `-X= -X POST graphql`). Finding 2 (URL prefix): `HTTPS://API.GITHUB.COM/...`, `http://...`, `:443` and the all-uppercase URL reach the doors. Finding 3: the MCP push leak mutant is now killed by test_a_secret_in_an_mcp_file_write_on_a_feature_branch_is_refused.
Real gh 2.89.0 against the local logging server (GH_HOST=github.localhost; probe.sh, probe2.sh, probe3.sh, 43 spellings): `-iX=PUT`, `-iiX PUT`, `--method=Put`, `-i=true`/`--include=true` and `-p=`/`--preview=` all send PUT, and the guard reads every one as merge. `-iXPUT=`, `-X==PUT`, `--method ' PUT'`, `-H=`, `--hostname=` and `--cache=` make gh error out before any request. With repeated `--input` gh sends the last file; the guard reads all of them and lands on the same door. `--paginate` refuses non-GET requests.
Main versus head: 96 spellings through guards.bash in archive copies of origin/main and the head (tests/test_sec_probe2.py). No spelling moves from a door on main to pass on head. All 24 seat routes pass on both: review threads, CCR resolve, comments and replies, the issue ping, reviewer requests, reviews, check-runs, issues, labels, PR patch, ref create, and contents/ref reads.
Suite at head in an archive copy: 682 passed, 2 skipped. Runtime is 2,996 lines, and the vendored guards.py is identical.
Mutants (mutate2.py, 22): 21 killed, including the new empty-value consumption, the attached-empty value, the short `=` form and the case-insensitive scheme strip. One survived (no-re-i, the first note).
Confidence is high: every blocking spelling from the last round was re-run against real gh and the head guard. security-89bce3a.md beside this file failed the strict shape check (nested bullets); this file replaces it.

## Residual risk
How github.com handles uppercase path segments, `/GRAPHQL`, percent-encoded paths and X-HTTP-Method-Override is unmeasured. Verbs that move the default branch without a PR remain outside every door, as on main.

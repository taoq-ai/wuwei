Verdict: PASS
Gate: arch
Item: verdict-closed
PR: taoq-ai/wuwei#1144
Head: d8a09671df6f45863316df639ea055e3f65e6993
Confidence: high
Breaking: no

## Findings
- [low] docs/site/reference.md:87 blocks: no. The published reference of the verdict format still says "(or none)" under Findings and does not say closed findings go under Probes. The charter and the FORMAT text now carry the rule, but the reference page lags (documentation drift of the verdict contract). A follow-up docs line would close it.
- [low] cli/wuwei/verdict.py:19 blocks: no. FORMAT says "a finding your fix closed", but a gate does not fix anything. The charter block says "open findings only, or the single word none" and rule 6 says "Closed findings". The FORMAT copy and the charter block also no longer match word for word. Wording only; the parser is unchanged.
- [low] charters/_gate.md:48 blocks: no. Trimming the text to fit the 2,250-word ceiling replaced the full name `<gate>-<first 7 of head>-2.md` with a bare `-2.md`. A reader could take that as a file literally named `-2.md`. It does no harm, because the hook attests any name under verdicts/ and every refusal now names the full free file.
- [low] cli/wuwei/hook.py:147 blocks: no. free() raises StopIteration once names -2 through -998 are all taken. That cannot happen with a handful of seats per head; recorded as a limit only.

## Probes
Conformance: the change follows the never-edit rule (charters/_gate.md "Never edit a verdict file once written") and docs/design.md "Verdicts count only when attested". All three "beside it" refusals in hook._verdict_problem (copy-in, other-seat, shape) now name free(path), which is computed over the workspace folder where the copy-in checks for a held name. No new import and no new module dependency; hook.py already imported verdict, re and Path.
Contract: verdict.parse is unchanged (the verdict.py diff touches only the FORMAT string). The only consumer is hook.py:170 (grep of verdict.parse/verdict.FORMAT across cli/). Old verdicts and old-charter verdicts parse the same way. In the builder's hand-back matrix I re-ran on the merge base 3d2eb29 and the head: 232 rows, 124 refusal reasons moved, 0 attest counts moved. So which verdicts attest is unchanged, and only the refusal text names a different file.
Breaking: no. The block or pass decision and the ledger attest rows are unchanged. The refusal text goes to agents, and no client parses it. The file format, config keys and ledger kinds are unchanged.
Route differential: I wrote my own probe at scratchpad/sentinel-arch-verdict-closed/scripts/test_zz_arch_diff.py. It reads every route through guards.bash and through hook.handle PreToolUse, comparing full decision JSON. Corpus sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 is the same at both ends. Merge base 3d2eb29 vs head: 251 routes, 0 moved. Main tip 8c1939e vs head: 1 moved ("gh pr create --draft"), and only the footer version moved (4.0.0 on main, 3.0.1 on the branch). That comes from the release commit #1143 on main, not from this diff.
Builder probe re-run (specs/verdict-closed/probe_differential.py and compare.py, base vs head): routes 251/0 moved, payloads 7/0 moved. At the head, 140 refusals name a next file, 140 of those files are free and attest, 0 holes. On the base, 32 holes. No file outside the folder changed.
Mutants (fresh git archive copy per mutant, tests/test_hook.py): no stem strip, no lookbehind, held names ignored, range starting at 1, old shape message, old copy-in message and old other-seat message. All 7 were killed by named tests (test_a_shape_refusal_names_a_number_no_file_or_link_holds[from-2/from-12/digit-sha/taken/first], test_closed_findings_under_findings_name_the_next_free_file_to_write, test_the_other_refusals_that_say_write_beside_it_name_the_next_free_file_too).
Fitness: runtime lines, from `cat cli/wuwei/*.py | wc -l`, went from 2986 at main to 2987 at the head. That is +1 against a budget of 1, and the ceiling is 3400. agents/sentinel-arch.md, from `wc -w`, is 2250 words at the head and 2245 at main, which is exactly the AGENT_WORDS=2250 ceiling (tests/test_charters.py:15). The goal, quality and security agents are at 1962, 2053 and 2088. charters/ and .claude/wuwei/charters/ are identical (diff -r), and so are the vendored hook.py and verdict.py.
Suite at head (/root/.local/bin/pytest -q): 1788 passed, 2 skipped, 1 failed. The failure was the timing test test_segments_and_redirects_stay_linear_at_125_and_500_kb[>x ]. It passed when re-run at both the head and main (9 passed each), and guards.py is unchanged, so I read it as a timing flake.
Failure scenarios 1 to 4 in specs/verdict-closed/spec.md are covered by the probe matrix and the parametrized tests: links (live or dangling), a -2 that already exists, a digit sha, and the race that ends in the copy-in refusal.
Confidence is high because the parser is unchanged and two independent differentials show 0 route moves and 0 attest moves. It would drop if some consumer outside cli/ parsed the refusal text.

## Residual risk
The format reference page (docs/site/reference.md) lags behind the charter. Gates only meet the new Probes rule through the charter or the refusal text.

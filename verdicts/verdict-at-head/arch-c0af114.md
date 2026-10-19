Verdict: PASS
Gate: arch
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: c0af1142c98228c41abd4ca28c1710d9e59df067
Confidence: high
Breaking: no (the delta changes only docs and tests; the patch call from bf88fb4 stands)

## Findings
- [low] blocks: no. On the site, "a newer head on the PR's line" is the term the same paragraph already uses for gates, and there it means what `newer` (evidence.py:252) computes: a strict descendant of the held verdict's head that is also an ancestor of the PR head. A reader who takes "newer" to mean later in time could expect a `Breaking: no` after a rebase to clear a yes from the head that was rebased away. It does not: a yes counts from any head (evidence.py:345, the same as main 5a33509:340), and only a descendant of that head clears it. This fails safe, since it holds more than the reader expects, and it was there before this PR. A later docs pass could write "a strict descendant of the yes's head" on the site too.
- [low] cli/wuwei/evidence.py:248 blocks: no. Carried. `ref` comes from the verdict body while the attest row records `pr`, so one fact has two sources.
- [low] blocks: no. Carried, and documented. A dropped PASS still shows only as the gate missing.

## Probes
- Read: PR via REST `repos/taoq-ai/wuwei/pulls/1152`: head c0af114, draft. Checks via REST `commits/c0af114/check-runs`: 8 of 8 success. Delta via `git diff bf88fb4 c0af114`: 3 files, +16/-3, nothing under cli/ or .claude/.
- closed: design.md:137 Breaking/Supersedes ambiguity at c0af114. design.md:137-139 now says a `Breaking: no` clears a yes "only from a strict descendant of that yes's head, and only for this PR or its repository alone; `Supersedes:` does not apply to it". That matches breaking_gaps (evidence.py:345), which goes through `newer` (different head, held head an ancestor of v, v an ancestor of the PR head) with `v['ref']` in (ref, repo) and reads no supersedes. It also matches the breaking_gaps docstring.
- Site against design.md: evidence.md:163-165 says "`Supersedes:` clears gates only: an arch `Breaking: no` clears a `Breaking: yes` only from a newer head on the PR's line, for this PR or its repository alone." "Newer head on the PR's line" is the site's existing term for the gate rule in the sentence before it, and both rules use the same `newer` function, so the site and design.md agree in the code's terms. The rebase reading is the low note above.
- closed: untested ESCALATE narrowing (evidence.py:300) at c0af114. Mutant E1 lets a later FIX replace a held ESCALATE at its head while still refusing a PASS that names it. I ran it in a fresh `git archive c0af114` copy, applied to both cli/wuwei and .claude/wuwei/cli/wuwei. It is killed: `test_a_later_fix_at_its_head_does_not_replace_a_held_escalate` fails (1 failed, 254 passed, tests/test_evidence.py).
- Mutant S1 drops the leading '/' in the Supersedes suffix match, in its own fresh copy and in both trees. It is killed by the new row `XI-1/quality-fix.md` of `test_a_pass_clears_a_finding_at_its_head_only_by_naming_it` (1 failed, 254 passed).
- Suite, `pytest -q` at the head copy: 2144 passed, 2 skipped. This matches the builder's count.
- Fitness: there is no runtime change, so the line count stays at 3,183 as measured at bf88fb4. No charter changed, so the agents cannot drift. guards.py and hook.py are untouched, so no parser probe is owed.
- Confidence is high: the delta is docs and tests only, I checked each docs claim against the code lines, and both new tests kill their target mutants.

## Residual risk
The create and ready doors still count a PASS from another PR of the item in the same repository (plan.json:79). A yes from a head that was rebased away cannot be cleared. Both fail safe and both were there before this PR.

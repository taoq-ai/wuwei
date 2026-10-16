Verdict: PASS
Gate: quality
Item: gate-rules
PR: taoq-ai/wuwei#1105
Head: dc733e0d49d3118fcdf7ad8e38cbb56087a71a51
Confidence: medium

## Findings
- [low] blocks: no. Acceptance 5 (planner.md line-budget check and free-lines-first order) and the lead, builder AUTH and sentinel-security rules 5 to 7 have no test pinning their text; only the four gate rules, the PR wording and the Stop wording are pinned. A later charter edit could drop them silently.
- [low] charters/_gate.md:13 blocks: no. The new rule 3 sentence is appended to an already long line (over 110 characters), so the rewrapped paragraph reads unevenly; cosmetic only.
- [low] blocks: no. The spec's How this fails 1 and Rollback say the runtime count stays 3,000; the measured count is 2,986 and is unchanged from main. The stale figure is a spec wording note, not a defect.

## Probes
- Suite at the head, copied by git archive into scratch: pytest -q gives 942 passed, 2 skipped.
- Red on main: copied the head's three changed test files onto a git archive of 247d72e; 6 fail (test_hook arm-watch wording, four test_setup sentinel parametrizations, test_verdict wording). The tests reach the real consumers: the built agents files, verdict.parse and FORMAT, and hook.stop.
- Guard reversal: the only changed strings are the verdict.py error text and the hook.py Stop line; no guard logic changed. Reversing either wording is caught by test_verdict and test_hook respectively (red on main above).
- Runtime lines: find cli/wuwei -name '*.py' | xargs cat | wc -l gives 2986, matching the stated count; the diff to cli replaces lines in place.
- Drift: diff -r charters .claude/wuwei/charters, cli/wuwei against .claude/wuwei/cli/wuwei, and agents against .claude/agents are identical (apart from the two json files that exist only in agents); the drift test passes.
- Charter consistency: the new main-worktree rule extends the existing scratch-copy rule in _common and _gate without contradiction; the Write-tool rule agrees with Boundaries 1; the stub rule only binds parsing claims and leaves the trust-boundary always-blocks sentence intact. The wording matches across _gate.md, verdict.py and docs/site/reference.md.
- Added lines contain no non-ASCII characters, so no emojis and no em dashes.
- Spec: specs/gate-rules holds spec, plan, tasks, analysis and checklist; the spec has the promise, How this fails (3 scenarios), clarifications, requirements FR-001 to FR-009, assumptions and rollback. Complete for full tier.
- Simplicity: none. The edits are text only; the one test with a loop over four roles and five phrases is the smallest way to pin the rules for every gate.

## Residual risk
Rules for lead, planner, builder and security are prose with no test, so they rely on review. The spec's stale 3,000 figure is cosmetic.

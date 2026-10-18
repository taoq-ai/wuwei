Verdict: PASS
Gate: security
Item: breaking-latest
PR: taoq-ai/wuwei#1135
Head: eb7cde7e34f7a4ed156ff578d979db8fc46b1ff1
Confidence: high

## Findings
- [low] blocks: no. Closed from 21d9ce3: the high finding at cli/wuwei/evidence.py:333 (CWE-636, a stale, foreign or off-line arch `Breaking: no` clearing a real break). At eb7cde7, F1 (older ancestor no attested last), F2 (non-ancestor head), F3 (other PR, other repo) and F5 now hold the announcement gap, the same as main.
- [low] blocks: no. Closed from 21d9ce3: the medium note about relaunching at one head. With strict descent, a later `no` at the same head as a `yes` clears nothing (P5).
- [low] blocks: no. Still open, as noted at 21d9ce3 and unchanged on main: editing an attested arch PASS that says `yes` drops it from verdicts() (P6c), and editing a sole FIX `yes` loses its Breaking field (P6b), though arch then has no pass.
- [low] blocks: no. Liveness, not a trust defect: a false-positive arch `yes` at the PR head can now be cleared only by a re-read at a new descendant commit, or by an announcement plus the owner's `breaking:` confirmation. Relaunching arch at the same head no longer works. This fails closed.

## Probes
- Delta read with git diff 21d9ce3..eb7cde7: evidence.py breaking_gaps (+4 runtime lines) and the vendored copy, byte-identical (diff), tests/test_evidence.py, and specs. No dependency, workflow or agent tooling changed.
- Suite in a git archive copy of eb7cde7: pytest -q gives 1699 passed, 2 skipped.
- My 24-probe differential, through the real hook.SubagentStop attestation, at eb7cde7 against main efcd9e7: 0 of 24 verdicts differ from main. P0 positive and P0n negative hold. The only intended move from main is the builder's acceptance case (yes at OLD, later no at the descendant HEAD, now clears), covered by test_breaking_is_read_from_the_latest_arch_verdict[said0-found0].
- New probes: when gh.ancestor raises GhError mid-read, gaps() returns "evidence unreadable: compare 502" (fails closed, against [] with a working read). A chain (yes at OLD, no at MID, no at OLD) clears through MID. A yes at MID followed by a no at the older OLD holds the gap.
- Mutants on the new guard, each in a fresh git archive copy, all killed:
  - dropping the same-head inequality: test_breaking_is_read_from_the_latest_arch_verdict[said2]
  - dropping descent from the yes: [said5]
  - dropping "ancestor of the PR head": test_a_no_on_a_dropped_descendant_of_the_yes_clears_nothing
  - dropping "a yes always sets": [said3] and [said4]
  - dropping "not said": 21 tests
- Heads are compared as strings. They come only from parsed verdicts (strict 40 lowercase hex) and from headRefOid, so the inequality and the compare URL take no free text. repo comes from the validated owner/repo#number ref.
- CI read once with gh api .../commits/eb7cde7/check-runs: CodeQL, ZIRAN, ziran-audit, both Analyze jobs, and test 3.11, 3.12 and 3.13 succeeded. The scanners were not re-run locally.
- The guard-parsing and normalisation standards lines do not apply (no command parser or path normalisation changed).
- Confidence high: every case from the FIX was re-run at this head through the real hook, and every new branch of the guard has a killing test.

## Residual risk
Seats still choose their own Head and Item lines, which the hook does not check against the brief. So an arch seat at a strict descendant of the yes's head on the PR line decides Breaking: the trust the arch gate already holds. An edit to an attested PASS `yes` still erases it, as on main.

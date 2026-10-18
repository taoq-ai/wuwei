Verdict: PASS
Gate: quality
Item: pr-draft-text
PR: taoq-ai/wuwei#1139
Head: 1bcbb4c01717ea7dd367a0f678cc5cfa6a083851
Confidence: high

## Findings
- [low] tests/test_guards.py:1272 blocks: no. Untested: the test checks substrings, so a contradicting sentence appended to the note (mutant "append-contradiction": `needs it. The PR never opens as a draft.` added to both copies) still passes. Nothing in the item's promise is let through, because the vendored-drift test and the equality test pin the note to the charter file, and a change to the charter is reviewed as a diff. If a fix is wanted later, assert on the whole paragraph after normalising whitespace.
- [low] tests/test_guards.py:1278 blocks: no. The once-per-session assertion repeats test_a_draft_opens_before_its_gates_with_the_pr_standard_once (28 parametrised cases). It does no harm.
- [low] blocks: no. How-this-fails scenario 2 holds as a limit. A non-draft `gh pr create` that create_door lets through at a gated head shows the same note (guards.py:255-256: found is None, then once()), and the note now says the PR opens as a draft. It is advice shown once and the create has already succeeded. The spec records this.
- [low] blocks: no. docs/site/concepts/evidence.md:86 has the heading "Gates before the PR, chosen by the diff". The body under it (lines 88-89) already describes the draft route, so only the heading is loose. It is outside this item's files.

## Probes
Suite at head in a `git archive` copy (pytest -q): 1685 passed, 2 skipped. The two skips are tests/test_release.py:36 and :57, skipped because ssh-keygen is absent. Neither touches this diff.
Targeted tests at head: the new test, test_the_pr_standard_note_is_the_charter_with_the_plugin_version, all 28 cases of test_a_draft_opens_before_its_gates_with_the_pr_standard_once and test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from all PASSED.
Mutants, each in a fresh `git archive` copy, scored on the three tests above (script under scratchpad/sentinel-quality-pr-draft-text/scripts/mut.py). 11 killed, 2 survived:
- old wording restored in both copies: KILLED by the new test. This also shows the new test fails against main's charter.
- negation "does not open as a draft": KILLED by the new test.
- "the builder requests": KILLED by the new test.
- the ready/shepherd clause dropped: KILLED by the new test.
- the before-merge clause dropped: KILLED by the new test.
- "Request a reviewer." added back: KILLED by the new test.
- "passed before it opened" added back: KILLED by the new test.
- stale vendored copy only: KILLED by the vendored-drift test.
- stale tree copy only: KILLED by the new test and the drift test.
- guards.PR_STANDARD pointed at _way.md: KILLED by all three tests.
- empty note reason: KILLED by all three tests.
- append-contradiction: SURVIVED, and survived again on a second run in a fresh copy. See the finding above.
- line rewrap only: SURVIVED. This is intended, because the test normalises whitespace and the meaning does not change.
Consumer: the new test calls guards.bash(root, 'gh pr create --draft', cwd, session), the same function pre_tool routes Bash through, and the PR_STANDARD file read is mutation-checked above.
End-to-end hook run: not run. The attempt to call `bin/wuwei hook PreToolUse` by hand was refused by the hook door ("a hand-made call would forge the record"). I did not try another way around it.
Grep at head with `git grep -n -i -E` across charters, agents, docs, skills, .claude/wuwei, README and AGENTS:
- "request a reviewer" and "before it opened" appear only in the new test's negative assertion (outside specs/).
- Every remaining reviewer mention gives the request to the shepherd after the flip to ready: shepherd.md:16-19, _way.md:11, builder.md:72, planner.md:62, wuwei-watch SKILL.md:26.
- The gate lines say "before the PR turned ready": _common.md:32, design.md:77, evidence.md:20.
- No text left tells a seat to request a reviewer at open, or says the gates pass before the PR opens.
Vendored copy: byte-identical to charters/_pr.md (same blob in the diff; the drift test passes). agents/ do not include _pr.md, so no agents build was needed.
Guard parsing probes and main-versus-head differential: N.A., because guards.py and hook.py are unchanged in this diff (diff stat: two charter copies, one test, spec artifacts).
Simplicity: none deletable. The three-sentence charter edit is the minimum the promise needs. The new test pins content and the existing equality test pins wiring, so they are not redundant, apart from the one repeated once-per-session line noted above.
Confidence reason: 11 of 13 mutants are killed, including every one the brief names (negation, a dropped clause, the old wording, a stale vendored copy). Both survivors are explained, and the full suite passes at the head.

## Residual risk
The note is advice shown once per session. A seat that skips it, or that opens a non-draft PR at a gated head, reads draft wording that does not match what it did. Neither case holds a merge.

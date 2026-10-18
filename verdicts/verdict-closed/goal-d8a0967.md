Verdict: PASS
Gate: goal
Item: verdict-closed
PR: taoq-ai/wuwei#1144
Head: d8a09671df6f45863316df639ea055e3f65e6993
Confidence: medium
Breaking: no

## Findings
- [low] blblocks: no. Drift beyond the promise, recorded by the builder as an assumption: the promise names only the shape refusal (hook.py:170-171), and the head also changes the copy-in refusal and the replaced-verdict refusal to name the free file (hook.py:156, hook.py:169), and rewords the charter's -2 sentence (_gate.md verdict paragraph) to stay inside the 2,250-word AGENT_WORDS ceiling. Each is the same fix for the same goal (a refusal names a file the seat can write) and is covered by a mutant (M5, M6) and a test. Note for review, not a block.
- [low] blocks: no. Probes is prose and is not machine-read: a seat that writes a wrong closed line under Probes is not checked, and acceptance 1 passes on main too (the parser never read Probes). Matches the item's recorded assumption; it is overturned only if the owner wants closures machine-read, which is a goal change and not asked for in #1118.
- [low] blocks: no. The Expected clause "the brief can say if refused write -2" is a planner-side change and is not in this diff; the hook-side half (the refusal names the next free file) is delivered. The planner brief text is outside the item.

## Probes
- Promise 1: `charters/_gate.md` rule 6 reads "Closed findings go under ## Probes (`closed: <finding> at <sha7>`); ## Findings holds only open findings, or none." and the verdict block says "(open findings only, or the single word none)" and "each closed finding" under Probes. grep of agents/sentinel-quality.md:140-141 and agents/sentinel-goal.md:139-140 shows the same text. `bin/wuwei agents check` at the head: agents match the charters.
- Promise 2: hook.py diff (`git diff 3d2eb29 d8a0967 -- cli`) replaces "Rewrite it in this shape" with "Write the corrected verdict to {free(path)} beside it (the next free number) in this shape". The word "Rewrite" no longer appears in the refusal.
- Acceptance 1, run with `verdict.parse(..., strict=True)` in a git archive copy: closed line under Probes and `none` under Findings gives errors []. Test `test_a_delta_verdict_with_its_closed_findings_under_probes_is_attested` drives the hook and records PASS attest.
- Acceptance 2, same parse: the line under Findings gives the shape error. Test `test_closed_findings_under_findings_name_the_next_free_file_to_write` asserts the refusal contains "Write the corrected verdict to quality-abc1234-2.md beside it" and not "Rewrite"; it passed in the suite.
- Acceptance 3: agents/sentinel-quality.md line 140 says "Closed findings go under ## Probes". Test `test_a_gate_puts_the_findings_its_fix_closed_under_probes` pins it.
- Issue #1118 Expected: first option (a section for closed findings plus charter sentence) is met; the third clause (a refused first file is reported with the reason and the expected next path) is met by the hook refusal naming the free file. The second option (ignore closed lines in the shape check) is not taken, matching "Outside: loosening FINDING"; `FINDING` and `parse` are unchanged in the diff.
- Suite at the head (`/root/.local/bin/pytest -q`, git archive copy): 1789 passed, 2 skipped. Body says 1789 passed, 2 skipped: matches.
- Red run (main code at 3d2eb29 with the head's tests/test_hook.py and tests/test_charters.py, `pytest -q`): 14 failed, 225 passed. Body says 14 failed, 225 passed: matches.
- Mutants (`specs/verdict-closed/mutants.py d8a0967`, each in a fresh git archive copy): M1 to M9 all killed (14, 2, 2, 7, 1, 1, 2, 1, 1 failing tests). Body says 9 of 9: matches, and the per-mutant counts match.
- Differential (`probe_differential.py` run at 3d2eb29 and at the head, then `compare.py`): corpus sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at both; routes 251 rows, 0 moved; payloads 7, 0 moved; hand-backs 232 cases, 124 refusal texts moved, 0 attest counts moved; head: 140 refusals name a next file, 140 free and attesting, holes 0; main: 72 named, 32 holes; outside file changed: False. Row counts by kind (8, 48, 12, 16, 16, 16, 8) sum to 124. All match the body.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` is 2986 at main and 2987 at the head, +1 equal to the item's budget of 1, under the 3,400 cap. `diff -r -x __pycache__ cli/wuwei .claude/wuwei/cli/wuwei` is clean. agents/sentinel-arch.md is 2250 words (`wc -w`), at the ceiling as the body says.
- Not run: the combinatorial bash probe and the normalisation probes. The change does not touch how a guard reads a command or normalises a path (hook.py changes are in `_verdict_problem` messages and a name helper), as the body states; I did not measure them.
- No finding closed since a previous verdict: this is the first goal round for the head.

## Residual risk
Two seats refused at the same moment can be told the same free number; the second hits the copy-in refusal, which names the next number, so no write is lost (builder's STATE note, consistent with the code). agents/sentinel-arch.md sits at the word ceiling, so the next _gate.md edit must pay for its own words.

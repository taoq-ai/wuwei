Verdict: PASS
Gate: quality
Item: verdict-closed
PR: taoq-ai/wuwei#1144
Head: d8a09671df6f45863316df639ea055e3f65e6993
Confidence: high

## Findings
- [low] charters/_gate.md:64 blocks: no. Untested prose (FR-002): reverting the verdict block's Findings line to "(or the single word none)" (X1) or its Probes line (X2) survives the whole suite, with only the vendored-copy drift test deselected. specs/verdict-closed/analysis.md says "the test reads the block's Findings line", and the data at this head does not support that: tests/test_charters.py:278-283 reads rule 6 and the paragraph only. One assert on each block line would close it.
- [low] cli/wuwei/verdict.py:19 blocks: no. Reverting the FORMAT note the refusal prints (X3) survives too. test_hook.py:432 checks that FORMAT appears in the refusal, not what it says.
- [low] tests/test_charters.py:278 blocks: no. The charter test checks for substrings. It kills a rule turned to Findings (M9, and X4 "## Findings holds closed findings too"), but a word-neutral qualifier that keeps every phrase survives (X5: "Wrong: Closed findings go under ## Probes ..."). Any prose test has this limit; I record it, it does not block.
- [low] cli/wuwei/evidence.py:316 blocks: no. Probe: a root-written shape refusal followed by the corrected -2 now leaves the malformed base file on disk. evidence.uncounted lists it as "verdict .../quality-abc1234.md not counted: finding not in the shape ..." (kind safety, actionable) whenever another gate is still missing. On main, "Rewrite it" fixed the file in place for root writers, so this noise is new for them. Worktree writers already got it on main. This is a limit, not a merge hold: uncounted is only appended to a missing-gate gap.
- [low] charters/_gate.md:48 blocks: no. Clarity: the tightened paragraph says "write yours beside it as `-2.md`" where main gave the full `<gate>-<first 7 of head>-2.md`. A literal reader could write a file named `-2.md`. Both hook refusals name the full free file, so a seat that misreads is corrected at the hand-back.
- [low] blocks: no. agents/sentinel-arch.md is at 2,250 words, exactly the AGENT_WORDS ceiling (main: 2,245). The next _gate.md word fails test_a_generated_agent_stays_under_the_word_ceiling[sentinel-arch] loudly (my X4 and X5 first draft tripped it). That is the designed steward trigger, not a silent trap, but the next charter change starts with no headroom.

## Probes
Suite at head (git archive into a scratch folder, /root/.local/bin/pytest -q): 1789 passed, 2 skipped. Main 8c1939e: 1774 passed, 2 skipped (15 new tests). Head merged with current main b28a3dc (merge-tree, clean): 1792 passed, 2 skipped.
Builder mutants (specs/verdict-closed/mutants.py d8a0967, each in a fresh archive): M1 to M9 all killed, with the same failing counts as the PR (14, 2, 2, 7, 1, 1, 2, 1, 1).
My mutants, each in a fresh archive, full suite minus the vendored-drift test: X4 (Findings holds closed too) killed by test_a_gate_puts_the_findings_its_fix_closed_under_probes. X6 (copy-in refusal computes free from the worktree side) killed by test_the_other_refusals_that_say_write_beside_it_name_the_next_free_file_too. X7 (shape refusal back to "Rewrite it") killed by test_closed_findings_under_findings_name_the_next_free_file_to_write. X8 (charter refusal sentence reverted) killed by the charter test. X1, X2, X3 and X5 survived, and survived again in a second fresh copy.
Consumers: the new tests drive hook.handle SubagentStop through _verdict_problem and check ws.rows attest. The end-to-end test writes the named -3 from a worktree and sees it attested. The charter test reads charters/_gate.md and the generated agents/sentinel-quality.md.
Differential (the committed probe_differential.py at main 8c1939e and at the head, compare.py): corpus sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at both. Routes: 251, 0 moved. Payloads: 7, 0 moved. Generated hand-backs: 232, with 124 refusal texts moved and 0 attest counts moved. Head: 140 refusals name a file, all 140 free and attesting, 0 holes. Main: 72 named, 32 holes. No outside file changed. These match the PR body table row for row.
Guard parsing probes: not applicable. No guard or command parsing changed (the brief's standards line asks only for the differential, re-run above).
Runtime lines (cat cli/wuwei/*.py | wc -l): 2986 to 2987, +1, within the item's budget of 1. Vendor diff clean. bin/wuwei agents check: agents match the charters.
Engineering: the assigned lambda with noqa E731 follows the precedent at evidence.py:438. The stem-strip regex matches only a trailing -N after 7 hex, so no gate name (arch, quality, security, goal) can trip it. With 997 numbers taken, next() raises and the hook fails open, which is still unattested and so safe.
Simplicity: none. free() is the smallest correct form: a bare `<stem>-2.md` leaves the 32 main holes the differential shows, and the regex strip is what stops -2-2.
Confidence high: every changed code expression has a killing mutant, and the differential reproduces. What is left is untested prose in the verdict block and the FORMAT note.

## Residual risk
The verdict block lines and the FORMAT note can drift without a test failing. An abandoned malformed verdict now shows as "not counted" next to a missing-gate gap for root writers.

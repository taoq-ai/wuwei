Verdict: PASS
Gate: goal
Item: gate-rules
PR: taoq-ai/wuwei#1105
Head: dc733e0d49d3118fcdf7ad8e38cbb56087a71a51
Confidence: high

## Findings
- [low] specs/gate-rules/spec.md:47 blocks: no. The spec, checklists/requirements.md:5 and plan.md:20 still say the runtime is 3,000 lines; after the merge of #1104 it is 2,986 at both base 247d72e and head (tasks.md:20 was corrected, the others were not). The acceptance holds; the spec text is stale.
- [low] tests/test_setup.py:1 blocks: no. Import reorder and a blank line outside the promise; cosmetic, needed only for the new pytest import.

## Probes
- Read the promise and 5 acceptance lines with python3 over .wuwei/plan.json (id gate-rules) and goal G-1 in .wuwei/goals.md.
- git diff 247d72e dc733e0 -- charters cli docs tests: rule 1 in _common.md Evidence 4 and _gate.md rule 3; rule 2 in _gate.md The verdict; rule 3 in _gate.md rule 3; rule 4 in _gate.md rule 4; rule 5 as sentinel-security.md rule 6; rule 6 in builder.md AUTH; rule 7 in lead.md Scope and tier 3 and planner.md The day 3. All seven landed where the promise says.
- Wording: grep shows '<owner/repo> alone before its draft PR exists' at _gate.md:52, verdict.py:11 and :48, reference.md:79; grep for 'before the PR opens' over charters agents cli docs finds nothing left. hook.py Stop line says 'unless a check-in or PR subscription is armed, which WUWEI cannot see'.
- git archive dc733e0 into scratch; pytest -q: 942 passed, 2 skipped.
- Acceptance 1: bin/wuwei agents build in a copy printed 'agents match the charters', diff -r agents shows no drift; test_the_generated_agents_match_the_charters and test_every_gate_carries_the_worktree_write_mutant_and_stub_rules[arch, goal, quality, security] PASSED. agents/sentinel-security.md:167 holds the normalisation round, agents/builder.md:166 the route corpus, agents/lead.md:140 the budget.
- Acceptance 2: test_a_verdict_written_before_the_pr_opens_names_only_the_repository and test_the_pr_line_wording_says_gates_run_before_the_draft_pr_exists PASSED.
- Acceptance 3: test_waiting_work_with_no_watch_armed_asks_once_to_arm_it PASSED with the new wording asserted.
- Acceptance 4: cat cli/wuwei/*.py | wc -l gives 2986 at base 247d72e and 2986 at head.
- Acceptance 5: charters/planner.md The day 3 names the budget check against headroom (3,000 minus measured lines) before the approval question and the free-lines-first order.
- Scope: diff --stat lists only charters, agents, cli/wuwei hook.py and verdict.py wording, reference.md, specs/gate-rules, three tests and the .claude/ re-vendor (diff -r shows .claude/wuwei/charters and cli/wuwei identical to the sources, FR-009, same practice as #1102). No guard or evidence code changed; nothing on #1078's attestation path.
- Explain-back in spec.md matches the promise rule by rule and all five acceptance lines.

## Residual risk
The rules are prose; whether seats follow them is only observable in later verdicts. Stale 3,000 figures in the spec could mislead a later reader about headroom.

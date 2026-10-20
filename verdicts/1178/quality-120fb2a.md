Verdict: PASS
Gate: quality
Item: 1178
PR: taoq-ai/wuwei#1188
Head: 120fb2a0f037e5c5cd065d34be7cce17f6cc0a1d
Confidence: medium
Breaking: no
Supersedes: none

## Findings
none

## Probes
Confidence reason: every changed guard has a killing behavioural test on both runtime copies; medium because the change is small and I did not diff the docs wording against the five acceptance docs beyond reading the diff.
Suite at the head, in a git archive copy, offline gh on PATH, CLAUDE_CODE_SESSION_ID unset, no -x: 4 failed, 2829 passed, 1 skipped. The 4 failures are the known bash 3.2 ones (test_codex hook shell, three test_bash_runs_the_push_in_each_refused_shape cases), the same set the brief names as failing on main.
CI at the head (gh pr view 1188 statusCheckRollup, read once): test 3.11/3.12/3.13, CodeQL, Analyze x2, ZIRAN, ziran-audit all SUCCESS.
Acceptance 1 and 2: test_the_old_item_line_alone_is_process_fit_that_names_the_footer asserts the old line alone gives exactly one gap of kind process, that visible and blocking are empty, and that a footer alone, old line then footer, and footer then old line give none. test_the_old_item_line_shows_on_the_full_board_only asserts it is in board.compute(root, True) and not in the default board.
Acceptance 3: test_an_unlinked_draft_by_the_session_login_shows_as_unplanned has a draft by the session login (listed) and a draft by someone else (not listed).
Acceptance 4: test_a_merge_flows_past_process_gaps_and_records_them now expects the gap first in merge.checked process, with the merge allowed.
Mutants, each applied to both cli/wuwei and .claude/wuwei/cli/wuwei in a fresh archive copy, vendored-copy test deselected, one suite at a time; a kill is a behavioural test failing:
- remove the old-line check: killed by test_evidence old-line test, test_review_request old-line test, test_guards merge-flows test.
- all() to any(): killed by the test_evidence old-line test (old line plus footer body).
- invert the startswith test: killed by the old-line test and many gap-list tests (test_complete_evidence_has_no_gaps and others).
- drop the empty-links guard (a body with no link gets the old-line gap): killed by test_gaps_are_classed_as_process_or_safety and test_upgrade::test_an_imported_pass_needs_only_a_delta_gate.
- drop the new alternative from PROCESS (gap would turn safety and hold the merge): killed by the old-line test, the board test and the test_guards merge-flows test.
- restore the isDraft skip in board.adopted: killed by test_an_unlinked_draft_by_the_session_login_shows_as_unplanned.
- break the ITEM old-line alternative (WUWEI-Item: no longer links): killed by test_watch (two tests), the old-line test and the board test, so old-line linking stays covered outside make_pr.
make_pr fixture change: the default body moved from the old line to footer(); old-line linking is still driven explicitly in test_watch.py, test_breaking.py, test_hook.py, test_status_perf.py and test_guards.py, and the footer path by test_the_wuwei_footer_links_a_pr_to_its_item. The ITEM mutant above shows the old-line path is still killed. No coverage lost.
Replay case: the recorded PR #57 body is the old line alone (WUWEI-Item: I-7). The new expectation (process, actionable, not owner) is correct, and it sits before the 780-line row in the order evidence.gaps emits; test_a_recorded_case_gives_the_same_gaps passes and compares text, actionable and owner in order.
Docs: AGENTS.md, CONTRIBUTING.md, README.md, constitution, design.md and reference.md now ask for the footer and name the old line as still accepted. charters/_pr.md exists as AGENTS.md says.
Simplicity: none. The walrus plus all() is the shortest form that treats a body with no link as not-this-gap, and the guard is test-covered; the footer() helper replaces 40 inline literals; the isDraft clause removal is a pure deletion.

## Residual risk
origin/main has moved since the base (1f074e79 touches evidence); the plan notes #1176 and #1177 edit the same replay case, so a rebase may conflict on case.json. wuwei evidence lists only the quality and security gates as missing, which this and the security verdict close.

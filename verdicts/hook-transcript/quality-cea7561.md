Verdict: PASS
Gate: quality
Item: hook-transcript
PR: taoq-ai/wuwei#1172
Head: cea75615de1231b0080b70dd34180efb1da12107
Confidence: medium
Supersedes: .wuwei/verdicts/hook-transcript/quality-018548a-2.md

## Findings
- [low] cli/wuwei/hook.py:279 blocks: no. `answer.pending` is written for every answer, confirmed or not, and nothing reads it back (the builder discloses this under Assumptions). It is a ledger row with no consumer; a later item should read it (board or report) or drop it.
- [low] tests/test_hook.py:1391 blocks: no. The merge-as-next-call test stands in for the evidence engine with a patched `evidence.gaps` that returns no gap once any ruling exists. I ran the same flow unmocked (scratch copy, a declared-breaking PR with the real `evidence.gaps`, the arch, quality and security gates attested, a `breaking:` question, PostToolUse before the answer row, row appended, then `gh pr merge 42 --repo acme/app --squash`): the merge passes (`out is None`) with one breaking ruling. So the patched test does not hide a gap, but it would not catch a ruling shape the real gate ignores.
- [low] tests/test_hook.py:1160 blocks: no. Carried from the last round: the 18 FORGE_SHAPES never reach the code, so the forge tests repeat 7 and 5 distinct cases. Kept as the owner's ruling.
- [low] cli/wuwei/hook.py:335 blocks: no. Carried: an entry older than 7 days reads as `{}`, and a Stop records `answer.unconfirmed` with no id. Harmless, untested.
- [low] cli/wuwei/hook.py:330 blocks: no. Carried: at a Stop each pending answer waits up to WAIT on its own, so N pending answers can wait N x 1.5 s.
- [low] cli/wuwei/hook.py:335 blocks: no. The cache glob `answer-<session>--*` lets session `a` also match entries of a session named `a--b`. The transcript still has to show the answer, so nothing false is recorded; session ids are harness UUIDs.

## Probes
Head cea75615de1231b0080b70dd34180efb1da12107, own `git archive` copy under `<scratchpad>/quality-hook-transcript/`. Delta read with `git diff 018548a cea7561` (it also holds the merge of main d4a803f: evidence.py, board.py, gh.py, test_status_perf.py and cache_prune are main's, not this item's).

Closed findings:
- closed: merge as the next call (high, hook.py:478) at cea7561. `handle` now confirms the planner's pending answers before the handler on PreToolUse and Stop. `test_an_answer_is_recorded_before_the_merge_door_that_is_the_next_call` is in the measured order (PostToolUse with no row, row appended, merge next). Red on fbf3c4e's hook.py, killed by mutant F1 (answers recorded after the door; also 2 other tests), and green in my unmocked run with the real gate (see the note above).
- closed: H11 flake (medium, test_hook.py:1347) at cea7561. The test now swaps `hook.time` for `SimpleNamespace(monotonic=time.monotonic, sleep=late)`. H11 (`end = time.monotonic()`) run on that test alone 22 times under load average 5 to 6: killed 22 of 22, each time by `assert len(ws.rows(root, 'ruling')) == 1` (0 == 1). The kill is by construction: with no wait the loop never reaches the fake sleep, and subprocess no longer calls it. Also killed in the pass over test_hook.py, test_codex.py and test_models.py.
- closed: filename sanitiser (medium, hook.py:279) at cea7561. `test_a_tool_use_id_never_names_a_file_outside_the_cache` kills X1 (run once on both copies at the same time, once on cli only: killed by that test). It passes on the old code, as the PR says, because the sanitiser already existed.
- closed: getpwuid KeyError (medium, ws.py:19) at cea7561. `test_a_uid_with_no_passwd_entry_keeps_the_doors_and_records_answers_unconfirmed` runs the real module entry with `pwd.getpwuid` raising. Red on fbf3c4e's ws.py (exit 1, the KeyError traceback), green at the head; killed W2 (the except catches ImportError) and W3 (a real fallback folder).
- closed: wait test upper bound (low) at cea7561. Only `>= 1.0` is left.

Mutants (specs/hook-transcript/mutants.py at the head, my runner from `git archive cea7561`, one tree per mutant, wall-clock bodies deselected, H9 with the goal-met probe deselected, behavioural kills only):
- Both runtime copies edited at once: F1 killed by 3, F2 by 2, F3 by 1 (`test_a_replayed_answer_records_nothing_more`), F4 by 1, X1 by 1, W2 by 1, W3 by 1, H9 by 2 (`test_the_real_flow_records_..._after_the_harness_writes_it`, `test_two_racing_planner_calls_record_an_answer_once`), H10 by 1 (the race test), H11 by 1, H12 by 2, H18 by 1, H19 by 1. 13 of 13 killed.
- `cli/wuwei` only: F1, F2, F3, X1, W2, H9, H10: 7 of 7 killed by the same tests.
- `.claude/wuwei/cli` only: F1, F2, F3, X1, W2, H9, H10 survive every behavioural test (0 failures), as AGENTS.md says, and the vendored-drift test kills them (`tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from`, shown on the F2 edit).
- Red on fbf3c4e's hook.py and ws.py with the head tests: 6 of the new tests fail (merge as next call, refusal notes, pending row, hook.error, replay, no passwd entry); the sanitiser test passes there, as the PR says.

Wall-clock detector change (mutants.py): it now counts a Call to `time.monotonic` or `time.perf_counter` instead of any reference. I ran the old and the new detector over test_hook, test_codex, test_models and test_guards: the deselected sets differ by exactly one test, `test_a_stop_records_an_answer_row_the_harness_writes_within_the_wait`, which now only passes the clock on and takes a fake sleep, so it measures no time. The 8 other deselected tests (the wait test and the 7 linear-time guard tests) are unchanged. No real wall-clock test got in. A call through an alias (`from time import monotonic`) would escape the detector; grep finds none in these files.

Suite and counts:
- Full suite `/root/.local/bin/pytest -q` (3.13): 2685 passed, 2 skipped. Python 3.11 (`uv run --no-project --python /usr/bin/python3.11 --with pytest pytest -q`): 2685 passed, 2 skipped. 3.12 not run.
- Vendored: `diff -r -x __pycache__ cli .claude/wuwei/cli` empty. Runtime lines `wc -l cli/wuwei/*.py`: 3,292 (cap 3,400; main d4a803f 3,208).

Route differential (AGENTS.md; guards.py, routes.json and test_guards.py are unchanged between 018548a and cea7561, so 0 routes move this round): corpus sha256 at the head 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49 (263 routes), main d4a803f 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 (257). All 263 read through `guards.bash` and the PreToolUse hook at both trees (the item's `probe_differential.py` and `compare.py`): 4 move, each its own row, all pass -> deny: `cd ~/.claude/projects/-repo && printf x >> s.jsonl`; `echo x >> ~/.claude/projects/-repo/s.jsonl`; `env -C ~/.claude/projects/-repo tee -a s.jsonl`; `tee -a ~/.claude/projects/-repo/s.jsonl`. No refusal names another PR or repository. The 30 checks without door words: 6 move, each behind a first segment that writes the transcript (curl with a token or the canary, helm, kubectl, nc, terraform: now refused for the transcript first). The same as the PR body says.
- Not re-run: the generated write probe and the real-entry probe. guards.py and the parser are unchanged since the last round.

Stale claims: none found. "H11 12 of 12" holds (22 of 22 here), "2685 passed, 2 skipped on 3.13 and 3.11", "3,292", the corpus hashes, the 4 moved routes and the vendored match all hold. Older body lines ("223 failed, 183 passed" and "+22 budget") were already noted at 018548a and the budget is disclosed.

Simplicity: the 18 FORGE_SHAPES can go (a shape-less parametrisation of the 7 and 5 cases kills the same mutants); `answer.pending` has no reader. Nothing in the runtime can be deleted: every new branch has a behavioural kill, and the sanitiser, the claim by `unlink`, the uid fallback and the replay check are trust-boundary or data-loss safeguards.

Confidence: medium. The four blocking findings are closed with kills I ran myself in fresh copies, and the real-gate run backs the ordering fix; the transcript format and the timing still rest on one harness version and one timed flow, and I did not re-run the 1,527-command write probe.

## Residual risk
The harness's row order (written after PostToolUse returns) was measured on one flow; if a harness release changes it, answers record at PostToolUse or unconfirmed, loudly. A session that never calls again leaves only an `answer.pending` row that nothing reads.

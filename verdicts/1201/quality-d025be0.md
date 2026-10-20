Verdict: PASS
Gate: quality
Item: 1201
PR: taoq-ai/wuwei#1204
Head: d025be050e4a4e53cc32c0e6bfa09117d90b6f2a
Confidence: medium
Breaking: no
Supersedes: 1201/quality-7ba5f67.md

## Findings
- [low] cli/wuwei/board.py:121 blocks: no. A status of "" reads "run: job " instead of "job state unreadable" if the `and s` part of the guard is dropped (mutant `isinstance(s, str)` alone survives); the case is untested but no unreadable file reads done, so it is a note.
- [low] cli/wuwei/board.py:117 blocks: no. A huge job file is read whole with no size cap and the status string is echoed unbounded into the run row; the path is one the planner registered, so these are notes carried from the earlier round.
- [low] blocks: no. Still untested and not blocking, carried from the earlier round: a relative --job path joined to the workspace root, stripping "[" "]" from a handoff word, and storing reason None when only --job is given.
- [low] tests/test_plan.py:230 blocks: no. codex_job repeats `import json` although the module now imports json at the top; harmless.

## Probes
- closed: nested arrays in status or result.rawOutput crash board.job on Python 3.14 (CWE-674) at d025be0. Mutant taking rawOutput without the str check is killed by test_an_unreadable_codex_job_file_never_reads_done[nested-rawOutput] on 3.14.5; mutant taking status without the str check is killed by [{"status": ["running"]}] and [nested-status] on 3.14.5 (2 failures) and by the list-status case on 3.13.
- Delta read: d025be0 against 892359d (the merge of main) changes only board.py job() (both copies), tests/test_plan.py and specs/codex-job-state/tasks.md. job() takes rawOutput only when str and status only when a non-empty str; every other shape reads "state unreadable".
- Conflict resolution against main 40b5fb5 (#1205): board.py keeps the `taken` PR-not-linked branch and the run-row join with job(); __main__.py keeps `--pr` in the option loop beside `--job`; plan.py and tests/test_watch.py match main; `git diff 40b5fb5 d025be0 --stat` shows no stray change to #1205's files besides the intended ones.
- Tests: tests/test_plan.py, 44 passed under uvx Python 3.13 and 44 passed under /opt/homebrew/bin/python3.14 (3.14.5, python3 here), PATH offline-gh, CLAUDE_CODE_SESSION_ID unset, in a git archive copy of d025be0. Full suite under 3.13: 3025 passed, 1 skipped, 4 failed; the 4 are the known bash 3.2 ones (test_the_hook_commands_run_under_either_harness_shell and three test_bash_runs_the_push_in_each_refused_shape cases), none in the diff.
- Mutants, applied to both cli/wuwei/ and .claude/wuwei/cli/wuwei/, run one at a time on tests/test_plan.py and tests/test_upgrade.py, each in a fresh copy: 20 mutants under 3.14.5, 18 killed by a behavioural test, 2 survive. Killed: completed guard (2), endswith('?') (3), OSError dropped (1), top-level dict guard (20), result dict guard (9), rstrip (1), [-1:] to [:1] (1), 'state unreadable' to 'done' (8), handoff word filter (5), "job " prefix (20), job not joined into the row (20), `--reason or --job` (10), job not stored (20), status key (12), rawOutput key (3), backtick strip (1), paren replace (1), plus the two str guards above. Survivors: the non-empty status part (the low note above) and RecursionError dropped from ws.read_json, which on 3.14 is unreachable for these files because the parser accepts 100000-deep arrays; under 3.13 that mutant is killed by [nested-200KB] and the raw-str mutant survives (its parser refuses first), so the two interpreters cover each other.
- CI at d025be0, read once with gh pr checks: test 3.11, 3.12, 3.13, ziran-audit, ZIRAN, CodeQL and both Analyze jobs all pass. mergeStateStatus CLEAN; the PR is still a draft. wuwei evidence names quality as the only missing gate at this head.
- Runtime budget: cli/wuwei/*.py is 3362 lines at the head (cap 3,400); the vendored copy matches cli/wuwei (diff -r shows no difference).
- Corpus/guard route differential: not applicable, no change to guards.py or hook.py.
- Expected rows in the new cases follow what the interpreter in use parses, and the test reads that from json.loads itself, not from a version check; the test does not depend on the clock, the network or ordering.
- Simplicity: none to delete. job() is dense (two chained walrus lines) but one function with one caller; ws.read_json remains the single reader shared with upgrade.py.

## Residual risk
CI covers 3.11 to 3.13, so the 3.14-only crash path is guarded by the str checks and a test that is red only on 3.14; a local run on 3.14 shows it. The job shape rests on a fixture copied from one real file; a companion release that renames status or result.rawOutput reads "job state unreadable", which fails safe.

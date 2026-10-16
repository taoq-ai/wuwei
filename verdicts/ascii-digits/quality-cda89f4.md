Verdict: PASS
Gate: quality
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: cda89f41f7dae59165e7dddac94ba50e2a6a6be9
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:246 blocks: no. The `answer` guard in the merged ruling reader has no test: dropping `answer and` leaves the suite green except the vendored-copy check (same gap on main for the owner review path). An empty answer would record an approved:false ruling. Missing test: a question with an empty answer records nothing.
- [low] cli/wuwei/hook.py:246 blocks: no. `and found[1]` is untested: dropping it survives in a copy. Input `owner review: #7 at abc1234` would record pr `None#7`, but guards.pre_tool already denies a classed question without the owner/repo#n shape, so the input cannot be asked. Missing test: a repo-less ref records nothing.
- [low] tests/test_setup.py:73 blocks: no. The scan is line based: it misses `a.isascii() and b.isdigit()` (guard on another value), `.isdigit()` on a continuation line, `map(str.isdigit, xs)`, getattr, and `isdecimal`/`isnumeric`. It is not fooled the other way: `'\\d'` in a string and `[\d]` are flagged (false positive, safe). The code at the head holds none of these.
- [low] specs/ascii-digits/spec.md:1 blocks: no. Spec is complete (spec, plan, tasks, analysis, checklist; Rollback, Assumptions, Clarifications, How this fails, Breaking none). The recorded behavior change (owner review read by class prefix, case-insensitive) is named under Assumptions.

## Probes
- Full suite at head (git archive copy, pytest -q): 964 passed, 2 skipped; the same 2 skip on main. Reproduced.
- Head tests on main code: 7 failed, 957 passed (refs, evidence CLI x2, hook ruling x2, scan, verdict PR line). The new tests are red on main and reach the real consumers (hook.handle, cli.main, verdict lint, evidence.refs).
- Mutants, each in a fresh copy of head, `\d` put back: evidence PROCESS, REF, VERSION_LINE, DEFERRED; guards open-days and #n shapes; hook pull, thread, REF; verdict FINDING and PR; upgrade days. Each is killed by the scan test. Behavior tests also kill evidence REF (test_refs), hook REF (test_hook), verdict PR (test_verdict). The other `\d` mutants are killed only by the scan, which is the stated guard.
- Mutant, `isascii()` dropped in __main__._ref: killed by the evidence CLI test (o/r#７).
- Mutants on hook._answers: drop the breaking `kind` key (test_breaking, test_hook), always add `kind` (test_an_owner_answer_becomes_a_ruling, test_hook), breaking only (test_hook, test_an_owner_answer), owner review only (test_breaking), `approved` forced true (killed). Survivors: `and found[1]` removed and `answer and` removed; both re-run in fresh copies, listed as notes above.
- Runtime lines at head: 2,988 (cat cli/wuwei/*.py | wc -l); main 2,992, so not higher.
- Vendored copy: diff -r cli .claude/wuwei/cli is empty; test_the_vendored_plugin_matches passes.
- Emoji and em dash: no U+2014 in cli, the changed tests or specs/ascii-digits; the only non-ASCII in the spec is the intended fullwidth and Arabic digit examples.
- Confidence medium: suite run only through pytest in a copy; gh/CI state not read.
- Simplicity: none; the merged REF reader already removed one pattern and the branch (-4 lines against main). The `[0-9]` edits are the minimum.

## Residual risk
New numeric readers can slip past the line scan in forms listed above; the guard on empty answer in the merged reader rests on no test.

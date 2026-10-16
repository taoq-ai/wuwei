Verdict: PASS
Gate: goal
Item: vendored-drift
PR: taoq-ai/wuwei
Head: 8b188da0299289caf82c973235508077c7cdeeb0
Confidence: high

## Findings
- [low] release-please-config.json:17 blocks: no. Acceptance 3 is shown by the config test (exact path and jsonpath) and by a simulated bump, not by a real release-please run; the first release PR after merge is the live check.
- [low] docs/adr/0001-cut-1.2.1-before-1068.md:10 blocks: no. The Context gives the alternative as "wait for 1068 and ship all three together"; the ledger question (.wuwei/ledger/388e50a5.jsonl) asked only "cut release 1.2.1 now?" with that recommendation. The paraphrase is fair; the decision, the answer "Cut 1.2.1 now", the 1065/1067 fixes and 1068 as 1.2.2 match the ledger word for word.
- [low] tests/test_setup.py:137 blocks: no. 1068 is not merged yet, so the item's "1068 included" is not delivered here; the test makes the 1068 PR carry its re-vendored copy, which is the promise.

## Probes
- `wuwei plan show vendored-drift` and .wuwei/goals.md read; item serves G-1 (WUWEI runs on itself), and the copy at the head runs this repo's hooks (.claude/settings.json calls "$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei).
- Detached checkout of the head: `.claude/wuwei/bin/wuwei --version` prints 1.2.1, the same as `bin/wuwei --version` and root .claude-plugin/plugin.json (acceptance 4, 1.2.1 at the head).
- `diff -r -x __pycache__ cli .claude/wuwei/cli` and `diff -r charters .claude/wuwei/charters`: identical, so merged fixes #1070 and #1071 are in the vendored copy.
- Full suite in a venv at the head: 292 passed (includes runtime size test; `wc -l cli/wuwei/*.py` totals 3000, no cli/ lines changed; acceptance 5).
- Mutant: append a line to .claude/wuwei/cli/wuwei/evidence.py: drift test fails naming 'wuwei/cli/wuwei/evidence.py' (acceptance 1).
- Main's .claude/ restored on the head's tests: fails naming plugin.json, evidence.py, gh.py, setup.py (SC-001).
- Simulated release bump of both plugin.json to 1.2.2: tests/test_setup.py 19 passed; root only bumped: 2 fail; release-please entry for the copy removed: 1 fails (acceptance 3 guard).
- test_the_drift_check_names_a_changed_vendored_file covers a fresh vendor() run passing (acceptance 2), extra files, a removed agent, a project's own agent and skill, and __pycache__.
- Explain-back in specs/vendored-drift/spec.md matches the promise and all five scenarios; no out-of-scope change (vendor(), symlink, doctor untouched).
- ADR checked against the owner's answer in .wuwei/ledger/388e50a5.jsonl.

## Residual risk
release-please behaviour on a dotted .claude/ path is asserted from config, not exercised; if it skips the copy the first release PR goes red and says why.

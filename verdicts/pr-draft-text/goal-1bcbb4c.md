Verdict: PASS
Gate: goal
Item: pr-draft-text
PR: taoq-ai/wuwei#1139
Head: 1bcbb4c01717ea7dd367a0f678cc5cfa6a083851
Confidence: high

## Findings
- [low] blocks: no. The spec's How-this-fails 2 says a non-draft create is "let through at a gated head"; guards.OPEN allows a ready create only once the gates pass, so the note's draft wording is advice for the normal route, as the Assumptions say. No drift from the issue.
- [low] blocks: no. The kept sentence "A delta after review fixes is re-read when it needs it." is not named in the promise or the issue's Expected. It is true (matches _common.md Done) and recorded under Assumptions; not a claim the requirement forbids.

## Probes
- Trace: issue #1132 Expected -> promise (charters/_pr.md:20-22) -> charters/_pr.md lines 20-22 at the head read "The PR opens as a draft so CI runs, and the gates the diff needs read the draft head. It turns ready once they pass, and the shepherd requests the reviewer then. Before merge, CI is green and every review thread is answered." All four promise points present; "Request a reviewer" and "before it opened" absent. Read with `git archive 1bcbb4c | tar -x` and `grep -n "" charters/_pr.md`.
- Explain-back: the PR body's promise and acceptance restate the item's promise and both scenarios correctly; no outcome missing, no unrequested claim.
- Acceptance 1: `pytest -q tests/test_guards.py -k pr_standard_note` at the head: `2 passed, 1192 deselected`. The new test calls guards.bash for `gh pr create --draft`, holds the three sentences, refuses "request a reviewer", and checks once per session. Against the old charter (efcd9e7 _pr.md in the copy): `1 failed, 1 passed, 1192 deselected`, matching the body.
- Acceptance 2: full `pytest -q -W error` at the head in the git archive copy: `1685 passed, 2 skipped` (body count matches); the vendored-drift test is in that run. `cmp charters/_pr.md .claude/wuwei/charters/_pr.md` identical.
- `sh bin/wuwei agents build` at the head: "agents match the charters"; `git diff efcd9e7 1bcbb4c --stat -- agents` empty. No agent includes _pr.md.
- Counts read live: `wc -l cli/wuwei/*.py` = 2976 at the head and at efcd9e7 (runtime 0 lines, matches body). `git diff --name-only origin/main...origin/pr-1138` shares no file with this diff (count of matches 0), matching the body's claim.
- Consistency with outside text: charters/builder.md:69-73 (draft, gates read the draft head, turns ready after) and charters/shepherd.md:14-19 (reviewers requested after the flip) agree with the new paragraph.
- CI at the head via REST check-runs: CodeQL, ZIRAN, ziran-audit, test 3.11, 3.12, 3.13, Analyze (actions), Analyze (python) all completed success.
- Authorship: git log efcd9e7..1bcbb4c is Leone only.
- Mutants: not run by me; the change is charter text, no guard or validation changed (guards.py untouched). Builder's five mutants not re-run. Parser probes: N.A. (no parsing change).

## Residual risk
A seat with no shepherd leaves the ready PR without a reviewer; this is process fit and held by the planner running the shepherd. The test pins whole sentences, so a later rewording needs a deliberate test edit.

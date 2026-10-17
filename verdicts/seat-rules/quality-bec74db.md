Verdict: PASS
Gate: quality
Item: seat-rules
PR: taoq-ai/wuwei#1111
Head: bec74db0c78b9f3f2b2812a77589d37427dffea6
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. The tests assert exact phrases from the charters, so they hold the wording and not the behavior. That is expected for charter text. A reflow of a phrase is absorbed by the whitespace-flattening helper, but a reword fails the test.
- [low] blocks: no. Builder and gate text use "door program" and "door words", which are WUWEI terms. The text glosses "door program" (the guarded program the stub stands for) and gives examples for door words, so it reads acceptably in other products.

## Probes
- Archived head into a scratch dir and ran `pytest -q`: 1198 passed, 2 skipped. The 2 skips are not in the changed tests.
- Archived main 9d6701e with the head's tests/test_setup.py and ran `pytest -q tests/test_setup.py`: 6 failed, 29 passed. The 6 are the new tests (builder and security parametrized, gates, equivalence, planner, steward), so they are red on main.
- Copied the head archive and ran `bin/wuwei agents build`: "agents match the charters". `cmp` of agents/, .claude/agents/ and .claude/wuwei/charters/ against the rebuilt copy found no difference, so agents and vendored copies match. The drift test passes in the suite.
- `git diff --stat 9d6701e bec74db -- cli` is empty, so runtime is unchanged.
- Read the charter diff. Each of the six promised rules is present: planner (verdicts forwarded together), _gate rule 3 (differential probe, untested), _gate rule 4 (generated probe with counts, re-run, door-word-free checks, JSON fixtures by code), builder VAL (same), steward rule 4 (lesson placement). The acceptance phrases map to the tests.
- _gate.md renumbering: grepped charters, agents and tests for citations of gate rules by number. The only numbered references are "Evidence 4" and "Boundaries 2", which point into _common.md and are unchanged. tests/fixtures/routes.json cites `charters/_gate.md:8`, which is before the insertion and still the same line. No reference breaks.
- Scanned the added lines with python for em dashes, en dashes and emoji: 0 hits.
- Spec completeness: specs/seat-rules has spec, plan, tasks, analysis and the checklist. The spec holds the promise, acceptance, "How this fails", clarifications, requirements FR-001 to FR-007, Assumptions and a Rollback line.
- Guard mutants: not run. The diff changes no guard or validation, only charter text. The red-on-main run above is the equivalent check.
- Simplicity: none. The diff is the six rules plus tests and spec. No runtime code is added, and the rules reuse the existing VAL line and gate rule list.
- Confidence is medium because the check was done on the diff and a test run, without a live seat applying the rules.

## Residual risk
The rules are untested in a live round. The first parser build under them will show whether the three counts are practical to report.

Verdict: PASS
Gate: goal
Item: wide-specs
PR: taoq-ai/wuwei#1142
Head: a7654a879f3e841e433ae81123c20498f705752c
Confidence: medium

## Findings
- [low] docs/design.md:109 blocks: no. The Breaking-changes paragraph still says "a contract file takes the arch gate at any tier" and does not name a spec contract; line 77 (the table the promise names) and the charter and site page do. It is not wrong (a spec contract is a contract), only less complete. Candidate for the next docs touch.
- [low] cli/wuwei/evidence.py:252 blocks: no. Docstring says "a contract or a wide change of code and specs", which matches the code. Code under docs/ no longer counts toward the wide trigger (a 300-line docs/conf.py dropped from arch to none); the PR body records this as an assumption and names it a candidate item, and the promise says "never prose" with docs/ in the prose class. Not a drift from the goal; flagged so the owner sees the direction.

## Probes
- Traced issue #1131 (read with gh api) -> plan item wide-specs (plan show) -> spec specs/wide-specs/spec.md -> diff. The issue's option 2 ("deliberately ask for arch on a large spec diff, or on any specs/**/contracts/* change ... say it in the rules") is what the diff does: evidence.py CONTRACT gains `^(specs|openspec)/(.+/)?contracts/`, `wide` keeps code and spec files only, charter/design/site say it. "The rule and the code should agree": checked below. The issue's cause, `lines(files)` counting every file, is gone (`lines(wide)`).
- Ran evidence.needed from `git archive` copies of main (efcd9e7) and head, tier as named. Acceptance 1 (standard, 1780 lines under specs/): main ('arch',), head ('arch',), the pinned already-true case. Acceptance 2 (standard, 150 README.md + 150 docs/site/a.md): main ('arch',), head (). Acceptance 3 (light, specs/001-x/contracts/api.yaml): main (), head ('arch',). Also head: openspec/changes/x/contracts/a.md light -> ('arch',); specs spec.md 200 lines -> (), 201 -> ('arch',); 150 py + 600 README -> ('quality',) (main ('arch','quality')); docs/contracts/api.md light -> (); full with only a spec or only README -> ().
- Acceptance 4: in a copy of the head, `bin/wuwei agents build` printed "agents match the charters"; `diff -r` of the tree before and after: no change; `diff -r cli .claude/wuwei/cli` and charters/_common.md vs the vendored copy: no difference. tests/test_charters.py::test_decisions_and_done_are_stated_once_in_common reads `over {evidence.WIDE} lines of code and specs, or 10 code files` and the spec-contract sentence; both are in charters/_common.md lines 40-42.
- Rule text vs code: charters/_common.md:40-42, docs/design.md:77 and docs/site/concepts/evidence.md:95,98 all say: wide = over 200 lines of code and specs (prose never), or 10 code files; spec contract takes arch at any tier. grep of charters/, skills/, docs/, README for other statements of the wide rule found none that disagree. The site row "docs only, or specs of 200 lines or fewer with no contract: none" matches the probes above.
- PR body counts read at the head. `pytest -q` (/root/.local/bin/pytest, head archive): 1700 passed, 2 skipped (body: same). Red run (head's tests/test_evidence.py and tests/test_charters.py copied onto an efcd9e7 archive): 10 failed, 218 passed (body: same). Runtime `cat cli/wuwei/*.py | wc -l`: 2,976 at efcd9e7, 2,978 at head (body: same; +2 matches the promise's +2, budget 3). `git diff --numstat efcd9e7 a7654a8`: 360 added + 85 deleted = 445 (REST files 29); split by path: specs/ 215, agents/ and .claude/ 163, other 67 (body: 445 / 163 / 215 / 67, all match).
- Builder's explain-back (PR body "Promise in my words") restates the four acceptance scenarios and the two behaviours (code and spec lines only, spec contract takes arch) faithfully; the body's "acceptance 1 already held on main and is pinned" is true per the probe. No claim beyond the promise: the 3 moved rows listed in VAL (Specs/ upper-case, openspec-named spec file, docs/conf.py) are declared as assumptions, not hidden.
- Mutants/guards: not run (goal gate; the quality gate owns them). The measure (200 lines) and computation (lines over code plus specs files, GENERATED excluded) are both fixed in the text, so no open computation follows the result.
- CI at head per the brief: tests 3.11/3.12/3.13 and ZIRAN passed, CodeQL neutral (not re-read here).

## Residual risk
The owner may prefer the issue's option 1 (code lines only); the assumption names that as a one-line change. Code under docs/ now gets no wide-trigger count and still no quality gate, recorded as a candidate item.

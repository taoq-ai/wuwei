Verdict: PASS
Gate: goal
Item: merge-evidence
PR: taoq-ai/wuwei#1114
Head: fc27033543ad8c0a57ec39f84fd0082d5d8587f2
Confidence: high

## Findings
- [low] blocks: no. docs/design.md is changed though the promise's file list names only docs/site/concepts/evidence.md; the edit rewrites the owner review row and the CI not started paragraph to match the new behaviour, so it keeps the design source true rather than adding scope.
- [low] blocks: no. The commit is declared breaking (`fix(evidence)!:` with a BREAKING CHANGE footer and migration). The promise does not say "breaking", but promise (1) is exactly that behaviour change, so declaring it matches the item.

## Probes
- `wuwei plan show`-equivalent read of .wuwei/plan.json id merge-evidence: promise (1)-(4), 4 acceptance lines, tier full, goal G-2 (bugs fixed before features).
- `git diff --stat 86135fa fc27033`: 10 files: cli/wuwei/evidence.py and its vendored copy (byte-identical, checked with diff), tests/test_evidence.py, docs/site/concepts/evidence.md, docs/design.md, specs/merge-evidence/*. Nothing outside the promise's files except docs/design.md (note above); gh.py untouched since the pull_request_target read lands in evidence.py.
- Builder's compare.py run by me on `git archive` copies of both trees (pytest's interpreter): A1 main shows no owner review gap with only breaking+exception rulings, head shows `owner review needed (owner_paths: infra/main.tf)`; with a kindless approved ruling added, head clears it. A2 docs+specs only: main `CI not started`, head `no gaps`; with cli/wuwei/x.py both show it. A3 GhError('HTTP 403'): head reads `CI not started at aaaaaaa (Actions host unreadable: HTTP 403)`, main gives no reason. A4 only pull_request_target runs: main no CI gap, head `CI not started`. All four acceptance lines hold on head and fail on main.
- Head suite: `pytest -q` at fc27033: 1207 passed, 2 skipped.
- Head tests against base evidence.py: 7 failed (6 new tests red plus the updated failed-read cache test), matching tasks T006 and the PR body.
- Extra probes on head: a docs-only diff makes zero `actions/runs` calls (spec FR-002 claim), and a repo with pull_request runs makes exactly one Actions read (spec assumption "a repository with both costs one read"). Both passed.
- hook.py:244 confirmed: an `owner review:` answer is recorded with no kind, `breaking:` with kind breaking, `exception:` with kind exception, so "no kind" is exactly an owner review ruling as the promise defines it.
- Spec (specs/merge-evidence/spec.md) explain-back matches the promise and all four acceptance scenarios; FR-001..005 map to tasks; Breaking section and migration match the commit footer. Runtime 2,976 to 2,977 lines (cat cli/wuwei/*.py | wc -l), within budget 6 and the 3,000 cap.
- Out-of-scope items (workflow path filters, Codex attestation #1078) are untouched.

## Residual risk
A docs-only PR in a repository whose docs CI should hold merges can merge before that CI registers; this is the plan item's recorded assumption, which the owner can overturn.

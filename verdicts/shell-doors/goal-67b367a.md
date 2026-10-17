Verdict: PASS
Gate: goal
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: 67b367ae51e6d4c111b50aa3b74d8df270130b1e
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:88 blocks: no. Promise (1) says a punctuation-only word makes the command unreadable; the build splits it into sh operators instead (declared in spec Clarifications and the PR body). Every acceptance 1 outcome still ends refused, but a push inside process substitution to a non-default branch (cat <(git push origin i-1-change)) now passes like a plain push, where the promise wording would refuse it. This matches the acceptance outcomes and is not a goal change.
- [low] cli/wuwei/guards.py:28 blocks: no. Goes beyond the promise, all declared: |& joins CONTROL, LEDGER also matches after = (dd of=), and DOOR_WORDS matches bare .wuwei, so multi-line commands naming .wuwei are refused (2 of 2,435 traced commands, per spec How this fails 1).
- [low] blocks: no. SECURITY.md lists rm -rf .wuwei/* as a recorded gap that the promise's Outside list does not name. Probe confirms it passes. It is recorded honestly; no acceptance line asks for it.

## Probes
- Stub git on PATH (my own, logs "$*"), bash -c on each of the 7 acceptance 1 commands at head and at base 83f1f09: the log holds "push origin main" every time. guards.bash at head: the first 5 are denied by the push door ("pushing to the default branch main refused"), $'main' and $"main" are denied as unreadable. At base all 7 pass.
- Acceptance 2 at head: diff <(sort a) <(sort b) and echo $'a\tb' pass.
- Acceptance 3 at head: rm -rf .wuwei/ledger, mv .wuwei/ledger x, cp x .wuwei/ledger, rm -rf .wuwei and rm -rf /abs/path/.wuwei/ledger are denied with "the ledger is written only by WUWEI's hooks". cat .wuwei/ledger/x.jsonl and ls .wuwei pass. tee, dd of=, >> and rm -rf ./.wuwei are denied too. At base all 5 named writes pass.
- Acceptance 4: pytest -q at head in a git archive copy gives 1103 passed, 2 skipped. Head routes.json run against base guards (mixed tree): exactly 13 failures, all new rows (6 to push, 7 to refusal). Base has 133 rows and head has 151 (+18). The routes.json diff only appends rows plus a comma on the old last row, so no pre-existing row moved. This matches the PR body's corpus claim.
- cli/wuwei/guards.py and .claude/wuwei/cli/wuwei/guards.py are identical at head. Runtime is 2999 lines, within the 3,000 budget.
- The spec (specs/shell-doors/spec.md) restates the promise and acceptance, records the split-not-refuse choice, Breaking, Rollback and Assumptions. It matches the diff and the PR body (WUWEI-Item: shell-doors, draft, head 67b367a, read once via REST).
- Confidence is high: I re-ran every acceptance line myself in a real execution, at both heads.

## Residual risk
The split reading follows sh for the shapes probed. Rarer runs (>>(, <<() rely on the spec's argument that splitting only adds segments. The outside-scope gaps (cd .wuwei, globs, find -delete, git clean) stay open.

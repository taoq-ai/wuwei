Verdict: PASS
Gate: arch
Item: 1201
PR: taoq-ai/wuwei#1204
Head: e84f228d7679c07893577ed65011808b879572f3
Confidence: high
Breaking: no (minor: plan run gains an optional --job; input that was refused before is now accepted, nothing documented is removed or changes meaning, exit codes unchanged)

## Findings
- [low] cli/wuwei/board.py:116 blocks: no. Coupling: board, the core read path, now imports upgrade (the one-off 0.34 to 1.0 migration module) for its private `_json`. No cycle (upgrade imports evidence, plan, ws, verdict, not board), and the import costs about 1 ms on the hook path (`python3 -X importtime`: wuwei.upgrade 937 to 1211 us out of about 100 ms for wuwei.hook). But deleting upgrade.py in a later deletion pass now breaks the board. Moving `_json` into ws.py, next to `cache_get`, would undo that coupling.
- [low] cli/wuwei/__main__.py:48 blocks: no. Asymmetric merge: `plan run --reason` alone keeps a registered job, but `plan run --job` alone sets the reason to '' (probe: after `--reason "Codex builder in /wt/a"` and then `--job j.json`, the reason is ''). The ledger event `item.open` records only the empty reason and never the job path, so the registration cannot be seen in the ledger. The charter tells the planner to pass both flags in one call, so the effect is small.
- [low] cli/wuwei/board.py:117 blocks: no. Contract drift (an undocumented external JSON shape, specs/codex-job-state/spec.md). A removed or renamed `status`, a deleted file (the companion prunes to 50 jobs per state dir, state.mjs pruneJobs) or a partial read (writeFileSync is not atomic) each fail safe to `job state unreadable`. A non-string status is printed verbatim (probe: `job {'x': 1}`). The silent case is `result.rawOutput` moving: a job that ended with a question would then read `job completed` and lose the question signal. The spec records this assumption, and the row stays [waiting] in every state, so the item is never marked done.
- [low] charters/planner.md:28 blocks: no. Operability: the charter says "the companion's `jobs/<job id>.json`" but not where to find it. The companion prints only `Log: <...>/jobs/<id>.log` (render.mjs:146), so the planner has to derive the .json path from that Log line. One clause naming that would save a search.

## Probes
- Why arch: `evidence.needed` at the head (scratch script over `gh pr view 1204 --json files`) marks the change wide. The non-prose lines total 212, over WIDE=200: specs/ 106, tests 44, and the code and charter lines counted twice because of the vendored copies under .claude/wuwei/ (runtime 22+22, charter 9+9). It has 7 code files (10 or fewer), no contract file and no risky path.
- Design rule "reads only a registered file": board.job opens exactly os.path.join(root, item['job']) through upgrade._json. No glob, listdir or iterdir was added (diff read). design.md section 6 and the reference table match the code.
- Companion shape, read only: the newest real job file has keys that match the spec table, `status`/`result.rawOutput` included. The largest job files are about 69 KB, so one read per run item per 60 s board TTL is cheap.
- Probes at the head (python3 -I in a scratch case folder): a directory path, a missing relative path and a non-dict JSON all gave `job state unreadable`. A trailing question with a handoff gave `job asked a question, handoff /wt/HANDOFF.md`. A question in the middle of the text gave `job completed, handoff ...`, as the assumption states.
- Budgets: runtime is 3,351 at main 5b5084b and 3,357 at the head (`cat cli/wuwei/*.py | wc -l` on git archive copies). That is +6, within the item's budget of 6 and the constitution's 10, and leaves 43 lines under 3,400. No config key was added. `diff -r` shows cli/wuwei equal to .claude/wuwei/cli/wuwei and the charters equal to their vendored copies.
- Agents build: planner.md is not a role in agents/allowlist.json, so it produces no agent file. `agents.stale('.')` at the head returned [].
- Breaking, read against base docs/site/reference.md: `plan run` was documented as "refused without --reason". It is now refused without --reason or --job, a new optional flag that only widens what is accepted. The item record gains an additive `job` field.
- Mutants (fresh copy each, both trees, tests/test_plan.py): guard to `if not args.reason` gave 8 failed. Guard to `if False` gave 1 failed (test_plan.py:125). `or 'state unreadable'` to `or 'completed'` gave 5 failed. The question check to False gave 1 failed. All four were killed.
- Suite at the head (uvx pytest, offline gh on PATH, CLAUDE_CODE_SESSION_ID unset): 4 failed, 3012 passed, 1 skipped. The 4 failures are the known bash 3.2 cases on main (test_codex hook shells, plus three test_guards push shapes).
- CI at e84f228 (`gh pr checks 1204`): test 3.11, 3.12 and 3.13, CodeQL, Analyze and ziran all pass.
- Confidence high: the change is additive, fails safe on every unreadable shape I probed, holds its budget, and CI and the local suite agree.

## Residual risk
The question and handoff signals depend on the free-text heuristic over an undocumented `rawOutput`. When the companion changes, these signals degrade to `job completed` without an error. A stale `running` file whose process died also keeps reading running. The spec records both as assumptions.

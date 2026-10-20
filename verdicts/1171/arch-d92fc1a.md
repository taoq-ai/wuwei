Verdict: PASS
Gate: arch
Item: 1171
PR: taoq-ai/wuwei#1184
Head: d92fc1a50d41c2308d3864c05ec464c11e36c8b2
Confidence: high
Breaking: no (patch: the PostToolUse note is advisory additionalContext text, not a declared API element; no exit code, schema, CLI flag or ledger shape changes)

## Findings
- [low] cli/wuwei/hook.py:385 blocks: no. The fallback reads as exhaustive ("an existing docs/adr/ or docs/decisions/, else the item's spec folder"). A repository whose ADRs live elsewhere (adr-tools' default is `doc/adr/`, not `docs/adr/`) could read the "else" literally and start a second home. The leading clause "where the repository keeps its ADRs" covers it, and finding the folder is out of scope in the item. The PR's assumption that adr-tools uses `docs/adr/` is not exact.
- [low] blocks: no. PR #1187 (head 041f4b6) also rewrites agents/sentinel-arch.md and .claude/agents/sentinel-arch.md, in a different hunk (the _gate section). Whichever PR merges second must rebuild agents/ (`bin/wuwei agents build`) and re-vendor. The drift test catches a stale copy.

## Probes
- CI at d92fc1a (`gh pr checks 1184 -R taoq-ai/wuwei`, read once): all 8 pass (test 3.11/3.12/3.13, CodeQL, Analyze actions/python, ZIRAN, ziran-audit).
- `wuwei evidence taoq-ai/wuwei#1184`: unmeasured. gh API rate limit exceeded; not retried.
- Conformance: docs/design.md:71 ("A `one-way:` answer becomes an ADR in the repository") and :227 (PostToolUse ADR notes) still hold. The rule is now stated the same way in the hook note, charters/planner.md:77-80 and docs/site/concepts/decisions.md:66-70. The constitution names no ADR folder. No other runtime, charter or docs text names `docs/adr/` as the only home (grep -rn over the head archive, excluding specs/ and .claude/wuwei/). specs/vendored-drift still cites this repository's own docs/adr/0001, which is fine because this repository has that folder.
- Dependencies/coupling: the hook.py change is a string literal inside `_answers`. No import, call or control flow changes. cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py are byte-identical (cmp).
- Contracts: the note's only consumer is the model reading additionalContext. Its only test is tests/test_hook.py::test_a_one_way_answer_asks_for_an_adr_where_the_repository_keeps_them. The note is still emitted only when the transcript shows a `one-way:` answer, per #1172's path.
- Route differential over tests/fixtures/routes.json (sha256 4f6e25d0..4d49, identical at main 8a92be7 and the head). A scratch pytest dumped verdict, decision and reason for each route through guards.bash with the test_guards stubs: 263 routes on each side, 0 moved (head: 103 refusal, 67 pass, 34 push, 25 merge, 21 ready, 13 create).
- Fitness, runtime lines (`cat cli/wuwei/*.py | wc -l`): 3318 at the head and 3321 at main 8a92be7, so 3322 after merge, under the 3400 budget. The item's 1-line budget holds (hook.py +3/-2).
- Fitness, agent word ceiling (AGENT_WORDS=2250, counted with str.split as tests/test_charters.py:56 does). main 8a92be7: sentinel-arch 2250. This head: 2249. PR #1187 alone (041f4b6): 2249. Both together (#1187's charters/_gate.md diff applied onto this head, then `sh bin/wuwei agents build`): sentinel-arch 2248, sentinel-security 2105, sentinel-quality 2068, builder 2001, sentinel-goal 1979. Every agent stays under the ceiling.
- Tests at the head (uvx --python 3.13, git archive copy): tests/test_hook.py + tests/test_charters.py, 609 passed.
- Mutant: I dropped the "amend that ADR" sentence in both hook.py copies. tests/test_hook.py::test_a_one_way_answer_asks_for_an_adr_where_the_repository_keeps_them fails, so the mutant is killed. The charter rule is pinned by tests/test_charters.py::test_an_adr_goes_where_the_repository_keeps_them_and_a_reconfirmed_one_is_amended.
- Decisions: the order rule (an existing folder first, else the spec folder) and the issue-vs-item choice ("that ADR", not "ADR-003") are recorded under the PR's Assumptions. No unrecorded one-way choice.
- Confidence is high: the change is text only, CI is green, 0 routes move, and the budgets were measured.

## Residual risk
The note stays advice; WUWEI does not check where an ADR actually lands. A repository with an unusual ADR folder depends on the planner reading the leading clause rather than the listed fallbacks.

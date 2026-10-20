Verdict: PASS
Gate: security
Item: 1171
PR: taoq-ai/wuwei#1184
Head: d92fc1a50d41c2308d3864c05ec464c11e36c8b2
Confidence: high

## Findings
none

## Probes
- Scope: `git diff 1877565c...d92fc1a5` (merge base is main 1877565). The only runtime change is the fixed text of the one-way note in `hook._answers` (cli/wuwei/hook.py:385-387). `diff -r` of cli/wuwei between the main and head archives shows those 3 lines and nothing else. The vendored .claude/wuwei/cli/wuwei/hook.py is byte-identical (cmp). The merge resolution keeps #1172's transcript-checked `kept` path and `return notes`, so the note is still emitted only for an answer the transcript confirms.
- Trust boundary (OWASP LLM01 prompt injection, CWE-74): the note interpolates no question, answer or repository text. It is a constant string of about 300 characters, well under SESSION_CAP 10000. No new path from untrusted input into model context.
- Route differential (AGENTS.md "Testing the guards"): every route in tests/fixtures/routes.json (sha256 4f6e25d0864d7922f17515d94a99be77590c11816113c273f211626318be4d49, the same at main and head) was read through guards.bash at main 1877565 and at the head. I used a dump test that uses the harness from test_every_route_reads_as_recorded, with basetemp under the seat scratch folder. Result: 263 routes, 0 moved in verdict or reason, 0 differ from the recorded verdict on either side (refusal 103, pass 67, push 34, merge 25, ready 21, create 13). No refusal names a different PR or repository.
- Generated combinatorial parser probe and normalisation probes: not run. No guard parsing, normalisation or door decision changed (guards.py is untouched, and the hook.py change is note text only).
- Mutant: I put main's hook.py into both cli/wuwei and .claude/wuwei/cli/wuwei in a fresh archive copy. tests/test_hook.py::test_a_one_way_answer_asks_for_an_adr_where_the_repository_keeps_them failed, so the mutant is killed.
- Full suite at the head (archive copy, `uvx --python 3.13 --from pytest pytest -q`): 2734 passed, 1 skipped, 4 failed. The 4 are the known macOS bash 3.2 failures named in the brief (test_the_hook_commands_run_under_either_harness_shell and 3 test_bash_runs_the_push_in_each_refused_shape shapes).
- `bin/wuwei agents check` at the head: "agents match the charters". Largest agent is sentinel-arch at 2249 words (`wc -w`), under the 2250 ceiling. The vendored charters and agent are identical (cmp).
- Supply chain and agent least privilege: the diff touches no dependency, lockfile, workflow, hooks.json, settings or agent tool grant. CI ZIRAN role-grant audit and CodeQL (actions, python) pass at the head.
- Secrets and information exposure (CWE-200): guards.SECRETS over the 237 added lines found 0 hits. A grep for local paths, emails and the client names in issue #1171 (Tinuiti, ai-stacks, A-Teams, genesis) also found 0 hits, so no workspace content reached this public repo.
- How this fails (spec.md:32-41): checked at text level. The note leads with "where the repository keeps its ADRs" (scenario 1), puts "an existing" folder before the spec folder (scenario 2) and names the re-confirm case (scenario 3). None of the three is a security scenario.
- CI: `gh pr checks 1184 -R taoq-ai/wuwei` read twice. On the second read every check passed at headRefOid d92fc1a5 (test 3.11, 3.12 and 3.13, ziran-audit, ZIRAN, CodeQL, Analyze actions and python).
- `wuwei evidence taoq-ai/wuwei#1184`: unmeasured. It printed "evidence unreadable: gh: API rate limit exceeded", and I did not retry.
- Confidence high: the change is constant model-facing text on an unchanged, transcript-checked path. The route differential shows 0 moves and CI is green at the head. Evidence of a door or parsing change I missed would lower it.

## Residual risk
The note now lets repository content choose the ADR folder (docs/decisions/ or the spec folder, besides docs/adr/). A planted symlink at that folder (CWE-59) carries the same risk class as main's docs/adr/; I did not probe it here. hook.py is an owner path, so owner review is still a merge gap outside this gate.

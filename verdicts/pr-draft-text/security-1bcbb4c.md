Verdict: PASS
Gate: security
Item: pr-draft-text
PR: taoq-ai/wuwei#1139
Head: 1bcbb4c01717ea7dd367a0f678cc5cfa6a083851
Confidence: high

## Findings
- [low] blocks: no. Wording, not a door: "It turns ready once they pass" does not name who flips the PR, so a lone seat could read it as permission to run `gh pr ready` itself. That cannot skip a gate, because `ready_door` (cli/wuwei/guards.py:274-282) still refuses the flip and reviewer requests on a draft until the gates pass, and that code is byte-identical to main. Process fit only (OWASP LLM08 excessive agency: covered by the door, not by the text).
- [low] specs/pr-draft-text/spec.md:42 blocks: no. "How this fails" 3 says the new guard test fails when the charter goes stale. In a checkout, `ws.PLUGIN` is the repository root (cli/wuwei/ws.py:15), so the guard test reads `charters/_pr.md` and not the vendored copy. A stale vendored copy is caught by the drift test in tests/test_setup.py instead (mutant run below). The risk is still covered; the claim is just slightly off.

## Probes
- Diff scope: `git diff --name-only efcd9e7 1bcbb4c` lists 2 charter copies, 5 spec files and tests/test_guards.py. `diff -r` of cli/ and agents/ between `git archive` copies of main and head shows no differences, so no guard, parser, dependency, workflow or lockfile changed. Parser and normalisation probes: N.A. Route corpus differential: N.A. because the runtime is byte-identical, and the only input that differs is the note text, which only changes the note.
- The text against the trust questions: the paragraph keeps "Before merge, CI is green and every review thread is answered". It says the PR opens as a draft and turns ready only after the gates pass. It moves the reviewer request to after the flip, and the ready door enforces that (READY covers `requested_reviewers` and `--add-reviewer`). Nothing in it permits a non-draft open, an early flip, a skipped gate, or a merge without CI and answered threads. It agrees with charters/builder.md:70-73 and charters/shepherd.md:7-19.
- Doors at head vs main: `pytest -q tests/test_guards.py -k 'draft or ready or create or reviewer or pr_standard or merge'` gave 379 passed on main and 380 passed on head (the +1 is the new test). This includes test_a_create_that_is_not_a_draft_waits_for_its_gates_and_names_the_draft_route, test_a_draft_leaves_draft_or_asks_reviewers_only_once_its_gates_pass, the MCP create/update routes and the graphql ready/reviewer refusal.
- Full suite at head (archive copy): `pytest -q -W error` gave 1685 passed, 2 skipped.
- Mutants (fresh archive copy): old `_pr.md` in the vendored copy only: new guard test passes, drift test fails (1 failed, 2 passed). Old `_pr.md` in the tree charter: new guard test fails (1 failed, 1 passed). No guard was changed, so there was no guard to reverse.
- Live PR state, read once via REST (`gh api repos/taoq-ai/wuwei/pulls/1139`, `.../commits/<head>/check-runs`): head 1bcbb4c, draft true, no requested reviewers. CodeQL, ZIRAN, ziran-audit, test 3.11/3.12/3.13 and Analyze (actions, python) all completed success.
- Scanner: agent tooling unchanged, so the repo's own scanners were not re-run locally. CI's CodeQL and ZIRAN at this head report success.
- Confidence high: docs-only change with byte-identical runtime, door tests green on both sides, and live CI green.

## Residual risk
The note is advice and can be ignored or misread. Safety rests on the create and ready doors, which this PR does not touch.

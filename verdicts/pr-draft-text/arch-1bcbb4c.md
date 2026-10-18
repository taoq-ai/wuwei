Verdict: PASS
Gate: arch
Item: pr-draft-text
PR: taoq-ai/wuwei#1139
Head: 1bcbb4c01717ea7dd367a0f678cc5cfa6a083851
Confidence: high
Breaking: no

## Findings
- [low] charters/_pr.md:20 blocks: no. A non-draft `gh pr create` that create_door lets through at a gated head (guards.py:254-256) gets the same note, which says the PR opens as a draft. Probed: the note is returned with decision `note` after the create is allowed. It is advice shown once per session, not a refusal, and the spec records it under Assumptions with its overturn condition; it was already a single standard text for both routes before this change.
- [low] blocks: no. Wording drift, not a contradiction: _pr.md says the PR "turns ready once they [the gates] pass", while shepherd.md:14 turns it ready once CI is green and the gates passed. CI green stays a merge condition in _pr.md and in _common.md Done, so no seat is told a different order.
- [low] guards.py:393 blocks: no. Existing gap outside this diff: the MCP create path never shows the PR standard note, so a seat that opens the draft by MCP does not see the corrected text. Not moved by this change.

## Probes
Conformance: new _pr.md:20-22 read against builder.md:70-73 (builder opens draft, never readies or requests reviewers), shepherd.md:7-19 (shepherd readies after gates and CI, then requests reviewers), _way.md:10-11 and :18 (draft first, ready with reviewers only after gates), _common.md:32 and :51 (gates before ready; requested reviewer is process fit). All agree on draft-first order and that the shepherd, not the body writer, requests the reviewer. Old text ("passed on this branch before it opened. Request a reviewer.") contradicted builder.md:71; the new text removes that.
Consumers: `git grep` at head shows one reader of _pr.md, guards.PR_STANDARD (guards.py:62, 256), returned as a `note` reason. No code parses the reason text; tests/test_guards.py door_reached maps any note to `pass`. No other file at head quotes "Request a reviewer" or "before it opened" (grep over md/py/json/toml, specs excluded).
Route corpus: tests/fixtures/routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at both main efcd9e7 and head (unchanged). Main-versus-head differential through guards.bash over all 251 routes: 0 verdicts move; 4 routes keep decision `note` with changed reason text (gh pr create --draft; gh pr create --draft -t t -F body.md; two gh api POST pulls -F draft=true routes), which is the intended change. The routes.json:5 citation of charters/_pr.md:1 still holds: line 1 is unchanged and that route (non-draft create) still reaches the create door. Route tests: 350 pass at main and at head.
Suite at head (git archive copy, /root/.local/bin/pytest -q): 1685 passed, 2 skipped.
Mutants (each in a fresh git archive copy, tests/test_guards.py + tests/test_setup.py): both _pr.md copies reverted to main -> test_the_pr_standard_note_opens_a_draft_and_leaves_the_reviewer_to_the_shepherd fails; only charters/_pr.md reverted -> that test and test_the_vendored_plugin_matches_the_tree_it_was_copied_from fail; only the vendored copy reverted -> the vendored-drift test fails. No surviving mutant.
Non-draft probe: plan item I-1 light, quality attested, `gh pr create --title t --body "WUWEI-Item: I-1"` -> decision `note` with the new draft text (residual confirmed).
Composition with #1138 (models-table, head 344745a, same base efcd9e7): file lists disjoint (it touches planner.md, steward.md, agents/steward.md, skills, docs, test_charters.py; not _pr.md, guards.py or test_guards.py). Its diff applies cleanly onto this head in a copy; combined suite 1693 passed, 2 skipped.
Fitness functions: runtime lines under cli/wuwei/ unchanged (0 runtime lines in the diff); no config key, no dependency added. agents/ do not include _pr.md, and the agents drift test passes.
Breaking: the note is advisory text read by agents; its decision kind (`note`) and its trigger (once per session on an allowed create) are unchanged, and no client parses its wording.
Confidence high: a text-only change with one reader, a full route differential at 0 moves, and three killed mutants; it would drop if a consumer outside this repository parsed the note wording.

## Residual risk
A seat reading the note after a gated non-draft create may think it should have opened a draft; harmless because the create already succeeded and the note is advice. A seat working without a shepherd may leave a ready PR without a reviewer, which is process fit and never holds a merge.

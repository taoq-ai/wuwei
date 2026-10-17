Verdict: PASS
Gate: arch
Item: charter-review
PR: taoq-ai/wuwei#1124
Head: 7f67ab2479c16c529ee54bf19a172ba495ab0c61
Confidence: high
Breaking: no

## Findings
- [low] blocks: no. agents/sentinel-arch.md is 2230 words under the 2250 ceiling (wc -w agents/*.md): 20 words of headroom, down from 44 at 7021905 because the closing paragraph grew by one sentence. The ceiling test still asserts a bare boolean (tests/test_charters.py:56), so the first seat to add a common sentence gets no count in the failure message. Kept from the previous round, unchanged by the delta.
- [low] blocks: no. tests/test_charters.py anchors on exact prose ("are the security gate's" at line 100, the Decisions table row, "Charters shrink too"). The artefact under test is prose, so there is no record to assert on; every steward deletion under its rule 9 carries a test edit. Kept from the previous round for the retro, unchanged by the delta.
- [low] tests/test_charters.py:70 blocks: no. `days = {3: 'three'}[evidence.STALE_DAYS]` maps one value; a change to STALE_DAYS raises KeyError inside the test rather than an assertion message. The failure is still loud and forces the charter edit the test exists to force, so this is a wording note, not a defect.

## Probes
- Standards line for arch: `git diff --stat origin/main 7f67ab2 -- cli/` is empty, so neither cli/wuwei/guards.py nor cli/wuwei/hook.py is touched; the main-versus-head differential over tests/fixtures/routes.json does not apply and was not run.
- Delta scope: `git diff --stat 7021905 7f67ab2` is 26 files, 102 insertions, 74 deletions; charters/_common.md, charters/sentinel-arch.md, skills/wuwei-rules/SKILL.md, tests/test_charters.py, specs/charter-review/*, and agents/ plus .claude/ rebuilt. Docs and tests only.
- Previous finding 1 (two rules for one case) closed: in the generated agents/sentinel-arch.md, gate rule 5 (lines 129-133) says a trust-boundary defect blocks and a trust-boundary security finding always blocks; the closing paragraph (lines 217-220) now says trust boundaries are the security gate's to probe, "A trust defect you see is still a finding with its class and blocks under gate rule 5: the security gate may not run on this head". The two agree. Only the open-measure case goes to goal as a note. Acceptance 4's "leaves trust boundaries to the security gate" holds in the probing sense and the test phrase "are the security gate's" (tests/test_charters.py:100) passes.
- Previous note 2 (average at 30) closed: test_sentences_average_under_20_words asserts < 20, matching _common-authoring.md:24 "under 20 words on average and none over 35". Measured with the test's own splitter under pytest's interpreter: averages 8.5 (_pr) to 16.7 (sentinel-security), maxima 12 to 35 (steward at the cap), all 19 files.
- Previous note 3 (five-merge floor) closed: _common.md:44 now reads "over 15 percent (over at least five merges)"; evidence.py:221 `found['merged'] >= 5 and found['cfr'] > BUDGET`. The thresholds test now derives its strings from evidence.MAX_LINES, STALE_DAYS, BUDGET, TRIVIAL, WIDE = 400, 3, 0.15, 20, 200 (evidence.py:46) and adds the wide-change line; it passes at the head.
- Suite in the git archive copy: `/root/.local/bin/pytest -q -W error` gives 1682 passed, 2 skipped. `bin/wuwei agents check`: "agents match the charters", exit 0. Runtime `cat cli/wuwei/*.py | wc -l` = 2976, unchanged, under 3000.
- Vendoring: `diff -r charters .claude/wuwei/charters`, `diff -r skills .claude/skills` and `cmp` of each agents/*.md against .claude/agents/*.md: identical.
- Contracts: the YAML front matter (name, description, tools) of all eight agents is byte-identical between origin/main and the head (awk front-matter diff); `git diff origin/main 7f67ab2 -- cli/wuwei/verdict.py` is 0 lines, so verdict.FORMAT is unchanged; no cli/ change at all. Breaking: no.
- PR body counts re-derived: `git diff --stat origin/main 7f67ab2` gives 65 files; `git diff --name-only` minus agents/ and .claude/ gives 30 hand-written files; red run reproduced in a second archive of origin/main (9c637ab) with the head's tests/test_charters.py, tests/test_setup.py and tests/fixtures/skill-triggers.json copied in: `pytest -q tests/test_charters.py tests/test_setup.py` gives 32 failed, 85 passed, with test_no_sentence_is_over_35_words red on 11 files and the ceiling test red on none. All four numbers match the spec, tasks.md and the PR body.
- Conformance: the preamble no longer names docs/design.md; "the design document its process names" resolves through AGENTS.md:5 ("What to build: docs/design.md"), so the arch gate still finds the design here and the charter stays generic for other workspaces. wuwei-rules now says "this skill gives only the short form", which is what the paragraph does.
- PR head read once via REST (`gh api repos/taoq-ai/wuwei/pulls/1124`): head 7f67ab2479c16c529ee54bf19a172ba495ab0c61, draft true; the head did not move during review.
- Confidence high: every count in the PR body was reproduced from a run, the generated agent's two trust sentences were read side by side, and the delta is docs and tests with no runtime path.

## Residual risk
The gate-selection hole stays in the runtime: evidence.RISKY is name-based, so a contract file off a risky-named path at standard still runs arch without security; the charter now makes arch block on a trust defect it sees, which closes the charter-level regression but not the runtime one (recorded in the PR's review notes as a candidate outside this item). The 20-word headroom on sentinel-arch means the next common-rule edit fails the ceiling test and needs a deletion first.

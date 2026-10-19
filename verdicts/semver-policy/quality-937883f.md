Verdict: PASS
Gate: quality
Item: semver-policy
PR: taoq-ai/wuwei#1154
Head: 937883f990689a054239d816a173f2f542706dc6
Confidence: high

## Findings
- [low] tests/test_charters.py:109 blocks: no. The bound `len(rule.split()) <= 66` is one word above the old rule 7 by the test's own measure (base 65, head 64, counted with the test's split, which leaves out the `7.` marker), so the test allows rule 7 to grow by one word past its old length, while the promise says "in no more words". The PR body's "65 words (66 before)" counts the marker, so it is consistent but measured differently. Note only: agents/sentinel-arch.md is held at 2,250 by AGENT_WORDS anyway.
- [low] docs/site/concepts/evidence.md:106 blocks: no. "Before such a change merges" now follows the new sentence "A stricter check is a `fix:` commit ... never a `!`", so "such a change" reads as the stricter check. A reader could take it that a stricter check needs an `Announcement:`. Moving the sentence into the **Why** paragraph, or writing "Before a breaking change merges", removes the ambiguity.
- [low] blocks: no. "One thing once" is mostly met, but not fully. docs/design.md:116-118 restates the definition and the minor case before it links to the section. Inside evidence.md the "stricter check is a minor" point appears in the table, the ESLint paragraph, the `fix:` sentence and the Why line. This is repetition, not contradiction: every copy says the same thing.
- [low] blocks: no. Rule 7 asks for `Breaking: no` with the bump, but the verdict template (charters/_gate.md:59, cli/wuwei/verdict.py FORMAT, docs/site/reference.md:82) still shows only `Breaking: no`. The parser reads the bump as free text and does not record it. This is the PR's stated assumption (no `Bump:` field), and nothing breaks.
- [low] tests/test_charters.py:104 blocks: no. The test pins phrases in the prose, which is this file's existing convention for charter fitness tests. It cannot tell a pinned phrase used in a negated or contradicting sentence. This is an inherent limit for a docs-only item.

## Probes
- Base red: I put the head's tests/test_charters.py into a git archive of 5fe8347 and ran `pytest -q tests/test_charters.py -k semver`: 1 failed, on the first assert ('When unsure, say yes' still present).
- Phrase-by-phrase mutants (scratch mutants.py, each in a fresh copytree of the git archive at the head, `pytest -k semver`): 27 mutants, 27 killed, 0 survived. They covered: arch rule 7 with 'When unsure, ESCALATE', 'public API', 'Yes is a SemVer major' and 'reports more, is minor' each dropped, 'When unsure, say yes.' re-added, and 3 words padded (67 > 66); builder 'Only a major' and the `fix:` sentence dropped; 'outward contract' re-added to _common.md, builder.md and sentinel-arch.md; each of the 10 pinned evidence.md section phrases dropped inside the section only; for design.md, reference.md and decisions.md, the link dropped and 'outward contract' re-added.
- verdict.parse strict, arch gate, at the head (scratch parse_probe.py). These shapes give no errors with breaking='': 'Breaking: no (minor)', 'Breaking: no (patch)', 'Breaking: no, minor', 'Breaking: no: minor', 'Breaking: no minor', 'Breaking: no'. 'Breaking: yes: renames --tier for scripts' gives no errors and breaking='renames --tier for scripts'. 'Breaking: minor', 'Breaking: patch' and an absent line are refused with the Breaking error, which is the fail-closed behaviour.
- Full suite in the archive copy: `pytest -q` gave 1926 passed, 2 skipped, the same as the builder's numbers. The two skips are present on main as well (not this diff).
- Agents and vendoring, in a separate archive copy: `bin/wuwei agents build` printed "agents match the charters" and git status was clean. `diff -rq` shows .claude/agents equal to agents/ (apart from the pre-existing allowlist.json and ziran-baseline.json, which are only in agents/ on main too), .claude/wuwei/charters equal to charters/, and .claude/wuwei/cli/wuwei equal to cli/wuwei. `wc -w agents/*.md` max is 2248 (sentinel-arch), all at or under 2,250.
- Em dash, en dash and emoji scan over all 32 changed files (python regex for U+2014, U+2013, U+2600-27BF, U+1F000-1FAFF): none.
- Leftover old wording: `grep -rn "outward contract|say yes|published contract|behave differently"` outside specs/semver-policy hits only historical specs (gh-doors, shell-doors, doors-by-rest, draft-raise, wide-specs). No live charter, skill or site doc keeps the old rule.
- The ESLint citation was checked against raw README "Semantic Versioning Policy". Patch is "reporting fewer linting errors"; minor is "a bug fix that results in ESLint reporting more linting errors". It supports the docs' claim.
- PR read once with REST (gh api repos/taoq-ai/wuwei/pulls/1154): head 937883f matches, draft true, `WUWEI-Item:` and `Release-As: 4.1.0` alone on their lines, with `Rollback:` and `Assumptions:` present.
- Mutants of runtime guards: not run, because no runtime code changes (cli/wuwei is unchanged by the diff).
- Confidence high: docs and charters only, every pinned phrase is killed by a mutant, and the parser is unchanged and probed on the new shapes. A hidden consumer that reads charter prose for the old wording would change this; none was found by grep.
- Simplicity: none. The diff is prose plus one fitness test. The only candidate is the duplicated "stricter check is a minor" sentences in evidence.md (the `fix:` sentence or the Why addendum), and the table already states it.

## Residual risk
Classifying a change stays a judgement for the arch seat. The two-clause line between "closing a hole in a documented rule" (minor) and "a new rule every PR must meet" (major) will need escalations at first. Acceptance 3 (release-please proposes 4.1.0) can only be read after the merge.

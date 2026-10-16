Verdict: PASS
Gate: arch
Item: gate-rules
PR: taoq-ai/wuwei#1105
Head: 5e1642f3474c19239799937ff55c03ce2a5de63d
Confidence: high
Breaking: no

## Findings
- [low] charters/_common.md:39 blocks: no. "a builder uses `git worktree add`" is new guidance for builders under Evidence 4 (a probe rule); builder.md:3 already gives the builder its own worktree, so it agrees, but it reads as an instruction to create one. Note only.
- [low] blocks: no. The promise text (plan item) still names "3,000 minus the measured lines"; the charter now reads "that stated budget minus the measured lines", which is the scoped form of the same rule and still meets acceptance 5. The goal gate may want the plan wording aligned at merge.

## Probes
- Diffed dc733e0..5e1642f (git diff --stat and full diff of charters, docs, cli, tests).
- Previous blocking finding (planner.md:15 unscoped 3,000 budget): closed. planner.md and lead.md now apply only "in a repository whose own process states a runtime line budget (its constitution or AGENTS.md)" with no literal figure; WUWEI's constitution and AGENTS.md state 3,000, so WUWEI keeps the check and other workspaces do not get it.
- Previous notes: lead.md scoping closed; literal 3,000 copy closed; builder.md AUTH now scoped to the repository's guard code with the corpus "where it exists"; sentinel-security rule 6 defines a normalisation round and makes wrappers examples; hooks.md:46-48 matches the Stop line; worktree rule appears once (_common Evidence 4), _gate rule 3 refers to it; gates use git archive only, removing the .git write tension.
- _gate rule 4 now keeps trust-boundary security findings blocking without a stub run, consistent with the sentence before it.
- git archive of 5e1642f into scratch/arch-gate-rules/r2; pytest -q: 942 passed, 2 skipped (drift test and sentinel rule test included).
- charters/ and cli/wuwei/ byte-identical to .claude/wuwei copies (cmp per file). Runtime lines 2986, unchanged from base.
- Contract: no change to verdict.py or hook.py in this delta; outward wording as judged at dc733e0, Breaking: no.
- Confidence high: docs-only delta, every change traced against the earlier finding, suite green.

## Residual risk
"Whose own process states a runtime line budget" relies on the planner reading the repository's constitution or AGENTS.md; a budget stated elsewhere would be missed, which only skips an advisory check.

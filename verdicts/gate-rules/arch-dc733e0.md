Verdict: FIX
Gate: arch
Item: gate-rules
PR: taoq-ai/wuwei#1105
Head: dc733e0d49d3118fcdf7ad8e38cbb56087a71a51
Confidence: medium
Breaking: no

## Findings
- [medium] charters/planner.md:15 blocks: yes. Failure: the planner charter is product text that the SessionStart hook loads into every workspace (hook.py:304), but the new approval step is unconditional: "check the line budget of each item that adds runtime lines against the headroom (3,000 minus the measured lines); when it does not fit, order a free-lines item first". In a user workspace planning acme/app (no line budget, tens of thousands of lines), the headroom is negative for every item that adds code, so the planner reorders the queue to put a non-existent "free-lines item" first or invents deletion work before it asks plan approval. That contradicts design.md principle 7 ("read each repository's own process and fill only the gaps") and puts a WUWEI-repo budget (constitution, AGENTS.md) into the shipped charter. Fix: scope it to a repository that holds a line budget, for example "for a repository with a runtime line budget (WUWEI: 3,000 lines, per its constitution)"; acceptance 5 still holds.
- [low] charters/lead.md:31 blocks: no. Same scoping gap on the lead side: "runtime lines" is WUWEI vocabulary; scope it the same way as the planner line. Harmless alone (it only asks for an estimate), so a note.
- [low] charters/planner.md:16 blocks: no. The literal 3,000 duplicates the constitution and design.md budget; if the budget is amended the charter drifts silently. Naming the source ("the budget the repository's constitution sets") avoids the copy.
- [low] charters/builder.md:56 blocks: no. "For a guard change, run the route corpus ... tests/fixtures/routes.json" is WUWEI-specific but reads as general; a builder in another repository touching an auth guard finds no corpus. planner.md:33 already scopes the same differential to guards.py or hook.py; reuse that scope.
- [low] charters/sentinel-security.md:16 blocks: no. "A normalisation round" is undefined in the charters, and the wrapper list (cd, env -C, sudo -D) is about WUWEI's own doors; scope to "a change to a path or command guard" so it reads right in other repositories.
- [low] docs/site/concepts/hooks.md:47 blocks: no. Still says "nothing else would wake it when CI finishes" while the Stop line now hedges "unless a check-in or PR subscription is armed"; align the doc with the new wording.
- [low] charters/_gate.md:14 blocks: no. The worktree rule is now stated twice in every gate agent (_common Evidence 4 and _gate rule 3); one copy would do. Line 14 also runs to 154 characters against the file's wrap.
- [low] charters/_common.md:38 blocks: no. `git worktree add` writes worktree metadata into the main clone's .git, a mild tension with Boundaries 1 ("write only the item's worktree or your own verdict file"); `git archive` alone avoids it.

## Probes
- Read the item with wuwei plan show gate-rules; diffed 247d72e..dc733e0 (git diff --stat and full diff of charters, cli, docs, tests).
- git archive dc733e0 into scratch/arch-gate-rules/tree; pytest -q in a copy: 942 passed, 2 skipped (drift test and the new sentinel rule test included).
- Runtime lines (sum of cli/wuwei/*.py lines): 2986 at base 247d72e and 2986 at head; acceptance 4 holds.
- .claude/wuwei/charters and cli files at head are byte-identical to charters/ and cli/ (diff per file).
- Contract check: verdict.parse PR regex unchanged; only FORMAT comment and the error string change, so existing verdicts parse as before. Stop line keeps "nothing will wake this session for the waiting work" and "arm /wuwei-watch"; no code, skill or doc parses the text (grep over cli, skills, docs). Breaking: no, wording only for human readers.
- allowlist.json grants Write to every sentinel, so the Write-tool rule is executable.
- Consistency grep: no "before the PR opens" left outside specs; skills wuwei-rules and wuwei-run carry no conflicting rule; design.md:190 "a change that breaks a budget deletes something first" agrees with the free-lines-first order once scoped.
- Confidence medium: the rules are docs and agree with design and constitution except the unscoped budget; the blocking call rests on reading the planner charter as product text for all workspaces, which hook.py:304 confirms.

## Residual risk
Several new lines (route corpus, normalisation round, line budget) are WUWEI-repo lessons that may belong in .wuwei/standards.md rather than charters; the steward may want a rule for where repo-specific lessons land.

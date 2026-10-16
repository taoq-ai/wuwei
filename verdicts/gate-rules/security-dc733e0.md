Verdict: PASS
Gate: security
Item: gate-rules
PR: taoq-ai/wuwei#1105
Head: dc733e0d49d3118fcdf7ad8e38cbb56087a71a51
Confidence: high

## Findings
- [low] charters/_gate.md:22 blocks: no. The new stub sentence sits after "A trust-boundary security finding always blocks" and ends "without one it is a note", so which wins is left open. The spec's How this fails 3 means the security rule to win, but the charter does not say so. A gate that cannot set up a stub could file a real wrapper bypass of a door as a note. Suggest adding "(a trust-boundary security finding still blocks)" to that sentence. The wording is the approved promise text, and a stub run costs little with Bash, so this does not block.
- [low] charters/_common.md:39 blocks: no. `git worktree add` writes `.git/worktrees/` metadata in the main repository and leaves a worktree registered until someone prunes it. `git archive` is the copy that leaves no trace. This is not a security defect.
- [low] blocks: no. Not changed by this diff: builder.md:21-22 tells the builder to save analysis.md with a shell redirect, because the harness refuses a subagent's Write of a file named like a report. The target is the item's own worktree under specs/<feature>/, so it stays inside Boundaries 1 and gets around no WUWEI door. This PR does not touch it.
- [low] blocks: no. Not changed by this diff: verdict.parse accepts `PR: ../..#3` as repo `../..`, on main and on the branch alike. This is out of scope here and only worth noting if repo ever reaches a path.

## Probes
Read the diff with `git diff 247d72e dc733e0`. Runtime changes are string-only: verdict.py FORMAT line 11 and the PR error at line 48, and the hook.py stop() message. `_verdict_problem` is byte-identical between the trees (diff of the function body), and hook.py differs in 4 lines.
Ran verdict.parse on both trees (git archive copies) over 20 inputs, each at strict False and True: good, bare repo, bare with a trailing note, no slash, #x, empty PR, repo# with no number, ../..#3, a leading space, a/b/c#1, a short head, a bad confidence word, a blocking finding with no Failure, a note with no anchor, a missing Findings section, empty text, binary garbage, a duplicate PR line, and FIX. All 40 results match on repo, pr and every other field, and the error lists match once the old and new wording is normalised.
Ran attestation end to end through hook._verdict_problem in both trees with good, bare-repo and malformed (app#x) verdict files: good and bare return None in both, and malformed gives the same shape error in both apart from the wording.
Ran pytest on the branch copy: 942 passed, 2 skipped. This includes the agents-match-charters drift test, the size budget test and the new parametrized gate-rule test. Ran pytest on the main copy, test_verdict.py and test_hook.py: 120 passed.
Diffed cli/ and charters/ against the vendored .claude/wuwei copies: identical. agents/ against .claude/agents differs only in allowlist.json and ziran-baseline.json (present only in agents/), as on main.
Reviewed the charters for weakened security duties. Main-worktree ban, Write-tool verdicts, mutant re-runs, the route-corpus sha256 in the AUTH sweep and the security normalisation round (path classes and cd, env -C, sudo -D wrappers) all tighten. The heredoc rule sends verdict writing to Write and opens no way around the Bash door. Lead and planner line budgets do not touch security.
Mutants: none. No guard or validation logic changed; only message strings did.
Confidence high: real parses and attestation are identical across both trees, and the full suite passes.

## Residual risk
The stub rule could still be read as overriding the security-always-blocks rule in a narrow case (wrapper or parse bypass with no stub run possible). Nothing else is left.

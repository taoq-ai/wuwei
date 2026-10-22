# Common gate rules

You review one item at one head. You are independent of the builder: judge the diff, the
requirement and the running code, not the builder's summary.

1. Read the item's promise and acceptance with `wuwei plan show <id>` (the plan is the source; a
   brief is a copy). Read the brief's standards lines for your gate, the defects this workspace
   has seen escape, and check each one. Standards lines add checks; rules 3 and 5 alone decide
   what blocks. Review exactly the head sha the brief names: the pushed
   branch or its draft PR before it turns ready (diff it against the default branch), or the PR
   head on a delta after review. If the head moves while you review, start again.
2. At `full` or `smart` complex, probe the builder's `How this fails:` scenarios first.
3. Run checks, probes and mutants in a `git archive <sha>` copy (Evidence 4). For each changed
   guard or validation,
   reverse it in the copy and name the test that fails, or write `not run` with the reason. A
   surviving mutant blocks only when you can name a concrete input the reversed guard lets
   through and the harm it does (that is the `Failure:`). Call code
   equivalent or deletable only after a generated differential probe between the head and the
   change shows 0 differences; a surviving mutant alone is reported as untested, `[low] blocks: no`, with the
   missing test as a note. Re-run every mutant you list as surviving, in a fresh copy, before you
   list it.
4. A change to a parser or a guard carries the probes the repository's own process names for it
   (its `AGENTS.md` or `CLAUDE.md`, and the standards lines in your brief). Re-run them at the
   head you review and report their counts under Probes.
5. Classify each finding against the item's promise. A regression, a violated requirement or a
   trust-boundary defect blocks; a limit or an existing gap is a note (`blocks: no`) for the PR's
   review notes. A finding about how a shell, a
   wrapper or gh parses a command names a run that shows what executes: with a stub program on PATH,
   or gh with `http_unix_socket` at a logging server. Without one it is a
   note; a trust-boundary security finding still blocks.
6. On a delta after a fix, compare with your previous verdict. Weigh each `No change:` answer the
   builder gave on its evidence: close findings the fix resolves, keep closed findings closed
   without new evidence, block only on what the fix broke or left. From the third round on, block
   only on what the last fix changed; a test-only finding on code already judged correct is
   `blocks: no`, collected for one combined final round. Closed findings go under ## Probes
   (`closed: <finding> at <sha7>`); ## Findings holds only open findings, or none.
7. A one-way choice, a goal change or a trust-boundary question the item cannot settle is
   ESCALATE, named in the finding.

## The verdict

This is the one verdict path; a brief never names another. Write it to
`.wuwei/verdicts/<item>/<gate>-<first 7 of head>.md` in this shape with the Write tool, never a
shell heredoc (the Bash door refuses a heredoc that names a door program). Then end your report
with `Verdict file: <that path>`. The path is under the workspace that holds `.wuwei/`.
From a worktree, name the absolute path; WUWEI copies it in.
Never edit a verdict file once written, yours or another seat's: WUWEI counts the bytes it
recorded, so an edit uncounts it. If the file already exists, another seat reviewed the same head:
write yours beside it as `-2.md` (or the next free number). WUWEI reads the file at the hand-back
and refuses a wrong shape, naming the next free file: write the corrected verdict there and hand
back with its `Verdict file:` line.

```
Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>   (or <owner/repo> alone before its draft PR exists)
Head: <the 40-character sha you reviewed>
Confidence: medium
Breaking: no   (arch only; or "yes: <what breaks for which clients>")
Supersedes: <item>/<FIX file at this head>   (PASS only: finding closed outside the diff)

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes. Failure: <the concrete scenario that goes wrong>
- [low] <file>:<line> blocks: no. <a note>
(open findings only, or the single word none)

## Probes
<what you ran and what it showed, and each closed finding, one line each>

## Residual risk
<one or two lines>
```

`Confidence:` is one word, low, medium or high; give its reason under Probes. PASS has no blocking
finding. Each line under Findings is one whole finding, never a sub-bullet or continuation line;
detail goes under Probes. A blocking finding names its `<file>:<line>`. Its text starts with exactly
`Failure: `, its class (CWE, OWASP, contract or requirement id) in parentheses after
the scenario: `- [high] cli/auth.py:42 blocks: yes. Failure: a blank token passes (CWE-287)`. A
note without a place leaves it out, never a padded `:1` anchor:
`- [low] blocks: no. PR body: the Size line gives no reason`. A blocking PR body finding names
`PR-body:0`: `- [medium] PR-body:0 blocks: yes. Failure: no Rollback line (requirement R-3)`.
Calibrate honestly: the steward compares your confidence with what later escaped, and an
overconfident gate earns stricter standards.

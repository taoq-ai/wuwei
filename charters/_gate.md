# Common gate rules

You review one item at one head. You are independent of the builder: judge the diff, the
requirement and the running code, not the builder's summary.

1. Read the item's promise and acceptance with `wuwei plan show <id>` (the plan is the source; a
   brief is a copy). Read the brief's standards lines for your gate (the defects this workspace has seen escape) and
   check each one. Review exactly the head sha the brief names: the pushed branch or its draft PR
   before it turns ready (diff it against the default branch), or the PR head on a delta after review. If the head moves
   while you review, start again at the new head.
2. At `full`, probe the builder's `How this fails:` scenarios first.
3. Run checks, probes and mutants in a copy of the tree at that sha, in a new empty scratch
   directory made with `git archive <sha>` (Evidence 4). For each changed guard or validation,
   reverse it in the copy and name the test that fails, or write `not run` with the reason. A
   surviving mutant blocks only when you can name a concrete input the reversed guard lets through
   and the harm it does (that is the `Failure:`). A mutant that is equivalent, or that you cannot
   turn into a bad input, is `[low] blocks: no` with the missing test as a note. Re-run every
   mutant you list as surviving, in a fresh copy, before you list it.
4. Classify each finding against the item's promise: a regression, a violated requirement or a
   trust-boundary defect blocks; a limit or an existing gap is a note (`blocks: no`) for the PR's
   review notes. A trust-boundary security finding always blocks. A finding about how a shell, a
   wrapper or gh parses a command names a run with a stub program on PATH (or gh with
   `http_unix_socket` pointed at a logging server) that shows what really executes; without one it
   is a note, except a trust-boundary security finding, which still blocks.
5. On a delta after a fix, compare with your previous verdict and weigh each `No change:` answer
   the builder gave on its evidence: close findings the fix resolves,
   keep closed findings closed without new evidence, block only on what the fix broke or left.
   From the third round on, block only on what the last fix changed; a test-only finding on code
   already judged correct is `blocks: no`, collected for one combined final round.
6. A one-way choice, a goal change or a trust-boundary question the item cannot settle is
   ESCALATE, named in the finding.

## The verdict

This is the one verdict path; a brief never names another. Write it to
`.wuwei/verdicts/<item>/<gate>-<first 7 of head>.md` in this shape with the Write tool, never a
shell heredoc (the Bash door refuses a heredoc that names a door program), then end your
report with the line `Verdict file: <that path>`. The path is under the workspace that holds `.wuwei/`; working in a
worktree, name the absolute path you wrote and WUWEI copies it into the workspace. Never edit a verdict file once written, yours or
another seat's: WUWEI counts the bytes it recorded, so an edit uncounts it. If the file already
exists, another seat reviewed the same head: write yours to `<gate>-<first 7 of head>-2.md` beside it
(the next free number) and end with its `Verdict file:` line. WUWEI reads the file when you hand back
and refuses the hand-back if the shape is wrong: write the corrected verdict to the next free
`-2.md` the same way, name it in your `Verdict file:` line, and hand back again. A verdict counts
only as WUWEI recorded it.

```
Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>   (or <owner/repo> alone before its draft PR exists)
Head: <the 40-character sha you reviewed>
Confidence: medium
Breaking: no   (arch only; or "yes: <what breaks for which clients>")

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes. Failure: <the concrete scenario that goes wrong>
- [low] <file>:<line> blocks: no. <a note>   (the <file>:<line> is optional on a note)
(or the single word none)

## Probes
<what you ran and what it showed, one line each>

## Residual risk
<one or two lines>
```

`Confidence:` is one word, low, medium or high; give its reason under Probes. PASS has no blocking finding.
A blocking finding names its `<file>:<line>`; a note without a place in the code leaves it out
(`- [low] blocks: no. <a note>`), never a padded `:1` anchor. Calibrate honestly: the steward compares your confidence with what
later escaped, and an overconfident gate earns stricter standards.

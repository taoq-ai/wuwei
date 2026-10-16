Verdict: FIX
Gate: arch
Item: 1068
PR: taoq-ai/wuwei
Head: 4be5260656160f8624c2d4647fc960131aaf0cba
Confidence: high
Breaking: no

## Findings
- [medium] cli/wuwei/guards.py:78 blocks: yes. Failure: the flag's trigger set misses two places where bash 5.2 reads `<<` as something other than a heredoc, so the scanner still drops a "body" that bash runs. Main 5d7157b refuses all of these and this head lets them through: `a=( [1<<EOF ]=x )\ngit push --force origin x\nEOF`, `a+=( [1<<EOF ]=x )\n...`, `declare -A m=( [k<<EOF ]=v )\ngit push --force origin x\nEOF` (a compound-array subscript, where the `[` follows a space, so it is not joined), and `shopt -s extglob\necho @(a<<EOF )\ngit push --force origin x\nEOF` (an extglob group). Real bash runs the push line in all four, and `guards.pre_tool` returns None for them at this head. This is the class of bypass the item's own acceptance closes (`a[1<<EOF ]=x`, `$[1<<EOF]`), so it is a regression against main. The spec's Assumptions line "A `[` after whitespace ... does not set it" is the decision this input overturns. The shape is right and only the opener set is short. Tried in a scratch copy: adding `|[=?*+@!]\(` to the inline pattern closes all four. The suite still passes (340), and the runtime stays at 3000 lines. The fail-closed cost of that change is that an ordinary `a=(1 2)` then stops later body dropping. Record that under Assumptions.
- [low] cli/wuwei/guards.py:246 blocks: no. Since ee252d7 the unreadable-command refusal text changed: it now says "names a door (git push, gh, wuwei hook, the ledger)" and "put the text in a file (gh --body-file, git commit -F)". This text exists only on this branch and never shipped on main, so it is not a published contract. It now names `-F`, which closes my ee252d7 note.
- [low] cli/wuwei/guards.py:64 blocks: no. Existing gap, also on main: the scanner reads `$'\''` as plain single quotes, so `echo $'\''\ngit push --force origin x\n#'` hides the push inside what it takes for a quoted word. bash runs the push. This is deliberate construction, outside SECURITY.md's cooperative model. Worth a follow-up next to compound-doors.

## Probes
- Suite in a scratch copy at 4be5260 (`git archive | tar`): 340 passed. Runtime `cat cli/wuwei/*.py | wc -l` = 3000, at the budget.
- Contracts since arch-ee252d7. `git diff ee252d7 4be5260 -- cli/wuwei/hook.py` is empty, so the hook JSON, the PostToolUse regex and the ledger kinds are unchanged. Against main, hook.py only reformats the `attest` record (same keys). `deny()` keeps the `{'decision','reason'}` shape. Every refusal text that main has is byte-identical. No new door, flag, config key or file. The `pre_tool` refactors (inlined cwd, `any(map(LEDGER.search, paths))`) behave the same.
- Design fit. design.md section 7 line 123 ("A door that cannot read its evidence stays shut") and SECURITY.md line 17 (cooperative, never isolation). A one-way flag is the simplest honest shape: once set it never unsets, so no shape of paren, case `)` or bracket can reopen body dropping. A stack would need a model of each bracket form, and a mis-pop fails open, which is the failure class of both fix rounds. The flag costs net 0 lines against the depth counter. Its only weakness is completeness of the opener set (finding 1), and a stack shares that weakness.
- Ran 14 extra inputs through the head scanner and `bash -c` with stub `git`/`cat` functions (probes/probe.py). The 4 regressions above, plus the `$'` gap. `[[ a == @(a<<EOF ) ]]` is refused because `[[` joins a `[`. Quoted `"${x}"` and `"$((1))"` before a heredoc agree with bash. `case a in (a<<EOF)` agrees. Re-ran the same inputs on 5d7157b, ee252d7 and 7fd4019: the 4 bypasses go back to ee252d7. I missed them at my previous PASS.
- Mutants in scratch copies, tests/test_guards.py. Never setting the flag: 14 fail. Ignoring the flag at `<<`: 14 fail. Dropping the `(?<=\S)` lookbehind: 1 fails. Removing `\$\{`: 1 fails. Removing `\(\(`: 11 fail. `break` changed to `continue` in the in-order body loop: 1 fails. All killed.
- `git merge-tree origin/main 4be5260` is clean. main moved to 2a306da (release 1.2.1, CHANGELOG and version only).
- Confidence high: each bypass was checked against real bash 5.2.21 and against `pre_tool` on both main and head, and the fix was tried in a copy.

## Residual risk
After the opener fix the scanner still models sh heuristically. A context it does not know that reads `<<` as text could reopen body dropping until the flag is set. ANSI-C `$'...'` quoting stays unmodelled, as on main.

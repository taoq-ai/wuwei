Verdict: FIX
Gate: quality
Item: 1068
PR: taoq-ai/wuwei
Head: 1450f8d985d609624b8be2c80ba40f3210340017
Confidence: medium
Breaking: no

## Findings
- [high] cli/wuwei/guards.py:78 blocks: yes. Failure: the arithmetic fix counts the text `((` and `))` in the whole prefix (`command.count('((', 0, i) <= command.count('))', 0, i)`), including quoted words and comments. A stray `))` before the `<<` cancels the `((` and the `<<` is read as a heredoc again. Input: `echo "))"; echo $((1<<EOF))` + newline + `git push --force origin x` + newline + `EOF`. Head returns segments [['echo','))'], ['echo','$','((','1','))']], so the push line is dropped as data and no door fires; real bash ran the line after the arithmetic (a `touch` ran). Same with `# ))` on an earlier comment line, and with `echo ")) "` before `(( x = 1 << EOF ))`. Main refused all three. The test suite only has the bare forms, so it cannot see this. Fix direction: track the `((` depth in the scan loop itself, outside quotes and comments, rather than counting characters in the raw prefix; add the three inputs above as tests.
- [low] cli/wuwei/guards.py:78 blocks: no. The same count errs the other way too: an unmatched `((` inside a quoted word earlier (`echo '(('`) turns heredoc dropping off for the rest of the command, so a later `cat <<'EOF'` body naming `git push` is read as commands and refused. Fails closed; the depth tracking above removes it as well.
- [low] cli/wuwei/hook.py:216 blocks: no. Unchanged from the previous round: the PostToolUse regex also fires on a command that only mentions `gh pr create` when its output holds a PR URL (a note and a board cache reset). It also now reads a create after a heredoc, which main missed.
- [low] cli/wuwei/guards.py:_unwrap blocks: no. Unchanged: `bash script.sh <<EOF` treats the stdin body as commands, so a body naming `git push` is refused. Fails closed.

## Probes
- Previous round, closed at this head: the two-heredoc bypass (`cat <<A <<'B'` with `$(git push ...)` in the first body) is now refused: the loop breaks at the first body it cannot drop, so later bodies stay commands. `cat <<'B' <<A`, `<<'A' <<'B'`, `<<A <<B` and `<<'A' <<B` variants behave as real sh does (data stays data, the executing `$(...)` is read).
- Previous round, closed: test gaps. In a scratch copy at this head I reversed each guard and the suite named a failing test every time: closing quote left open (the `echo "hi"` case), single-quote backslash rule, backslash-newline join with no space (`git push origin ma\` newline `in`), the `gh repo`, `gh api`, `wuwei hook` and ledger alternatives of DOORS (one test each), the arithmetic prefix check removed (`echo $((1<<EOF))`), the unquoted-`$(` body check removed, and the hint text (`git commit -F`). The in-order `break` reversed is caught only by the unterminated-heredoc test, not a two-heredoc test: the two-heredoc input is also in the suite, so the behaviour is covered either way.
- The hint now names `gh --body-file` and `git commit -F`; the reason string and the AskUserQuestion/Write ledger one-liners (`any(map(LEDGER.search, paths))`, `return DOORS.search(command) and deny(...)`) keep their returns (None when no door is named; `deny` dict otherwise).
- Suite at head in a git-archive copy: 296 passed. Runtime lines: 3000 (`find cli/wuwei -name '*.py' | xargs cat | wc -l`).
- Friction replay of the 366 Bash commands from this session's transcripts was done at the previous head and the parser change since is the heredoc break and the arithmetic prefix, so the earlier result (0 refused, 0 unreadable) was not rerun: unmeasured at this head.
- Simplicity: none to delete; the prefix character count is the one piece to replace with depth tracking.

## Residual risk
The parser is a deny-list over shell syntax; eval, `| bash` and `source /dev/stdin` stay outside the promise and unchanged. After depth tracking replaces the character count, rerun the three stray-`))` inputs.

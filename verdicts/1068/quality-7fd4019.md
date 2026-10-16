Verdict: FIX
Gate: quality
Item: 1068
PR: taoq-ai/wuwei
Head: 7fd4019d5e9116d10c36efc127c192001f481c6e
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/guards.py:78 blocks: yes. Failure: the new depth counter treats every adjacent `))` outside quotes as the end of an arithmetic expression, but two command substitutions can also close with `))`. Input: `echo $(( $(echo $(echo 1))<<EOF ))` + newline + `git push --force origin x` + newline + `EOF`. The `((` opens depth 1, the `))` that closes the two nested `$( )` takes it to 0, the `<<` is read as a heredoc, and the push line becomes one quoted word: segments returns `['echo','1','))<<','git push --force origin x','))']`, so no door fires. Real bash evaluates the arithmetic and then ran the line after it (a `touch` ran; bash printed `1` and a command-not-found for `EOF`). Main refused it. It is contrived, and eval, `| bash` and python -c stay outside the promise, but it is the same class as the two bypasses closed in earlier rounds and is in what the last fix changed. Cheapest sound fix, no extra lines needed: replace the depth with a flag set at the first unquoted `((`, and stop dropping heredoc bodies for the rest of the command once it is set (fails closed; the only cost is a false refusal when a body names a door after an arithmetic expression). Add the input above as a test.
- [low] cli/wuwei/guards.py:78 blocks: no. Mutant: tracking only `((` and never `))` survives. It errs toward reading a body as commands, so `echo $((1+2))` + newline + `cat <<'EOF'` + a body naming `git push` would be falsely refused; no bypass. Missing test: a closed `$((1+2))` followed by a heredoc whose body names a door must pass.
- [low] cli/wuwei/hook.py:216 blocks: no. Unchanged: the PostToolUse regex also fires on a command that only mentions `gh pr create` when its output holds a PR URL (a note and a board cache reset). It also reads a create after a heredoc, which main missed.
- [low] cli/wuwei/guards.py:116 blocks: no. Unchanged: `bash script.sh <<EOF` treats the stdin body as commands, so a body naming `git push` is refused. Fails closed.

## Probes
- Closed from the last verdict: the stray-`))` bypass. All four inputs (`echo "))"; echo $((1<<EOF))`, `echo '))' $((1<<EOF))`, `# ))` line first, `echo ")) "` then `(( x = 1 << EOF ))`) are refused at this head by tests in the suite; quoted and commented parens no longer count because the branch sits after the quote and comment branches.
- Mutants in a scratch copy at this head (full suite each): clamp removed, decrement replaced by +1, decrement replaced by -1 only, `not depth` removed, `))` not tracked as a closer, `((` not tracked, `<<-` tab strip dropped, comment skip dropped, quote close dropped, the in-order `break` dropped. Nine killed, each by a named test (for example the clamp by `x=$(a $(b))` + heredoc, the tab strip by the `cat <<-EOF` case, the quote close by the `echo "))"` case). One survived: not tracking `))` (see the low finding).
- Suite at head in a git-archive copy: 303 passed. Runtime lines: 3000 (`find cli/wuwei -name '*.py' | xargs cat | wc -l`).
- Friction replay at this head, measured: every Bash command in this session's transcripts (437 commands, 144 multi-line, including heredoc PR bodies, spec writes and multi-line python): unreadable by shlex 0, refused by the unreadable rule 0. On main 18 of them silently returned []. Door programs seen by main and not by head: 3 commands, all text inside heredoc bodies or a for-list, correctly dropped. Command used: a script walking `/root/.claude/projects/*/*.jsonl` Bash tool inputs through guards.segments at 7f8a0d7 and at this head.
- Real shell checks: bash ran the line after `$(( $(echo $(echo 1))<<EOF ))`; the earlier `$((1<<EOF))` forms are refused at this head.
- Simplicity: none to delete. The `cwd` inline in `pre_tool` and the shortened `segments` docstring free lines without changing behaviour.

## Residual risk
The parser stays a deny-list over shell syntax; eval, `| bash`, `source /dev/stdin` and interpreter bodies are outside the promise and unchanged from main. If the flag fix lands, rerun the nested-substitution input above.

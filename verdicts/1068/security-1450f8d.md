Verdict: FIX
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: 1450f8d985d609624b8be2c80ba40f3210340017
Confidence: medium

## Findings
- [medium] cli/wuwei/guards.py:78 blocks: yes. Failure: the new arithmetic check, `command.count('((', 0, i) <= command.count('))', 0, i)`, counts raw text, including quoted words and comments. An earlier `))` inside quotes or a comment balances the count, so the `<<` inside `$((1<<EOF))` is taken as a heredoc again and the next lines are dropped as data. Seen in a scratch copy at this head: `echo '))' $((1<<EOF))`, then a line with `git push --force origin x`, then `EOF`. Same with `# ))` on an earlier line. Head passes, and both bash and dash run the force push. Main 7f8a0d7 also passes it, but this delta claims to close `$((1<<EOF))` hiding later lines, the promise is that a newline outside quotes ends a command, and the check it added can be beaten. Fix: keep the `((` depth inside the `_lines` loop, where quote and comment state are already known (count only outside quotes, and comments are already skipped). Add the quoted-`))` case to test_a_command_on_a_later_line_meets_its_door.
- [low] cli/wuwei/guards.py:73 blocks: no. Mutant: dropping the `<<-` tab strip survives the suite. It fails closed: the indented delimiter is not found, so the body is read as commands and the sh <<- test still refuses. A note on the missing test: a passing `cat <<-EOF` with a door-shaped body.
- [low] cli/wuwei/guards.py:54-86 blocks: no. Carried from the previous verdict: gaps that main also has (input piped or fed to a shell, here-strings, eval, shell flags before -c, wrappers that take option arguments, brace and compound bodies, `$(...)` in double quotes, a variable as the program name, some ledger redirects and touch). These are outside this delta. A follow-up item is recommended.
- [low] cli/wuwei/guards.py:245 blocks: no. Closed from the previous verdict: How-this-fails #1 friction remains, and the refusal now names gh --body-file and git commit -F.

## Probes
Previous blocking finding (two heredocs on one line, the first unquoted with `$(...)`, the second quoted): closed. Head now refuses it. I also checked the reversed order and two unquoted heredocs: refused (harness with logging git/gh/wuwei stand-ins, run under bash 5.2 and dash).
Delta probes: `$((1<<EOF))`, `$[1<<EOF]` and `${x:1<<EOF}` followed by a door line are refused at head. A quoted or commented `))` before `$((1<<EOF))` passes at head and at main, and bash and dash run the door (the finding above). A stray quoted `((` before a real heredoc fails closed. The acceptance create-after-heredoc case is refused.
zsh: not run, not installed in this environment (unmeasured).
Suite: 296 passed at head. Runtime: 3000 lines (sum of cli/wuwei/*.py lines).
Mutants (each reversed in a scratch copy, then tests/test_guards.py and tests/test_hook.py run). Killed: break->continue (two-heredoc test), the unquoted `$(` check off (3 tests), the `((` guard removed (2 tests), unreadable-command refusal off (5 tests), continuation join off, comment handling off, shell heredoc body not read (2 tests). Survived: `<<-` tab strip off (equivalent for safety, see the note above).
Confidence is medium: the delta was probed directly and the mutants are mostly killed, but the parser works by deny-list over shell syntax and zsh is unmeasured.

## Residual risk
Any raw-text count in `_lines` that ignores quote state can be defeated the same way. Gaps shared with main remain open until a follow-up item.

Verdict: FIX
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: 7fd4019d5e9116d10c36efc127c192001f481c6e
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:78 blocks: yes. Failure: any `))` lowers the arithmetic depth, even when it closes two single parens rather than the `((`. So `echo $(((1)) <<EOF )`, then a line with `git push --force origin x`, then `EOF` reaches depth 0 at the `<<`, and the door line is dropped as heredoc data. Head passes it, main 7f8a0d7 refuses it, and bash runs the force push. This is a regression this item opens. Fix: keep a small stack in the loop (push on `((` and on a single `(`; a `)` pops a single paren first; an arithmetic level closes only on `))` when a single paren is not on top), and start a heredoc only when no arithmetic level is open. Every unsure case then reads the body as commands, which fails closed.
- [medium] cli/wuwei/guards.py:78 blocks: yes. Failure: same root cause, and the last fix did not cover it. Inside `$(( ))`, a nested group that ends in `))` drops depth to 0 before the arithmetic closes. Examples: `echo $(( (1+(2)) <<EOF ))`, `(( (1+(2)) << EOF ))`, and `echo $(( $(echo $(echo 1)) <<EOF ))`, each followed by a door line and `EOF`. Head passes them, main passes them too, and bash (and dash for the `$(( ))` forms) runs the force push. They block because this round's fix claims to track arithmetic depth so that a `<<` inside `(( ))` is a shift, and these inputs defeat that claim. The stack in the finding above closes them as well.
- [low] cli/wuwei/guards.py:80 blocks: no. Arithmetic without `((` is not tracked. `echo $[1<<EOF]`, then a door line, then an `EOF]` line drops the door line. Head and main both pass it, and bash runs it. The last fix did not change this (third round), so it is a note. The `$[` form is deprecated. A follow-up could treat a `<<` whose word carries `]` or `}` as not a heredoc.
- [low] cli/wuwei/guards.py:54-88 blocks: no. Carried from the earlier verdicts: gaps that main also has (input piped or fed to a shell, here-strings, eval, shell flags before -c, wrappers that take option arguments, brace and compound bodies, `$(...)` in double quotes, a variable as the program name, some ledger redirects and touch). A follow-up item is recommended.
- [low] cli/wuwei/guards.py:78 blocks: no. Closed from the previous verdict: a quoted or commented `))` before `$((1<<EOF))` is now refused (probed: `echo '))' ...`, `echo "))"; ...`, `# ))` on an earlier line). The `<<-` tab strip mutant is now killed.

## Probes
Suite: 303 passed at head. Runtime: 3000 lines (cat cli/wuwei/*.py | wc -l).
Depth probes (harness: guards.pre_tool at head and main compared with real bash 5.2 and dash running each command against logging git/gh/wuwei stand-ins in empty scratch dirs):
Refused at head, as they should be: `$(( (1+2) <<EOF ))`, `$(( ((1)) <<EOF ))`, `$(( $(echo 1) <<EOF ))`, `x=$(echo $(echo a))` before `$((1<<EOF))`, arithmetic spanning a newline, a `((` or `))` inside a dropped heredoc body before `$((1<<EOF))`, and `for ((i=1<<EOF; ...))`.
Passes at head, correctly (bash runs no door): `((true); true)` before a quoted heredoc; `echo $((1))<<EOF` (a real heredoc).
Passes at head while bash runs the door: the three inputs in the blocking findings, and `$[1<<EOF]` with an `EOF]` line.
Mutants, each reversed in a scratch copy with tests/test_guards.py run. Killed: clamp removed, decrement removed, depth check removed (6 tests), tab strip off, comment skip off, depth counted inside quotes. None survived.
zsh: not installed here, unmeasured.
Confidence is medium: the probes aimed directly at the new depth logic and found a concrete regression, but a deny-list parser over shell syntax may have more such cases.

## Residual risk
Paren-matching heuristics that do not model nesting are easy to beat. A stack that fails closed on any open arithmetic level is the smallest sound shape. Gaps shared with main remain open until a follow-up item.

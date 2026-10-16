Verdict: FIX
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: ee252d7f974a2b80b927f5497e651ba85a3a3c4b
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:73-75 blocks: yes. Failure: when one line has two heredocs, the first unquoted with a `$(...)` door in its body and the second quoted, each body is matched by searching from the same position (command[i + 1:]) instead of one after the other. The second delimiter's match takes in the first body, so the `$(git push --force origin x)` line becomes quoted data. Seen in a scratch copy: `cat <<A <<'B'` + newline + `$(git push --force origin x)` + newline + `A` + newline + `x` + newline + `B`. Head passes it, main 7f8a0d7 refuses it, and bash really runs `git push --force origin x`. This is a new bypass at head, and it is the builder's own How-this-fails #3. Fix: read the bodies in order, each one starting where the last one ended, and treat any body that holds `$(` or a backtick as unquoted unless its own delimiter was quoted. Add this case to test_a_command_on_a_later_line_meets_its_door.
- [low] cli/wuwei/guards.py:66 blocks: no. A backslash then CRLF is not joined as a continuation, so head reads `git push \` CRLF `--force origin x` as a plain `git push` and lets it through (main refused it as one argv). bash does not join it either: it ran only `git push`, with no force. So head now matches what really runs. No harm, but noted as a change from main.
- [low] cli/wuwei/guards.py:54-82 blocks: no. Several gaps pass on both head and main, so this item did not open them (a heredoc or echo piped to sh/bash, here-strings, process substitution, eval, bash -c with extra flags such as -lc / -ec / --, wrappers with option arguments (env -u, env -C, nice -n, timeout, stdbuf), brace groups / if / for / function bodies, `!`, `$(...)` inside double quotes, a variable used as the program name, and the `>&` / `&>>` / touch ledger writes). Some are in the builder's stated residual. Brace groups, compound bodies and a quoted `$(...)` are close to this item's promise but not named in its acceptance. Recommend a follow-up item for these.
- [low] cli/wuwei/guards.py:268 blocks: no. Builder's How-this-fails #1 is real friction: a `gh pr create --body "$(cat <<'EOF' ...)"` that shlex cannot tokenize is now refused. The message points to --body-file, so the door fails closed with a way forward.

## Probes
Suite at head: 285 passed. At main: 264 passed (`python3 -m pytest -q` in scratch copies made with git archive).
Harness: guards.pre_tool from each tree (origin and branch stubbed, gh offline) compared with real bash running each command against logging fakes for git, gh and wuwei on PATH, in empty scratch dirs. About 150 commands.
All of this item's acceptance scenarios are refused or passed as specified at head. Single-line CRLF, comments, quoted and unquoted heredocs, `<<-`, `bash <<'EOF'`, backticks, unquoted `$( )`, `bash -c` with an embedded newline and continuation joins all meet their door at head.
Head-only bypass: the two-heredoc case above (head pass, main deny, bash ran the force push).
Mutants: not run separately. The two-heredoc probe covers the body-overlap logic and no test in the suite catches it.
Confidence is medium: the probing was broad but not exhaustive, and the run ended early.

## Residual risk
Many shell constructs still get past the guard on both trees (see the low note above). The parser is a deny-list over shell syntax, so similar heredoc-ordering edge cases may remain after the fix.

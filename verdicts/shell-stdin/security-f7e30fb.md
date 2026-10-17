Verdict: PASS
Gate: security
Item: shell-stdin
PR: taoq-ai/wuwei#1115
Head: f7e30fbfd02531e999589f7cf383310cabb8579d
Confidence: high

## Findings
- [medium] blocks: no. Existing gap, not a regression: `env -S 'bash -s'` (or `/usr/bin/env -S 'bash -e'`) fed on stdin with a door command runs the push and passes at base and head (probe class S1, 564 of 564 ran; same count at 86135fa). env -S splits its string, but the wrapper reader sees 'bash -s' as one word, so no shell is named and no UNREAD is added. Follow-up: split an env -S argument before the wrapper reads it.
- [high] blocks: no. Existing gap outside this promise: backtick command substitution runs a door program the guard never reads (`echo` + a backtick-wrapped push to main, `x=` + a backtick-wrapped push; class S4, 24 of 24 ran, identical at base). `$(...)` is read, backticks are not. Recommend a plan item: treat an unquoted backtick as unreadable so the raw-text rule applies.
- [low] blocks: no. Existing gap: a `-c` body that is a variable or a substitution (`C=...; bash -c "$C"`, `bash -c "$(echo ...)"`, `xargs -I{} bash -c {}`) is read as a program named `$C` or `{}`, never as unread (classes D1 36/36 and S2 36/36 ran, identical at base). A `-c` body holding `$`, a backtick or `{}` could join the UNREAD rule.
- [low] blocks: no. Existing gap outside the promise: `source`/`.` on /dev/stdin or `<(...)`, and `eval`, run door commands the guard passes (class S3, 60 of 60, identical at base).
- [low] blocks: no. Limit by design: the infra ask and the leak check do not read the text fed to a stdin shell (`bash <<< 'terraform apply'`, a token piped to `sh`; class L2, 96 of 96 each, identical at base). The new UNREAD only feeds the door-word rule; the promise covers door programs only.
- [low] blocks: no. Non-security: `bash x.sh && git push origin feature` and `bash --command ...` (an invalid bash option) are now refused, since a bare shell makes the line unread. The item is declared breaking and the route corpus keeps every verdict, so this is over-refusal, which fails closed.

## Probes
- Builder probes re-run in a git archive copy (security-shell-stdin/{base,head}): genprobe 912 generated, 803 ran the push, 586 holes at 86135fa, 0 at head. probe2 A 4032/3840 ran, 3420 holes to 0; B infra and B leak 576/467-468 ran, 300 holes to 0; C infra and C leak via shells 3420 holes at both (existing, see L2).
- probe3 (security-shell-stdin/probe/probe3.py, real bash, stub git, terraform and curl on PATH, 16 threads). Head results first, base after the slash.
- N named fd, push: {fd} {a_b} {A1} {_} {FD_2} {X9_y} {__} {a1b2} {ABC} {z} 3 10 0 2, each glued to every REDIRECTS operator (including &>, &>>, <<<, <<), x 4 targets x 18 positions (start, end, mid-argv, ;, &&, ||, |, ( ), { }, !, &, if, $( ), time, nice, env, for). 8316 generated. Exact argv `git push origin main` ran 4968 times; 0 holes at head, 2580 at base. The first round counted 84 holes on loose matching (`git 0&>x push ...`); bash runs that as `git 0 push`, the same argv the guard reads, so it is no push. The class now matches the exact argv.
- N infra after named fd: 7392 generated, 4416-4500 ran, 0 holes (2304 at base). N leak: 7392 generated, 4500 ran, 0 holes (2304 at base).
- S stdin shells: bash, sh, dash, /bin/bash, /usr/bin/bash, /bin/sh, env bash, /usr/bin/env bash, /usr/bin/env -S bash, env -S bash, command/exec/nice/timeout/stdbuf/nohup bash, bash -O extglob, --norc, --noprofile, -i, --posix, -o pipefail, +e, -eu, -x, -v, sh -s, dash -e, env FOO=1 bash, BAR=1 bash. Feeders: <<< glued and spaced, a pipe, |&, 0<<<, a leading <<<, <(...), < <(...), /dev/stdin, -s, -, cat |, {fd}<x prefix. Both quotes, 6 positions. 5748 generated, 5736 ran, 0 holes (5736 at base).
- Added classes for the holes found (S1 env -S quoted, S2 xargs -I{} sh -c {}, S3 source/./eval, S4 backticks, D1 -c body in a variable). The hole counts are identical at base and head, so no class is a regression.
- D -c detection (-c, -lc, -xc, -ce, -e -c, -c --, --norc -c, -O extglob -c, -o pipefail -c, -c Q _, --command, -c glued; bash, sh, env bash): 432 generated, 324 ran, 0 holes (48 at base: -O extglob -c and the like are now caught by the UNREAD rule).
- L leak, infra and push checks beside the new UNREAD shapes (before, after, &&, a pipe, a subshell with {a_b}): infra 35/32 ran 0 holes, leak 35/32 ran 0 holes, push 35/32 ran 0 holes (14 holes each at base). Ad hoc: a .wuwei/ledger target after {fd}>, {a_b}>> and {A1}<> is still denied; `{fd}>x wuwei hook` is denied; acceptance 3 negatives pass.
- ksh, mksh, busybox and zsh are not installed: real execution under them is unmeasured (zsh goes by name like bash in the guard).
- Mutants, each in a fresh copy, against tests/test_guards.py. All were killed. Dropping the {name} alternation fails 10, e.g. test_a_push_after_a_named_fd_redirect_meets_the_push_door. Dropping the bare-shell UNREAD fails 8, e.g. test_a_shell_fed_its_commands_naming_a_door_is_refused. Keeping {name} in the replacement fails 10. Treating only bash as a shell fails 2 (sh -s, dash -x). Adding UNREAD only for an argument-less shell fails 6.
- Route corpus: tests/fixtures/routes.json sha256 9ea9491c...01dff8 is unchanged from base. The verdict dump of 168 routes has sha256 4d0c79dc...11dd5 at both base and head. Full suite at head: 1237 passed, 2 skipped. Runtime is 2976 lines. Vendored guards.py is identical to cli/wuwei/guards.py.
- Confidence high: the change only adds deny paths (UNREAD feeds the door-word rule; stripping {name} keeps redirect targets), and every changed guard has a killing test. A hole that appears only at head would change this.

## Residual risk
The raw-text rule cannot see obfuscated fed text (split quotes, rev, base64). Backticks, env -S quoted strings, variable -c bodies, source/eval and infra or secrets inside fed text remain existing gaps for follow-up items.

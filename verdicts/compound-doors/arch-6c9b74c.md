Verdict: FIX
Gate: arch
Item: compound-doors
PR: taoq-ai/wuwei
Head: 6c9b74cb5e2bb7e241182bf53362e771bc063f27
Confidence: high
Breaking: yes: the Bash door (the PreToolUse hook decision) now refuses commands that passed on main. Intended: a door command inside a for/while/until/if body, a brace group or after `!`, inside `bash -lc`/`sh -ec`/`bash -e -c`, or after a wrapper's options (`timeout 60 gh pr merge 5`). Over-read, recorded under the spec's Assumptions: a wrapper followed by a program no door reads whose arguments name one (`nohup echo git push --force origin x`, `xargs -I{} echo gh pr merge 5`, `timeout 60 ./run.sh rm .wuwei/ledger/x`). And any unreadable `sh -c` body whose raw text names a door program, read-only ones included (`bash -c "echo it's; gh pr view 5"`), now gets the one-line hint deny. Agent sessions that send these shapes get a deny without changing anything. This follows the precedent of item 1068's arch verdict: a tightened door is still a behavior change for existing clients, so the PR needs the Announcement: line and the owner's breaking: confirmation.

## Findings
- [high] cli/wuwei/guards.py:89 blocks: yes. Failure: the first-program rule matches `Path(a).name` against READ on every word after a wrapper, `VAR=value` words included, and the old loop that dropped assignments after a wrapper is gone. So `env GIT_SSH=/usr/bin/ssh git push --force origin x` now reads `ssh` as the program (the basename of `GIT_SSH=/usr/bin/ssh`), and the force-push door never runs. The same happens with `env SHELL=/bin/bash git push --force origin x` (read as `bash` with no -c) and `sudo EDITOR=/usr/bin/sed gh pr merge 5 --admin` (read as `sed`). On origin/main all three are refused (force push refused; --admin refused). On this head pre_tool returns None for all three. This is a regression against the item's promise and a trust-boundary bypass a cooperating agent can plausibly write (`GIT_SSH=` and `SHELL=` are ordinary env settings). Fix: skip words matching `[A-Za-z_]\w*=.*` in the first-program search, or drop leading assignments again after the jump, and pin these three shapes in tests/test_guards.py.
- [low] cli/wuwei/guards.py:21 blocks: no. READ is built from the existing sets (SHELLS, INFRA, NETWORK, WRITERS), so those stay one source. But the literals 'git', 'gh', 'wuwei', 'sed' and the `startswith('python')` rule (line 89) repeat by hand what `bash()` reads at lines 236-262. A program a future door adds to `bash()` must be added to READ as well, or wrapped forms of it pass. A comment or a test that ties the two together would hold it.
- [low] cli/wuwei/guards.py:22 blocks: no. The UNREAD marker fits every caller of segments(). guards.bash checks it at line 229 and skips it as a segment with no argv. hook.post_tool (hook.py:209) indexes argv[:1], which is empty for the marker, so it reads as no command. hook.door (hook.py:368) reads DOOR_WORDS from the raw text and never calls segments, so the #1081 fail-closed path is unchanged. A literal `> '<an unreadable sh -c body>'` segment compares equal to the marker, but all it can do is apply the raw-text deny to a command that names a door, which only refuses more.
- [low] cli/wuwei/guards.py:89 blocks: no. Pre-existing on main, not widened here: a wrapper option value whose basename is a door-read program still hides the command (`env -C /home/user/wuwei git push --force origin x` reads `wuwei`; `sudo -u git gh pr merge 5 --admin` reads `git`). Worth a line among the SECURITY.md residuals.
- [low] SECURITY.md:45 blocks: no. The runtime budget line changes from 2,500 to 3,000 lines. That is outside the item's promise but corrects existing drift: design.md:176 and AGENTS.md already say 3,000.

## Probes
- Copied the tree at 6c9b74c and origin/main into the scratch directory with git archive. The full suite at the head passes: 431 passed (`pytest -q`).
- Ran segments() on 26 shapes on both trees (scratchpad/a-cd/probe.py). It found the assignment-basename regression and confirmed the documented over-read (`nohup echo git push origin main` reads `git push origin main`).
- A scratch pytest (test_zz_arch_probe.py) against both trees showed pre_tool deny on main and None on the head for the env GIT_SSH=, env SHELL= and sudo EDITOR= shapes. The over-read shapes are denied on the head and pass on main. `sudo apt install gh` and `command -v gh` pass on both.
- Mutant: removing `UNREAD in parts` (line 229) fails test_an_unreadable_sh_c_body_naming_a_door_is_refused.
- Mutant: removing the reserved words from the line 85 regex fails the loop/if door tests.
- Mutant: removing the python prefix from line 89 fails test_the_records_are_protected[payload7].
- Callers traced with grep for `segments(`, `_unwrap` and `UNREAD` over cli/: guards.bash, hook.post_tool, and _unwrap's own recursion. The .claude vendored guards.py matches cli/wuwei/guards.py byte for byte.
- SECURITY.md and docs/design.md describe the new reading and the residual shapes the promise names.
- Confidence is high because the regression reproduces with pre_tool on both trees.

## Residual risk
The first-program rule reads by basename, so any path-like word after a wrapper can stand in for the program. Once assignments are skipped, the remaining cases are option values (`-C dir`, `-u user`), which already pass on main and belong under the SECURITY.md residuals.

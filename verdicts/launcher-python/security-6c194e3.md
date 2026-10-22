Verdict: PASS
Gate: security
Item: launcher-python
PR: taoq-ai/wuwei#1241
Head: 6c194e3bd290209e6b6041f6f3b0a3bd4de66759
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:383 blocks: no. Older gap, moved to its own plan item: `python3 -m wuwei hook SubagentStop` and `bin/wuwei.cmd hook ...` get past the forged-hook refusal at main and at head.
- [low] bin/wuwei:6 blocks: no. The `-V` probe still has no timeout of its own (the same as a hanging python3 on main), and a crash after a good `-V` exits 139, not 2 (the same as main).

## Probes
- closed: cmd.exe working-folder search (CWE-427) at 6c194e3. Line 6 of both bin/wuwei.cmd and .claude/wuwei/bin/wuwei.cmd is `set "NoDefaultCurrentDirectoryInExePath=1"`, right after `setlocal` and before the first `call :fits`. The two files are byte-identical (cmp). All 31 lines are CRLF.
- Coverage, from reading the file: the variable is in the batch process's environment from line 6 until the script exits. setlocal only scopes it to this script, which still holds it at every lookup below. `call :fits` runs in the same cmd process, so its bare `py` and `python` names are covered. The `for /f ('call %* -V')` command runs in a child `cmd.exe /c`, which gets a copy of the parent's environment block at that moment, variable included, so the child's lookup is covered too. The `%py%` run line (line 19) is resolved by the same parent process, so it is covered. Python and any process it starts inherit the variable as well, which only narrows their lookups. A `WUWEI_PYTHON` holding an explicit `.\` path is still honoured, as the environment owner chose. Static only: no cmd.exe on this runner.
- Delta 20ef6f1..6c194e3: 3 files, +19 lines (the two .cmd lines in each copy, and two tests in tests/test_launcher.py). Nothing else moved. guards.py, hook.py and routes.json are unchanged, so the route differential from the last round (388 passed at main and head, corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1) still holds.
- tests/test_launcher.py at the head (git archive copy): 21 passed.
- Mutant: the NoDefaultCurrentDirectoryInExePath line deleted from both .cmd copies in a fresh archive copy. test_the_windows_entry_never_runs_a_py_or_python_from_the_working_folder fails (1 failed, 20 passed): killed. The test pins the presence and position of the line, not cmd.exe behaviour.
- The stderr-version test (Python 2.7.18 on stderr is named in the exit-2 line) is present and passes. It does not affect security.
- Earlier notes carried from the 20ef6f1 verdict and unchanged in this delta: the any-PATH-directory python3.x preference, the unquoted `%tried%` echo, and the BatBadBut class for wuwei.cmd called with untrusted arguments.
- Confidence medium: the fix follows cmd.exe's documented behaviour, but no Windows run confirms it.

## Residual risk
Windows paths are reviewed only statically. Forged-hook spellings stay open until the guards.py follow-up lands.

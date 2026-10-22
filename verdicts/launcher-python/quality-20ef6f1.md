Verdict: PASS
Gate: quality
Item: launcher-python
PR: taoq-ai/wuwei#1241
Head: 20ef6f1dd44c0d0fe71d0d5dcff9987c5b1637d0
Confidence: medium
Breaking: no

## Findings
- [low] tests/test_launcher.py:0 blocks: no. Untested: dropping `2>&1` from `fits` in bin/wuwei (mutant `-V 2>/dev/null`) survives all 19 launcher tests, because every shim prints its version to stdout. Python 2 prints to stderr; the interpreter is still refused (empty version never matches), but the exit-2 line would show it with no version, against the promise "naming each interpreter tried and its version". Add a shim that prints `Python 2.7.18` to stderr and assert `python3 2.7.18` in the line. The head is correct (checked by probe).
- [low] tests/test_launcher.py:0 blocks: no. Untested: dropping `-P` from the exec line (mutant `-I -S -c`) is killed only by the text assertion `'-I -P -S -c' in text` in test_the_launcher_is_posix_sh, not by a behavioural test. A shim that records its argv and a check for `-P` would pin it.
- [low] bin/wuwei.cmd:0 blocks: no. The cmd.exe path (`:fits` parse, `call %* -V 2^>^&1`, quoted WUWEI_PYTHON with spaces) is unmeasured: no Windows host. Tests pin its bytes (CRLF), its order, and that its Python bootstrap is the same AST as the sh one, but not its version parse. Acceptance 4 is run only through an sh `py` shim, which is the Git Bash path.
- [low] bin/wuwei:11 blocks: no. The sh list adds python3.15 and python3.14 beyond the promise's list, and also tries `py -3` and `python` on Linux and macOS. The spec records this as a choice (Q at spec.md:62); a `python` that is Python 2 is refused by the version check. Note only.

## Probes
- Ran at the head in the builder's worktree: `pytest -q tests/test_setup.py tests/test_launcher.py tests/test_hook.py` gave 612 passed in 43.58s. The launcher file alone is 19 tests under sh, dash and bash, none skipped.
- Acceptance 1 is pinned by test_an_old_python3_first_on_path_gives_way_to_python3_12, with used.txt showing only python3.12 ran and the call denied as usual. Acceptance 2 by test_only_an_old_python3_exits_2_naming_it_and_the_version_wuwei_needs: exit 2, one line, `python3 3.9.6`, `Python 3.11 or later`, and no `Unknown option`. Acceptance 3 by test_wuwei_python_names_the_interpreter_when_it_is_3_11_or_later (with a path containing a space) and the old WUWEI_PYTHON fall-through test. Acceptance 4 by test_windows_with_only_the_py_launcher_runs_wuwei_with_py_3 (the shim exits 9 unless `-3` comes first). Doctor naming by test_the_doctor_names_the_interpreter_the_hooks_use.
- Version parse probe (the `fits` function extracted to a copy, run under dash, 12 outputs): `3.11.0rc1` fits; `3.12.0a1` fits; `3.20.1` fits; `4.0.0` fits; `3.10.12+` refused and printed as `3.10.12+`; `3.9.6`, `3.2.5`, `3.1.5`, `3.10.0`, `2.7.18` refused. Stderr-only `Python 2.7.18` refused and shown with its version. Stderr-only 3.12.1 fits. A command that prints a version but exits 1 is `not found`. A path with a space works. Edge `3.100.0` is refused, which is irrelevant until Python 3.100.
- POSIX sh: `sh -n`, `dash -n`, `bash -n` all pass; no `[[`, `local`, `function`, `${x//`, `<<<` or `source` in bin/wuwei; `a && b || c` in `fits` and `[ ] && arg=-3 || arg=` behave as intended for the cases probed. bin/wuwei and .claude/wuwei/bin are identical (diff -r clean).
- .cmd read: CRLF throughout, `.gitattributes` keeps the bytes (`*.cmd -text`); the Python bootstrap is AST-equal to the sh one (tested); order WUWEI_PYTHON, py -3, python; fail-closed exit /b 2 with the same message shape; `set /a` errors on a non-numeric version leave major at 0, so "not found" is kept. No defect found by reading; not run (see the cmd note above). The `commandWindows` key is documented in the spec with a source for Codex, and Claude Code ignores it per the spec's own evidence.
- Mutants (fresh copies of the head, tests/test_launcher.py only, bin/wuwei mutated): remove `3.1[1-9]*` pattern killed by test_an_old_python3_first_on_path_gives_way_to_python3_12[sh]; blank the `not found` fallback killed by test_only_an_old_python3_exits_2_naming...[sh]; drop `-P` killed only by the text test (see finding 2); drop `2>&1` survived (finding 1). The builder's 12 of 12 claim was not re-derived beyond these four.
- Old doctor assertion: `('ok', 'fired 5s ago')` became `f'fired 5s ago under {sys.executable} {version}'`. That follows the promise's last clause ("wuwei doctor names the interpreter the hooks use"), and the value comes from the hook process's own sys.executable stamped in hook.pre_tool, not from a constant fitted to the output. The python row now also shows the executable, which test_launcher checks. Fit to the promise, not to the code.
- Not run: the full suite (the time box and the brief); the route differential (guards.py is not changed; hook.py only adds one cache_put in the existing try).
- Simplicity: none to delete. The `fits` helper is used for WUWEI_PYTHON and the loop. The python3.15/3.14 entries are a documented choice, one list entry each. The extra cache_put per PreToolUse is one small write inside the existing try, needed by the doctor row.

## Residual risk
The cmd.exe version parse and quoted-path handling are unmeasured on a real Windows host. The stderr version capture and the `-P` flag are pinned by no behavioural test.

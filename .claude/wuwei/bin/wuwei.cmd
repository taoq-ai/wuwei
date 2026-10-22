@echo off
rem WUWEI hook entry for a harness that runs hooks through cmd.exe (Codex on Windows); bin/wuwei is its sh twin.
rem It runs WUWEI under WUWEI_PYTHON when that is Python 3.11 or later, else py -3, else python.
setlocal DisableDelayedExpansion
rem cmd.exe looks in the working folder before PATH; a py.bat there must never stand in for Python.
set "NoDefaultCurrentDirectoryInExePath=1"
for %%i in ("%~dp0..") do set "root=%%~fi"
if not exist "%root%\cli\wuwei\" >&2 echo wuwei: cli not found under "%root%"
if not exist "%root%\cli\wuwei\" exit /b 2
set "tried=" & set "py="
if defined WUWEI_PYTHON call :fits "%WUWEI_PYTHON%"
if not defined py call :fits py -3
if not defined py call :fits python
if defined py goto run
>&2 echo wuwei: WUWEI needs Python 3.11 or later (set WUWEI_PYTHON to one); tried%tried:~1%
exit /b 2
:run
set "PYTHONEXECUTABLE="
%py% -I -P -S -c "exec('import runpy, sys; sys.path[:0] = sys.argv[1:3]; del sys.argv[1:3]\ntry: runpy.run_module(\x22wuwei\x22, run_name=\x22__main__\x22, alter_sys=True)\nexcept Exception as exc:  # a PreToolUse hook that fails before it can judge refuses: only exit 2 blocks the call\n    if sys.argv[1:] != [\x22hook\x22, \x22PreToolUse\x22]: raise\n    sys.stderr.write(f\x22wuwei hook PreToolUse: {type(exc).__name__}: {exc}\x22[:300] + \x22\\n\x22); sys.exit(2)')" "%root%\cli" "%root%" %*
exit /b %errorlevel%

:fits
rem Sets py to the interpreter %* when it is Python 3.11 or later; else adds it and its version to tried.
set "v=not found" & set "major=0" & set "minor=0"
for /f "tokens=1,2" %%a in ('call %* -V 2^>^&1') do if "%%a"=="Python" set "v=%%b"
for /f "tokens=1,2 delims=." %%a in ("%v%") do set /a "major=%%a, minor=%%b" >nul 2>&1
if %major% EQU 0 set "v=not found"
if %major% GTR 3 set "py=%*"
if %major% EQU 3 if %minor% GEQ 11 set "py=%*"
if not defined py set "tried=%tried%, %* %v%"
exit /b 0

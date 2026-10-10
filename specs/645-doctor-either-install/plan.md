# Implementation Plan: the same doctor answer from either install

**Branch**: `645-doctor-either-install` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

`doctor` hands itself over to the install `.wuwei/executable` names: when that launcher is
another runnable copy, `doctor.run` replaces its process with it (`os.execve`), same options,
and sets `WUWEI_DOCTOR_FROM` to the invoked launcher. The handed-over doctor adds one `ok` row
naming the invoked copy, itself, and the copy that last measured plugin integrity (the
SessionStart hook's verdict). Every row is then computed by the pointer's own code, so the
answer cannot depend on the copy that was invoked. Every seat brief gets one constant `Doctor:`
header line. No change to `integrity`, the hooks, the traces guard or any existing row.

## Prerequisite

#601 on main (it provides `integrity.recorded(root)`, `integrity.registered`,
`integrity.launcher` and the `installs` row). Merge `origin/main` into the worktree before
T001. If #601 is still not on main, add only `integrity.recorded` to `cli/wuwei/integrity.py`
exactly as #601 defines it, and list it under Deferred:

```python
def recorded(root):
    """The launcher .wuwei/executable names, or '' when missing, empty or unreadable (#601)."""
    try:
        return (Path(root) / '.wuwei/executable').read_text(encoding='utf-8').splitlines()[0]
    except (OSError, UnicodeError, IndexError):
        return ''
```

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, config key, event kind or state key.
`os.execve` keeps the working directory, the terminal and the environment, so `--workspace`
(exported as `WUWEI_WORKSPACE` by `__main__._main`), `--fix` host confirmation on `/dev/tty`
and `WUWEI_SESSION_ID` carry over. The launcher `bin/wuwei` runs `python3 -I`, which ignores
`PYTHON*` variables but keeps `WUWEI_*`.

## Constitution Check

- I stdlib only: yes. `os.execve` is not `subprocess`; `tests/test_integrity.py
  test_core_never_imports_subprocess` stays green.
- II exits: unchanged. The `invoked` row is `ok` (exit unchanged); a failed hand-over is a
  `warn` row (exit 1), never a silent fallback.
- III one behaviour, one function: hand-over in `doctor._hand_over`, the row in
  `doctor._invoked`, the brief line in `brief.DOCTOR`.
- IV test first: every task pair below puts the test first.
- V ponytail: one hand-over at the one spot every row routes through (the process), instead of
  a plugin parameter threaded through `integrity`. No abstraction.
- VII security: the pointer is already executed by the git hooks and SwiftBar, `init` refuses a
  symlinked pointer and `protect_state` refuses seat writes to it; no guard changes.

## Changes, by file

### `cli/wuwei/commands/doctor.py`

1. Module constant next to `REINSTALL`:
   `FROM = 'WUWEI_DOCTOR_FROM'  # #645: set on the handed-over doctor; the launcher that was invoked`
2. New `_hand_over(args)` above `register`:
   - return `[]` when `os.environ.get(FROM)` is set;
   - `root = workspace.find_workspace()`; return `[]` on `FileNotFoundError` or `ValueError`;
   - `here = integrity.PLUGIN / 'bin/wuwei'`, `target = integrity.recorded(root)`;
   - return `[]` unless `target` is non-empty, `os.path.isfile(target)`,
     `os.access(target, os.X_OK)` and `Path(target).resolve() != here.resolve()`;
   - argv: `[target, 'doctor']` plus `--fix`, `--json`, `--widget` when set, `--apply
     <args.apply>` and `--section <args.section>` when set (rebuilt from `args`, never from
     `sys.argv`);
   - `sys.stdout.flush()`, `sys.stderr.flush()`, then
     `os.execve(target, argv, {**os.environ, FROM: str(here)})`;
   - on `OSError as exc` return one row:
     `_row('install', 'invoked', 'warn', f'could not hand doctor over to {target} '
     f'({type(exc).__name__}); this report comes from {here}', f'{target} doctor')`.
     Never print the exception message.
3. New `_invoked(root)`, called at the end of `_install` (`rows += _invoked(root)` before
   `return rows`):
   - `invoked = os.environ.get(FROM, '')`, `here = integrity.PLUGIN / 'bin/wuwei'`; return `[]`
     when `invoked` is empty or `Path(invoked).resolve() == here.resolve()`;
   - `measured`: `json.loads((root / '.wuwei/integrity/verdict.json').read_text())['plugin']`
     when `root` is not None and it is a string, else `'unknown'` (catch `OSError`,
     `ValueError`, `KeyError`, `TypeError`);
   - return `[_row('install', 'invoked', 'ok', f'invoked as {invoked}; reported by {here}, the '
     f'launcher .wuwei/executable names; plugin integrity last measured from {measured} (the '
     'SessionStart hook measures it)')]`.
4. `run(args, confirm=None)`: after the option check and before `diagnose`,
   `failed = [] if confirm is not None else _hand_over(args)`; then
   `rows = diagnose(args.section) + failed`. Nothing else in `run` changes.

Must not change: `diagnose`'s signature and its in-process callers (`setup.py:601`,
`shepherd.py:553`, `plan.py:253`), every existing row, `_row`'s fix rewrite, the `--fix` allow
list, exit codes.

### `cli/wuwei/brief.py`

1. Constant next to `LIVE`:
   ```python
   # #645: one doctor for every seat; install findings belong to the owner.
   DOCTOR = ('Doctor: run the launcher in .wuwei/executable with doctor; another copy hands over '
             "to it. Its Install rows and its workspace executable row are the owner's: name them "
             'in your handoff, never as a Next: step, and never run their fix.')
   ```
2. In `write`, append it right after the `Scratch:` header line (every role passes there):
   `header.append(DOCTOR)`.

Must not change: the header's first-blank-line cut, `launch_prompt`, `mandate`.

### `docs/site/reference.md` (Doctor section, after "It works before there is a workspace ...")

Add: "When `.wuwei/executable` names another runnable install, `doctor` runs from that install
with the same options, so every copy prints the same rows; that report adds an `invoked` row
naming the copy that was invoked and the copy that last measured plugin integrity (the
SessionStart hook). Seat briefs carry a `Doctor:` line: install findings are the owner's."

### Not changed

`cli/wuwei/integrity.py` (beyond the prerequisite fallback), `cli/wuwei/guards/traces.py`,
`cli/wuwei/commands/init.py`, hooks, charters, the `installs` row of #601.

## Test notes for the builder

- `doctor.run` with no `confirm` now may call `os.execve`. Before T002, grep the suite for
  `doctor.run(` and `['doctor'` (`tests/test_doctor.py`, `tests/test_cli_known_command.py`,
  `tests/test_setup.py`, others) and confirm each runs with a pointer equal to
  `integrity.PLUGIN / 'bin/wuwei'`, a missing pointer, or no workspace. The `ws` fixture in
  `tests/test_doctor.py` writes the pointer as the patched plugin's launcher, so it does not
  hand over. A test that would replace the pytest process must set the pointer or patch
  `os.execve`.
- Patch `os.execve` with `monkeypatch.setattr(doctor.os, 'execve', fake)` where `fake` raises a
  test-local exception carrying `(path, argv, env)`; assert on that.
- Run `tests/test_reasons.py` and `tests/test_tone.py` after the doctor and brief changes:
  `doctor.py` is person-facing (no "you" in row values; fixes name a step) and brief text has a
  sentence budget.

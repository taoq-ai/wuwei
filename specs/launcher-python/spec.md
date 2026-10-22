# Feature Specification: the hook launcher finds a Python 3.11 or later on Windows, macOS and Linux

**Feature branch**: `leone/launcher-python`
**Item**: launcher-python, tier standard, goal G-2, expedite
**Input**: Eugenio Galioto, a Codex user, 2026-10-22: the hooks used the wrong Python interpreter, one
without the -P flag, and that blocks his Codex sessions. The owner, the same day: the plugin must work
on Windows, macOS and Linux.

## The promise in my words

`bin/wuwei` checked only that some `python3` exists, then ran `python3 -I -P -S`. `-P` came in Python
3.11. When the first `python3` on the hook's PATH is older (macOS `/usr/bin/python3` 3.9, Ubuntu
22.04's 3.10), Python stops with "Unknown option: -P" and exit 2, and an exit 2 from PreToolUse
blocks every tool call. Codex runs hooks through the login shell (`$SHELL -lc`), whose PATH can
differ from the user's interactive shell.

After this change the launcher picks its interpreter:

1. `WUWEI_PYTHON` when it is set and reports 3.11 or later;
2. else the first at 3.11 or later among python3.15, python3.14, python3.13, python3.12,
   python3.11, python3, `py -3` and python (sh, for macOS, Linux and Git Bash on Windows);
   `py -3`, then python (`bin/wuwei.cmd`, for cmd.exe on Windows);
3. with none, it exits 2 with one line that names each interpreter tried with its version (or "not
   found") and says WUWEI needs Python 3.11 or later.

It keeps `-I -P -S`, unsets `PYTHONEXECUTABLE`, and keeps the fail-closed bootstrap: a PreToolUse
hook that fails before it can judge exits 2. `-P` only ever reaches a 3.11 or later interpreter,
because only those are chosen. Codex on Windows runs each hook's `commandWindows` through cmd.exe,
so `hooks/hooks.json` gains that entry, pointing at `bin/wuwei.cmd`. `wuwei doctor` names the
interpreter it runs under, and the interpreter the last PreToolUse hook ran under.

The acceptance scenarios, restated:

1. `python3` on PATH is 3.9 and `python3.12` is also there: a hook runs under python3.12 and judges
   the call as usual.
2. Only a 3.9 `python3`: the hook exits 2 with a line naming `python3 3.9.6` and "Python 3.11 or
   later".
3. `WUWEI_PYTHON` names a 3.11 or later interpreter: that interpreter runs WUWEI.
4. Windows with only the py launcher: `py -3` runs WUWEI.

## Clarifications

### Session 2026-10-22

- Q: How do the harnesses run plugin hook commands on Windows? A: Claude Code runs a shell-form
  `command` through Git Bash, or through PowerShell when Git Bash is not installed (Claude Code hooks
  reference, "Exec form and shell form" and "Failed hooks on Windows without Git Bash",
  code.claude.com/docs/en/hooks.md, read 2026-10-22). Codex runs `%COMSPEC% /C "<command>"`
  (cmd.exe) on Windows and `$SHELL -lc "<command>"` elsewhere, uses `commandWindows` instead of
  `command` on Windows when present, and replaces `${CLAUDE_PLUGIN_ROOT}` in the text (openai/codex
  at 9a8a85bc, `codex-rs/hooks/src/engine/command_runner.rs` `build_command` and
  `default_shell_program`, `discovery.rs`, `config/src/hook_config.rs`). The Codex docs site was not
  reachable from this session.
- Q: Which hooks.json form works on both? A: `command` stays `"${CLAUDE_PLUGIN_ROOT}"/bin/wuwei hook
  <event>` for sh and Git Bash; `commandWindows` is `"${CLAUDE_PLUGIN_ROOT}\bin\wuwei.cmd" hook
  <event>`, read only by Codex on Windows. `claude plugin validate` (2.1.308) passes the plugin with
  the extra key.
- Q: How is the version read? A: `<interpreter> -V`, which every CPython answers, Python 2 included,
  without running site or any file from the working directory. A shim can answer it the same way.
- Q: WUWEI_PYTHON set but too old? A: The search goes on, and the failure line names it with its
  version.
- Q: Why python3.15 and python3.14 beyond the item's list? A: They are released or due, and a newer
  minor should not lose to an old `python3`.

## User Scenarios & Testing

### US1: an old python3 never blocks the session (P1)

Acceptance 1 and 3 under sh, dash and bash; an old `WUWEI_PYTHON` falls through to the search.

### US2: no fitting interpreter says why (P1)

Acceptance 2, and no interpreter at all: exit 2, one line.

### US3: Windows (P1)

Acceptance 4 through the sh launcher (Git Bash), with a `py` shim. `bin/wuwei.cmd` holds the same
bootstrap (checked by AST) in the order `WUWEI_PYTHON`, `py -3`, python, and its bootstrap fails
closed when run.

### US4: the doctor names the interpreter (P2)

## Requirements

- FR-001: `bin/wuwei` selects the interpreter as above and exits 2 with the one line when none fits.
- FR-002: `bin/wuwei.cmd` does the same for cmd.exe; `hooks/hooks.json` names it in `commandWindows`.
- FR-003: Both keep `-I -P -S`, the unset `PYTHONEXECUTABLE` and the fail-closed bootstrap.
- FR-004: `wuwei doctor` names its interpreter and the one the hooks last used.
- FR-005: The runtime grows by at most 6 lines; the sh launcher is POSIX sh.

## Assumptions

- Claude Code ignores `commandWindows`. Evidence: `claude plugin validate` 2.1.308 passes with it,
  and fails on a bad `type`, so it reads the hooks file. Overturned if a Claude Code release rejects
  unknown hook keys.
- Codex on Windows runs `commandWindows` through cmd.exe with the plugin root substituted (source
  above). Not run on real Windows: no Windows host here. Overturned by a Windows run that fails.
- Claude Code on Windows without Git Bash runs the `command` in PowerShell, where it does not parse.
  That is the case on main too; it belongs to the cross-platform item.
- `*.cmd -text` in `.gitattributes` keeps the CRLF bytes, so the release manifest hashes match on
  every platform.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; the `hook-python` cache file
is per machine and ignored by older versions.

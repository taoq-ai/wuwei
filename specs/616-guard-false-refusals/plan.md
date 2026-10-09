# Implementation Plan: guard false refusals on a published merge and on read-only gate reads

**Branch**: `616-guard-false-refusals` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Two narrow changes on existing functions: `push_commits` excludes commits any
remote-tracking ref reaches, and `verdict.check_write` skips read-only Bash calls through the
shared classifier and lints Bash-scanned gate files by their own names. Six checksum tools
join `shell.READ_ONLY`.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, config key, event
kind or command. Real git in `tmp_path` for the push range test (as `tests/test_vcs.py` and
`tests/test_git_hook.py` already do).

## Constitution Check

- I stdlib: no import changes; git is still reached only through the adapter's allowlisted
  `_run`.
- II exits: unchanged three-state results; a git failure on the new argv is exit 2 as before.
- III one behaviour one function: the range stays in `push_commits` (read by the PreToolUse
  guard, the native pre-push hook and `pr` actions through `push_check`); read-only stays in
  `shell.classify`/`shell.reads`, now also read by the verdict guard.
- IV test first: each regression test runs red before its change.
- V simplicity: two argv words, one early return, one keyword change, six set members.
- VII security: no new wall under any posture; the only checks narrowed are a read of
  already-published commits and a lint of calls that write nothing. Interpreter snippets,
  redirects and write programs still reach the lint.

## Design

### adapters/vcs/git.py

- `push_commits.log(base)`: `_run(repo, 'log', '-z', _HEAD_FORMAT, base + '..' + local_sha,
  '--not', '--remotes', '--')`. `--not` placed after the range negates only `--remotes`
  (checked with git 2.43 on a scratch repository: the range is unchanged, every commit on a
  remote-tracking ref drops out).
- `_run` allowlist: the `_HEAD_FORMAT` branch moves from the generic
  `('log', '-z', format_arg, rev, '--')` case to its own case
  `('log', '-z', format_arg, rev, '--not', '--remotes', '--')` with the same base and tip
  validation; the generic case keeps `_LOG_FORMAT` only.

### cli/wuwei/guards/verdict.py

- In the Bash branch, after the `gate-` relevance check:
  `if shell.classify(command, cwd=cwd).readonly: return CLEAN, ''` (the import is local,
  like the rest of the module's lazy imports).
- The Bash scan passes `role=''` to `lint_file`; Write/Edit and SubagentStop keep `role`.

### cli/wuwei/shell.py

- `READ_ONLY` adds `shasum`, `sha1sum`, `sha256sum`, `sha512sum`, `md5sum`, `cksum`.

### Users of READ_ONLY and classify (reviewed)

- `protect_state._write_targets` and `_owner_action` readers: a checksum tool has no write
  target and runs nothing, so treating it as a reader is correct.
- `shell.unread` (commit/push and PR guards) and `hook` levelling (I10): a checksum call is
  read-only, so it is never refused as unparsed; correct.
- `security.reads_honeytoken` keeps its own reader list; unchanged.
- `guide.py` reads `commands.READ_ONLY` (CLI paths), not `shell.READ_ONLY`.

### Docs

- `docs/site/reference.md`: one paragraph under Item worktrees (the commits the push
  identity check reads) and one under Gate verdict layout (when the lint runs, and that a
  read-only Bash call is not linted).

## Tests

- `tests/test_vcs.py`: `test_invariant_push_identity_reads_only_unpublished_commits`: a bare
  remote, `main` with a GitHub-committed commit pushed, a feature branch (pushed once, then
  more owner commits and `git merge origin/main`); `push_commits` with the tracking ref and
  as a new branch returns only the feature's commits, `push_check` passes; a commit by
  another identity on no remote is returned and refused.
- `tests/test_vcs_guard.py`: the replay steps' argv still names the range; the argv now ends
  in `--not --remotes --` (asserted).
- `tests/test_verdict.py`: `test_invariant_read_only_bash_never_lints` (`cat`, `grep`,
  `shasum` of a failing gate: clean, no events); `test_invariant_bash_write_lints_by_file_name`
  (`cp` and a redirect still lint and record; a `sentinel-quality` caller writing beside a
  valid security gate is clean). `test_bash_lints_every_daily_gate_even_when_not_named` and
  `test_daily_gate_scan_records_findings_and_unreadable_files` change their `echo` commands
  to a write (`echo ... > out.txt`), since a bare `echo` is now a read.
- `tests/test_shell.py`: the checksum tools classify read-only; `shasum x > y` does not.

# Feature Specification: the transcript guard leaves Claude Code's memory folder writable

**Feature branch**: `fix/memory-writable`
**Item**: memory-writable (issue #1196), tier full, goal G-2
**Input**: since 5.0.0 (#1172) `guards.harness` refuses every write under `~/.claude/projects`. That
folder also holds Claude Code's auto-memory (`<project>/memory/*.md` and `MEMORY.md`), so a planner
cannot record owner feedback that should outlive the session.

## The promise in my words

The guard keeps refusing writes to the harness's transcript files under `.claude/projects`: the
session `*.jsonl`, the subagent transcripts and `tool-results/`. It stops refusing a write to a
file in `<project>/memory/`, for Edit and Write and for the Bash writes the guard reads. Reads pass
as before. The pass is narrow: the path must be a plain literal, and it must still land directly in
a memory folder of the account's projects folder once links are read. A path that only looks like
memory (`memory/../x.jsonl`, a `memory` that is a link, an encoded or globbed segment) stays refused.

The acceptance scenarios, restated:

1. Edit or Write on `~/.claude/projects/<p>/memory/note.md` or `MEMORY.md` passes.
2. A Bash append or redirect to the same memory files passes.
3. A write to `<p>/<session>.jsonl`, a subagent transcript or `tool-results/`, in any spelling, is
   refused as today.
4. `memory/../<session>.jsonl`, a symlink named `memory`, or an encoded `memory` segment pointing at
   a transcript is refused.

## How this fails

1. A link staged in memory and followed in the same Bash call. `ln -s ../s.jsonl memory/n.md &&
   echo x >> memory/n.md` passes both checks if every writer gets the memory pass, because the link
   does not exist yet when the guard resolves the path. The pass is therefore given only to
   redirects and to `tee`, `sed -i`, `truncate` and `rm`, none of which makes a link. `ln`, `mv`,
   `cp`, `find` and `python` keep the old refusal. The probe's mutant that gives every writer the
   pass shows 236 holes under real bash; the head shows none.
2. A working directory in or below memory climbs out. `cd memory && echo x >> ../s.jsonl` writes a
   transcript through a relative path the guard cannot place. The working-directory hold
   (`held`, from the session cwd, `cd`, `pushd`, `-C`, `--chdir`, `-D`) never takes the pass, so
   every write after one of those into memory is refused, as on main.
3. The guard and the shell disagree on where `~` or `$HOME` points. The guard expands `~` and
   `$HOME` with the hook process's `HOME`, which the session's shell inherits, and then requires the
   resolved path to lie under `ws.PROJECTS` (the password database's home). A command that sets
   `HOME` itself before its `~` expands could point the shell elsewhere; that only matters when the
   other home holds a link staged outside the guards' sight, and it is listed under what stays
   open in SECURITY.md.

## Clarifications

### Session 2026-10-20

- Q: Which files count as memory? A: a file directly in `<project>/memory/` under the account's
  projects folder (`ws.PROJECTS`), after links are read. Claude Code keeps memory flat
  (`MEMORY.md` and one file per entry), so a deeper path (`memory/sub/x.md`) and `memory` itself
  are refused.
- Q: Which spellings get the pass? A: a literal path that starts with `~/`, `$HOME/`, `${HOME}/`
  or `/` and holds only word characters, `.`, `/`, `@`, `+` and `-`. `//`, `/./` and `..` are
  allowed because the path is resolved before the check. The guard reads a Bash word after quote
  and backslash removal, as sh does, so `"$HOME"/...` and `~/'.claude'/...` pass. A glob, a brace
  or `%` is refused, as are relative paths (they resolve against the hook's working directory, not
  the shell's).
- Q: How is "a symlink named memory" refused? A: by `os.path.realpath` of the expanded path: a
  `memory` link to its project folder resolves the write to the project folder, which is not a
  memory folder. A file link in memory to a transcript resolves to the transcript. `realpath` is
  non-strict, so a path that does not exist yet keeps its lexical form, and a loop does not raise.
- Q: Which Bash writers get the pass? A: redirect targets, and the words of `tee`, `sed -i`,
  `truncate` and `rm`. Not `ln`, `mv`, `cp`, `find -delete/-exec` or `python`, which can create a
  link. `dd of=` and `chmod`, `shred` keep the refusal too (no use case; fail closed).
- Q: Does the refusal text change? A: yes. A seat that meets the refusal on a memory write (a `cp`
  or a write after `cd`) learns which routes pass: Write, Edit, a redirect, `tee`, `sed -i`,
  `truncate` or `rm` on the literal path, from outside memory.

## User Scenarios & Testing

### US1: Edit and Write on a memory file pass (P1)

Acceptance 1: Write, Edit and MultiEdit on `<p>/memory/note.md` and `MEMORY.md`.

### US2: Bash writes to a memory file pass (P1)

Acceptance 2: `>>`, `>`, `tee -a`, a pipe into `tee`, `sed -i`, `rm -f`, `truncate`, `bash -c`
and `env A=1` around them, for `~`, `$HOME`, `"$HOME"`, `${HOME}`, `//`, `/./` and `x/..`.

### US3: transcripts stay refused (P1)

Acceptance 3: the existing transcript tests, plus `tool-results/`, a subagent transcript and a
project folder named `memory` with its own `tool-results/`.

### US4: look-alikes stay refused (P1)

Acceptance 4: `memory/..`, a `memory` link, a file link in memory, a folder link in memory,
`%6demory`, `memory%2f..`, a glob or brace, a relative path, `$X`, a staged link (`ln`, `mv`,
`cp -P`), `python`, `find -delete`, and a working directory in or below memory.

## Requirements

- FR-001: `guards.harness` takes `keep`; with it, a literal path that resolves to a file directly
  in `<project>/memory` under `ws.PROJECTS` is not a transcript write.
- FR-002: Edit, Write, MultiEdit and NotebookEdit paths and Bash redirect targets use `keep`; Bash
  writer words use it only for `tee`, `sed`, `truncate` and `rm`.
- FR-003: The working-directory hold never uses `keep`.
- FR-004: The refusal names the memory routes that pass.
- FR-005: The runtime grows by at most 3 lines.

## Assumptions

- Memory is flat: only files directly in `memory/` need the pass (Claude Code's layout today).
  Overturned if Claude Code writes memory subfolders.
- `cp`, `mv`, a glob, a brace and a write after `cd` into memory stay refused. The issue needs Edit
  and a Bash append, and every refused route has a passing one named in the refusal. Overturned
  if the owner wants `cp` into memory.
- The hook's `HOME` is the shell's `HOME` (both inherit the harness's environment), and a memory
  pass needs it to equal the password-database home. Overturned by a harness that sets a different
  `HOME` for its shell.
- A hard link from a memory file to a transcript, made outside the guards' sight, is residual risk
  in the same class as the symlinks SECURITY.md already lists. Overturned if the gates want an
  `st_nlink` check.

## Rollback

Revert the merge commit and re-vendor `.claude/`. No config key, ledger kind or file format changes.

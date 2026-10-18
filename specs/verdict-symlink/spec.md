# Feature Specification: the worktree verdict copy-in refuses a symlink under .wuwei/verdicts

**Feature branch**: `fix/verdict-symlink`
**Item**: verdict-symlink (issue #1113), tier full, goal G-2
**Input**: `hook._verdict_problem` copies a verdict a sentinel wrote in a worktree into the main
workspace's `.wuwei/verdicts/`. It builds the copy path, then calls `copy.exists()`,
`copy.read_bytes()` and `copy.write_bytes()`, which all follow symlinks. A link planted at the copy
path, at a folder between it and `verdicts/`, or at `verdicts/` itself makes the hook write a file
outside the verdicts folder, for example into `.wuwei/ledger/`.

## The promise in my words

When a sentinel hands back a verdict written in a worktree, the hook copies it in only along a path
with no symlink in it. The check covers the copy itself, every folder between it and `verdicts/`,
and `verdicts/` itself. The copy path is built under the resolved root, so a path with no link
in it also resolves under the resolved verdicts folder: the promise's `copy.resolve()` condition
follows from the link check. A path that fails the check is refused, and the refusal
names the copy path and says to remove the link. Nothing is written in that case. A path that
passes is written to a temporary file beside the copy and moved into place with `os.replace`
(`ws.atomic_write`). So a link planted at the copy path after the check is replaced, never
followed. A plain worktree verdict is copied and attested exactly as before.

The acceptance scenarios, restated:

1. The main workspace holds a link `.wuwei/verdicts/x/quality-abc1234.md` that points to a file
   outside `verdicts/`. A sentinel hands back a worktree verdict at the same relative path. The
   hook refuses, and the file the link points to stays unchanged (also when it did not exist yet).
2. The main workspace holds a link `.wuwei/verdicts/x -> .wuwei/ledger`. The same hand-back is
   refused, and no file under `.wuwei/ledger` is added or rewritten by the copy.
3. A plain worktree verdict is still copied in and attested.

## How this fails

1. A link is planted between the check and the write. At the copy path itself, `os.replace` swaps
   the link for the new file, so the target is not touched. At a parent folder, the rename can go
   through the link. The hook runs on the owner's machine, so an attacker would need write access
   to `.wuwei/` and a race window of a few system calls. This is residual risk, recorded in the PR.
2. A legitimate setup symlinks `.wuwei/` or `.wuwei/verdicts/`, for example to share it between
   clones. Those copy-ins are now refused. Today a symlinked `.wuwei/` already fails at the
   attest, because `path.relative_to(root)` raises after `resolve()`. So the change only rules out
   a symlinked `verdicts/` folder, which the item's assumption says no corpus payload uses.
3. A check built on `resolve()` misses a link loop: on Python 3.13 a non-strict `resolve()`
   returns a looping parent unchanged, and on 3.11 it raises. The check therefore reads each
   component with `is_symlink()` (an `lstat`), which sees a loop as a link. The loop probes on
   3.13 and 3.11 are refused with the link message.

## Clarifications

### Session 2026-10-18

- Q: Is `.wuwei/verdicts` itself being a symlink refused? A: Yes. A link at `verdicts/` pointing to
  `.wuwei/ledger` would put every copy into the ledger folder, and `verdicts.resolve()` hides it.
  The copy path is built under the resolved root and every component is checked with
  `is_symlink()`, so the `verdicts/` link is caught too. Components above the resolved root are
  never links, because `resolve()` returned them.
- Q: Is a link that stays inside `verdicts/` refused? A: Yes. The promise says no symlink between
  the copy and `verdicts/`, whatever it points to.
- Q: Does the check change verdicts written in the main workspace (no copy-in)? A: No. That path is
  read, never written, and already has to resolve under `verdicts/`. The ledger door is outside
  this item.
- Q: Where does the temporary file go? A: `ws.atomic_write`, the workspace's existing helper: a
  `.name.pid.tmp` file beside the copy, then `os.replace`. It now takes bytes as well as text, so
  the verdict bytes are copied unchanged.
- Q: What does the refusal say? A: `<copy> passes through a symlink under <verdicts>/: remove the
  link, then hand back again.`

## User Scenarios & Testing

### US1: a planted link at the copy path is refused (P1)

Acceptance 1, for a link to an existing outside file and for a dangling link.

### US2: a planted link at a parent is refused (P1)

Acceptance 2, for `verdicts/x -> ledger` and for `verdicts -> ledger`.

### US3: a link planted after the check is replaced, not followed (P1)

A link planted at the copy path between the check and the write is replaced by the copied file.
The file the link pointed to stays unchanged.

### US4: a plain worktree verdict is copied as before (P1)

Acceptance 3, held by the existing test
`test_a_verdict_written_in_a_worktree_is_copied_into_the_workspace_and_attested`.

## Requirements

- FR-001: `_verdict_problem` refuses the copy-in when the copy path or any folder above it, built
  under the resolved root, is a symlink. The refusal names the path and says to remove the link,
  and nothing is written.
- FR-002: The copy is written with `ws.atomic_write` (temporary file beside it, then `os.replace`).
- FR-003: `ws.atomic_write` accepts bytes as well as text.
- FR-004: The runtime grows by at most 3 lines and stays at 3,000 or fewer.

## Assumptions

- Worktree verdict paths never legitimately pass through a symlink under `verdicts/` (from the
  item). Overturned if a corpus payload does.
- A symlinked `.wuwei/` is not a supported setup: the attest already fails for it today. The check
  refuses its copy-in too. Overturned if the owner wants to support a linked workspace folder.
- A one-line change to `ws.atomic_write` (bytes as well as text) is inside the promise's "the write
  goes to a temporary file beside it and os.replace". Overturned if the owner wants hook.py alone.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger kind or file format changes.

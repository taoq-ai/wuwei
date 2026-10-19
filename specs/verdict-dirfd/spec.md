# Feature Specification: the verdict copy-in walks .wuwei/verdicts with directory file descriptors

**Feature branch**: `fix/verdict-dirfd`
**Item**: verdict-dirfd, tier full, goal G-2
**Input**: the security gate on #1137 at 200f361. A parent of the copy path swapped for a link to
`.wuwei/ledger` between the hook's `lstat` walk and `os.replace` still lands the write in the
ledger. On Python 3.11 and 3.12 a link loop at `.wuwei/verdicts` raises RuntimeError outside the
`except` in `hook._verdict_problem`, so SubagentStop fails open with no `verdict.missing` row. The
security gate on #1144 added two more fail-open paths in the `free()` helper of the same function.

## The promise in my words

When a sentinel hands back a verdict it wrote in a worktree, the hook copies it into the main
workspace without ever following a link, even one swapped in after the hook's own link check. The
write opens the workspace root, then each folder below it (`.wuwei`, `verdicts`, the item folder)
relative to the one above, with `O_DIRECTORY | O_NOFOLLOW`. A missing folder is made with `mkdir`
relative to its parent first. The temporary file is unlinked and then created with
`O_CREAT | O_EXCL | O_NOFOLLOW` relative to the last folder's descriptor, and `os.replace` renames
it with `src_dir_fd` and `dst_dir_fd` set to that descriptor. A folder swapped for a link before
its `open` makes the open fail, and the copy-in is refused; one swapped after its `open` no longer
matters, because the write goes through the descriptor of the real folder. A RuntimeError from
resolving a looping path is caught and refused like an OSError, so the hand-back is refused and,
when the block cannot reach the seat, `verdict.missing` is recorded. `sync.pull` (sync.py:82)
writes under `.wuwei/verdicts/` too, a folder a seat writes, so it walks the same way from `.wuwei`.

The acceptance scenarios, restated:

1. A background process swaps a parent of the copy path (`.wuwei/verdicts/x`, and in a second run
   `.wuwei/verdicts`) between a folder and a link to `.wuwei/ledger`. 2000 copy-ins run at the
   head. No file under `.wuwei/ledger` appears or changes.
2. On Python 3.11, `.wuwei/verdicts` is a link loop. A seat hands back a worktree verdict. The
   hand-back is refused and `verdict.missing` is recorded (no `hook.error`).

Added by the caller from the #1144 security gate, inside the promise's "fails closed": `free()`,
which names the next free `<stem>-N.md`, lists the folder once instead of once per candidate, and
returns a refusal text when no number from 2 to 998 is free or the folder cannot be listed.
Before, it raised StopIteration or PermissionError, and two of its three call sites sit outside
the `try`, so the hook failed open with `hook.error` and the seat was never told.

## How this fails

1. A legitimate setup links a folder below the walk's root, for example `.wuwei/verdicts` shared
   between clones. The hook copy-in already refused that at main (the `lstat` check). `sync.pull`
   did not: it now raises OSError at that file, the cloud SessionStart wrapper (`hook._sync`)
   prints it and goes on, and later files in that pull are not written. `wuwei sync` prints
   `wuwei sync: <reason>` naming the file the pull was writing, exits 1 and skips the push (fix
   round 1; it printed a traceback before). A linked `.wuwei` itself still syncs, because the
   pull's walk starts at `.wuwei`.
2. A platform without `renameat`, `mkdirat`, `unlinkat` or `openat` raises NotImplementedError,
   which no `except` catches, so the hook would fail open. Linux and macOS support all four, and
   `O_NOFOLLOW` already ruled out Windows at main.
3. After the copy-in the hook reads the verdict back through its path (`path.read_bytes()`),
   which still follows a parent swapped in after the write. The read can pick up a different file
   of the same name: the bytes the seat could have written itself, or a file under the ledger that
   then fails the verdict shape. No write follows the link. Residual risk, recorded in the PR.

## Clarifications

### Session 2026-10-18

- Q: Which folder is trusted at the top of the walk? A: For the hook, the resolved workspace root:
  `.wuwei` is the first folder opened with `O_NOFOLLOW`, consistent with the existing link check.
  For `sync.pull`, `.wuwei` itself (opened following links), so a linked workspace folder still
  syncs and only the folders a seat can write are held. Every other caller passes no root: the
  file's own folder is made and opened as before, so their behaviour is unchanged.
- Q: Does sync.py:82 write under a folder a seat can write? A: Yes. `sync.files` takes every file
  under `.wuwei` but `LOCAL` and `.tmp` names, so `verdicts/` travels on the state branch, and
  sentinels write `verdicts/`.
- Q: What does the seat see when a folder is a link at write time? A: The existing refusal "the
  verdict must be a readable file under <verdicts>/ (got <path>)". No new text, so the runtime
  budget holds.
- Q: What does `free()` name when no number is free or the folder cannot be listed? A: "a new name
  of your own (no -2 to -998 beside it is free, or <folder> cannot be listed)", inside the same
  refusal sentence, so the hand-back is refused either way.
- Q: Why not `openat2` with `RESOLVE_NO_SYMLINKS`? A: Python's stdlib has no binding for it; the
  per-component `O_NOFOLLOW` walk gives the same guarantee for the folders below the root.

## User Scenarios & Testing

### US1: a parent swapped after the check is never followed (P1)

Acceptance 1. A unit test swaps `verdicts/x` or `verdicts` for a link to the ledger right after
the link check (at `copy.exists()`); the ledger is unchanged and the hand-back is refused. The
race probe (`race_probe.py`) runs it with a real swapping process, 2000 copy-ins per level.

### US2: a loop at .wuwei/verdicts fails closed (P1)

Acceptance 2, on 3.11, 3.12 and 3.13, plus a test that raises RuntimeError from `resolve()` at the
verdicts folder and at the seat's path on any version.

### US3: no free name is a refusal, never a hook error (P1)

All of -2 to -998 taken, or the folder unlistable, at each of the three call sites (copy-in,
another seat's verdict, shape refusal): refused, `verdict.missing` when active, no `hook.error`.
The folder is listed once per `free()` call.

### US4: a pull never writes through a planted link (P2)

`sync.pull` with `.wuwei/verdicts/x` linked to the ledger raises OSError and writes nothing there.

## Requirements

- FR-001: `ws.atomic_write(path, text, root=None)` opens each folder of `path` below `root` with
  `O_DIRECTORY | O_NOFOLLOW` relative to its parent's descriptor, making a missing one with
  `mkdir(dir_fd=...)` first, and creates and renames the temporary file relative to the last one.
- FR-002: The temporary name stays `.{name}.{pid}.{threading.get_ident()}.tmp`, unlinked first,
  then created with `O_CREAT | O_EXCL | O_NOFOLLOW` at 0o666.
- FR-003: With no `root`, the file's folder is made and used as the root, as before.
- FR-004: The verdict copy-in passes the resolved workspace root; `sync.pull` passes `.wuwei`.
- FR-005: `_verdict_problem` resolves the verdicts folder inside its `try` and catches
  RuntimeError with OSError and ValueError.
- FR-006: `free()` lists the folder once and returns a refusal text on OSError or StopIteration.

## Assumptions

- The `free()` fixes belong in this item (the caller's brief, from the #1144 security gate:
  "fails closed"). Overturned if the planner wants them as their own item.
- A pull that stops at a planted link is the right failure: the link means tampering, and the
  rest of the pull is retried at the next session. Overturned if the owner wants a pull to skip
  the one file and go on.
- The runtime budget is +10 for the item. This change adds 18 (see plan.md Lines): the walk needs
  a `mkdir` per folder the item's estimate did not count, the `free()` fix adds 4, and naming the
  file a stopped pull was writing adds 3 (fix round 1, less 1 from the docstring). Overturned if
  the planner holds the item to 10, in which case the `free()` fix splits out.
- Under the SemVer policy (#1154), a pull that refuses a write through a planted link is a patch:
  it refuses a write it used to make. The PR carries it as a release note, not a breaking change.
  Overturned if the owner rules that a working linked setup is an outward contract.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger kind or file format changes.

# Implementation Plan: the verdict copy-in walks .wuwei/verdicts with directory file descriptors

**Branch**: `fix/verdict-dirfd` | **Spec**: `specs/verdict-dirfd/spec.md`

## Summary

`ws.atomic_write` takes an optional trusted `root` and walks the folders below it by directory
descriptor. The hook's copy-in and `sync.pull` pass a root. `_verdict_problem` catches the 3.11
loop error and `free()` stops raising.

## Technical Context

Python 3.11 stdlib (`os.open`, `os.mkdir`, `os.unlink` and `os.replace` with `dir_fd`). Tests in
tests/test_hook.py and tests/test_sync.py. Runtime cap 3,400 lines; main d7c4f43 is at 2,993.

## Constitution Check

- I. Stdlib only: yes, no `ctypes` in the runtime (the race probe uses it to swap atomically).
- III. An auditor: no new door; the hand-back check stays in `_verdict_problem`.
- V. Test first: the new tests ran red on main's code (10 on 3.13, plus the loop test on 3.11).
- VI. Budgets: no config key; runtime 2,993 to 3,009.

## Design

- `atomic_write(path, text, root=None)`: `root` defaults to the file's folder, made first with
  `mkdir(parents=True, exist_ok=True)` as before. Open `root` with `O_RDONLY | O_DIRECTORY`. For
  each part of `path.parent.relative_to(root)`: `os.mkdir(part, dir_fd=fd)` (FileExistsError
  ignored), then `os.open(part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW, dir_fd=fd)` and close the
  parent. The tuple assignment `fd, up = os.open(...), fd` leaves `fd` on the parent when the open
  raises, so the `finally` closes exactly one descriptor on every path.
- Then `os.unlink(temp, dir_fd=fd)` (FileNotFoundError ignored), `os.open(temp, O_WRONLY |
  O_CREAT | O_EXCL | O_NOFOLLOW, 0o666, dir_fd=fd)`, write, and
  `os.replace(temp, path.name, src_dir_fd=fd, dst_dir_fd=fd)`.
- A link at a folder makes the `O_NOFOLLOW` open fail with ELOOP (ENOTDIR on some kernels), an
  OSError the hook's `except` already turns into a refusal.
- Hook copy-in: `ws.atomic_write(copy, body, Path(root).resolve())`; `copy` is built under the
  same resolved root, so `relative_to` holds and has no `..` (the seat's path is resolved).
- `sync.pull`: `ws.atomic_write(Path(root) / ws.DIR / name, ..., Path(root) / ws.DIR)`.
- `_verdict_problem`: `verdicts` starts as the literal path and is resolved inside the `try`;
  the `except` adds RuntimeError.
- `free(p)`: a nested function; `next(n for held in [<names in p.parent>] for i in range(2, 999)
  if ... not in held)` builds the set once (the outermost iterable is evaluated once), and
  `except (OSError, StopIteration)` returns the refusal text.

## Lines

ws.py +11 (the walk, the import, an explicit default root; fix round 1 turned the two-line
docstring into a def-line comment), hook.py +4 (`free()` with its `try`), sync.py +3 (the pull names
the file it stopped at): runtime 2,993 to 3,011 at the code, 3,044 after merging main 5fe8347. The
item's budget is 10; see the spec's Assumptions.

## Guard testing (AGENTS.md)

- Route corpus `tests/fixtures/routes.json` through the guards and the PreToolUse hook at main and
  at the head with its sha256 (specs/verdict-closed/probe_differential.py), listing moved routes.
- `race_probe.py`: a separate process swaps a parent with renameat2 RENAME_EXCHANGE, 2000
  copy-ins per level, at main and the head, on 3.13 and 3.11.
- `path_probe.py`: a link into the ledger and a loop at every name the copy-in walks or creates
  (`verdicts`, `verdicts/x`, the copy, the temporary name), and one handed-back path per path
  class (`//`, `%xx`, `/./`, `/../`), at main and the head, on 3.13 and 3.11. Fixtures are
  written by code. The working-directory wrappers (`cd`, `env -C`, `sudo -D`) do not apply: no
  command is parsed.

# Implementation Plan: the worktree verdict copy-in refuses a symlink under .wuwei/verdicts

**Branch**: `fix/verdict-symlink` | **Spec**: `specs/verdict-symlink/spec.md`

## Summary

Build the copy path under the resolved root's literal `.wuwei/verdicts`. Refuse it when it or any
folder above it is a link. Then write it with `ws.atomic_write`.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py. Runtime budget 3,000 lines; main is at 2,976, and
this item may add 3.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the hand-back check stays in `_verdict_problem`.
- V. Test first: the new tests run red before the change.
- VI. Budgets: no config key; runtime at 2,979 (+3, the item's budget).

## Design

- `copy` is `Path(root).resolve() / ws.DIR / 'verdicts' / <relative path>`, not the resolved
  `verdicts` folder, so a link at `verdicts/` itself stays visible.
- Refuse when `next((p for p in (copy, *copy.parents) if p.is_symlink()), None)` finds a link, and
  name that component in the refusal. `is_symlink()` reads each
  component with `lstat`, so a link loop counts as a link, and a component that does not exist yet
  is not a link. The root is already resolved, so only links at `.wuwei/` or below can match. A
  first draft compared `copy.parent.resolve()` with `copy.parent`; the loop probe showed that
  Python 3.13 returns a looping path unchanged, so the draft was replaced.
- The refusal is a returned problem string, so `subagent_stop` and the hand-back deny send it to
  the seat as before.
- Replace `mkdir` plus `write_bytes` with `ws.atomic_write(copy, body)`. `atomic_write` writes
  bytes as given and encodes text as UTF-8, as before.
- Gate round 1: `atomic_write` opened its predictable temporary name with `write_bytes`, which
  follows a link. It now runs `temp.unlink(missing_ok=True)` and opens the name with
  `os.open(temp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o666)`, writing through that fd. The
  mode stays what `write_text` gave (0o666 before the umask); `mkstemp` would give 0600.

## Lines

hook.py +1 (two added for the check, one saved by atomic_write), ws.py +2 (the exclusive create):
runtime 2,976 to 2,979.

## Guard testing (AGENTS.md)

- Route corpus `tests/fixtures/routes.json` through the guards at main and at the head, with its
  sha256, listing every route whose verdict or reason moves.
- Probe one input per path class (`//`, `%xx`, `/./`, `/../`) in the named worktree path, and a
  symlink at the target, at each parent level, at `verdicts/` itself, and at a ledger file. Each
  probe checks that the target is unchanged. Fixtures are written by code.

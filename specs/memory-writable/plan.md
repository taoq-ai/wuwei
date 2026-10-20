# Implementation Plan: the transcript guard leaves Claude Code's memory folder writable

**Branch**: `fix/memory-writable` | **Spec**: `specs/memory-writable/spec.md`

## Summary

Give `guards.harness` a `keep` flag. With it, a literal path that resolves (links read) to a file
directly in `<project>/memory` under `ws.PROJECTS` is not a transcript write. The Edit door and
Bash redirect targets pass `keep`; Bash writer words pass it only for writers that cannot make a
link; the working-directory hold never does.

## Technical Context

Python 3.11 stdlib (`os.path.realpath`, `pathlib`, `re`). Tests in tests/test_guards.py and the
route corpus tests/fixtures/routes.json. Runtime budget 3,400 lines; main is at 3,348, #1155 will
add 18, and this item may add 3.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; the transcript door gets a narrower scope.
- V. Test first: the new tests ran red (86 failed) before the change.
- VI. Budgets: no config key; runtime at 3,351 (+3, the item's budget).

## Design

- `harness(path, cap=512, keep=False)`: expand a leading `~`, `$HOME` or `${HOME}` with
  `Path.home()`; with `keep`, the expanded path must fully match `/[\w./@+-]*`, and
  `realpath` of it must have the parent name `memory` and a great-grandparent equal to
  `realpath(ws.PROJECTS)`. The literal check runs first, so `realpath` never sees a NUL or a glob.
- `pre_tool`: the Edit door uses `harness(p, keep=True)`.
- `bash`: redirect targets use `keep=True`; writer words use `keep=program in ('tee', 'sed',
  'truncate', 'rm')`; `held` (session cwd, `-C`, `--chdir`, `-D`) and the `cd`/`pushd` hold stay
  without `keep`.
- `HARNESS`: the refusal adds the memory routes that pass.

## Lines

guards.py +3 (two in `harness`, one in `HARNESS`): runtime 3,348 to 3,351.

## Guard testing (AGENTS.md)

- Route corpus through `guards.bash` at main and at the head, with its sha256, listing every route
  whose verdict moves. Eight rows added for this item.
- The combinatorial probe under real bash: path spellings x targets x writers x positions, plus
  working-directory wrappers (`cd`, `pushd`, `env -C`, `sudo -D`, run through stubs on PATH) x
  folders x writers, with generated, ran and hole counts at main, at the head and at two mutants.
- Path classes `//`, `%xx`, `/./`, `/../` are spellings in the probe and rows in the tests.
- The checks without door words (the INFRA ask rule, the leak check on `curl`) after a memory
  write in the same command.
- Mutants of each new condition, in fresh copies of the tree, both guards.py copies, one at a time.

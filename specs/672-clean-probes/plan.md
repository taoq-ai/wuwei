# Implementation Plan: gate probes leave no files in the builder's worktree

**Branch**: `672-clean-probes` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One gate-only header line in `brief.write`, one status read and one stderr warning in
`dispatch.receive`, one sentence in `charters/_common.md` (regenerated into `agents/`), one
docs row. The status read reuses `brief.status`, the helper the gate brief already uses for
its dirty-tree refusal; the scratch path reuses `workspace.SCRATCH` and the `scratch`
variable #647 put in `brief.write`.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, function, config key, event kind,
state field, guard or adapter operation (`vcs.status` and its git form
`status --porcelain=v1 -z --untracked-files=all` are already allowlisted).

## Constitution Check

- I stdlib: `shlex` (already imported in `brief.py`), `sys` (already imported in
  `dispatch.py`).
- II exits: `receive` keeps 0 clean, 1 refused, 2 could not run. A failed status read raises
  `ValueError` through `brief.read`, which `commands/dispatch.py` already maps to exit 2,
  before the state write, so nothing is recorded.
- III one behaviour one function: the status read is `brief.status`; the brief line lives in
  `brief.write`; the charter rule has one home in `_common.md`.
- IV test first: tasks.md orders each test before its change.
- V simplicity: no enforcement hook, no ignored-file listing, no new adapter form, no copy
  helper; the seat makes its copy with the commands it already has.
- VII security: the warning never blocks; nothing new is written.

## Design

### cli/wuwei/brief.py `write`

Right after the `Scratch:` append (line 426), for gate briefs only (`gate` is set at line
383 and is true for every `sentinel-*` role and a second opinion):

```python
        if gate:  # #672: a gate probe never writes in the builder's worktree
            header.append('Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX='
                          f'{shlex.quote(str(scratch / "pycache"))}; set it on every command that '
                          'runs code, and run every probe, test and mutant in a copy of the worktree '
                          'under your scratch directory, never in the worktree itself')
```

`scratch` is the `<root>/.wuwei/scratch/<item>/<role>` path #647 defined two lines above and
creates before `return relative`; Python creates the `pycache` subdirectory on first write.

### cli/wuwei/dispatch.py `receive`

1. Before `if trees and trees[0] != 'none':` (line 665) set `left = []`.
2. Inside that block, load the VCS once and read the status after the HEAD comparison
   (lines 670-673):

   ```python
        vcs = registry.load('vcs', workspace.load_config(root))
        current_head = brief.read(vcs.head, str(tree), root=root)['sha']
        if ...:  # unchanged HEAD refusal
            raise Refused(...)
        left = [row['path'] for row in brief.status(vcs, str(tree), root)]  # #672
   ```

   `brief.status` validates the rows and raises `ValueError` on a damaged answer, as for the
   gate brief.
3. After `state._write_state(update, ...)` (line 718), before the agent-surface rewrite and
   `return value`:

   ```python
    if left:  # #672: the round left files in the builder's worktree
        # ponytail: git status omits ignored files (a gitignored __pycache__); the brief's
        # Probe env: line prevents those. Add an --ignored status form if seats keep leaving them.
        print(f"warning: {tree} has files the gate round left: {', '.join(left)}; gate seats "
              'probe in a copy under their scratch directory; remove them, or the next gate '
              'brief refuses a dirty tree', file=sys.stderr)
   ```

   The verdict, the returned value, the `gate.received` event and the exit code are as today.
   `dispatch.opinion` returns `receive(...)`, so a second opinion warns the same way.

### charters/_common.md

`version: 1.9.0` becomes `version: 1.10.0`. Write and action boundary, rule 1, append after
"files the out-of-scope bugs it finds (rule 7).":

> It never writes in the builder's worktree, not even a cache file: it runs every probe,
> test and mutant in a copy under its `Scratch:` directory, with the brief's `Probe env:`
> set.

Then run `bin/wuwei agents build` so every `agents/*.md` (all nine include `_common.md`)
carries the sentence; `bin/wuwei agents check` reports no drift.

### docs/site/reference.md

In the "Seat briefs and the build loop" table, after the `Scratch directory` row:

```
| Gate probes | A gate brief adds `Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<scratch>/pycache` and tells the seat to run every probe, test and mutant in a copy under its scratch directory, never in the worktree. `wuwei dispatch receive` still records the verdict, and prints `warning: <worktree> has files the gate round left: <paths>` when the worktree's git status lists any. |
```

## What must not change

- Every existing brief header line and its order; non-gate briefs are byte-identical apart
  from the `Written:` time. `agent_launch` hashes the brief as written, so nothing else moves.
- `receive`'s refusals, their order and messages, the recorded `gate_verdicts` value, the
  `gate.received` event payload, stdout JSON and exit codes on a clean worktree.
- `brief.status`, `vcs.status` and the git adapter allowlist.
- The four `charters/sentinel-*.md` files and every other charter rule (one home per rule).
- No absolute local path in any repository file (tests build paths from `tmp_path`).

## Existing tests that need a fake update

`receive` now calls `vcs.status` whenever the brief names a worktree. Two fakes in
`tests/test_dispatch.py` define only `head`:

- `test_receive_accepts_short_current_worktree_head`: the local `class VCS` gains
  `def status(self, tree, *, root): return Result(0, [])`.
- `agent_gate`: the `SimpleNamespace` vcs gains
  `status=lambda *args, **kwargs: Result(0, [])`.

`test_receive_rechecks_current_worktree_head` refuses on HEAD before the status read and needs
no change. Run the full suite to catch any other fake that reaches `receive` with a worktree.

## Test plan

- `tests/test_brief.py`: for `quality`, `arch`, `security` and `goal` gate briefs (as
  `test_gate_brief_accepts_dispatch_role_names`), the header has exactly one `Probe env:`
  line naming `PYTHONDONTWRITEBYTECODE=1`, the quoted
  `<workspace>/.wuwei/scratch/X/sentinel-<role>/pycache`, and the copy instruction; a
  `builder` brief and a `steward` brief have none. Acceptance smoke: take the two assignments
  from that line (`shlex.split` of the part before the first `; `), run
  `sys.executable -c 'import pkg.mod'` in a `tmp_path` tree holding `pkg/__init__.py` and
  `pkg/mod.py` with that environment, and assert the tree has no `__pycache__`.
- `tests/test_dispatch.py`: a receive whose fake VCS returns `head` `abc1234` and `status`
  `[{'path': 'pkg/__pycache__/mod.cpython-311.pyc', ...}, {'path': 'probe.py', ...}]` through
  `main(['dispatch', 'receive', ...])` exits 0, records the verdict, prints the JSON on stdout
  and one stderr line starting `warning:` naming the worktree and both paths. With `status`
  `[]` stderr is empty. With `status` `Result(2, reason='git status failed')` it exits 2 with
  that reason and `gate_verdicts` stays empty.
- `tests/test_charters.py`: a `RULES` row `("clean probes", "_common.md", "runs every probe,
  test and mutant in a copy under its `Scratch:` directory")` (one home), and a check that each
  `agents/sentinel-*.md` contains that anchor.

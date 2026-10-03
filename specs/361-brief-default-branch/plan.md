# Implementation Plan: item worktrees use their repository's default branch, and plan propose reads the scanner findings list

**Branch**: `361-brief-default-branch` | **Spec**: `specs/361-brief-default-branch/spec.md`

## Summary

Two small fixes, each at the one function every caller routes through.

- F3: `brief.write()` finds the repository of a worktree with the lookup `build next`
  already uses (path equality, else `guards/commit_push.context` by git common directory),
  and a failed merge-base read becomes a coaching reason with the fetch command.
- F2: `discovery.discover()` reads `result.data['findings']` from the audit report, maps
  each finding to a candidate with a stable id, and turns any scanner failure or
  out-of-contract result into an `unmeasured` source line instead of an exception.

No new module, helper, config key, port operation, event, state key or allowlist entry.

## Technical Context

Python 3.11+, stdlib only. External tools stay behind their adapters: git through
`adapters/vcs/git.py`, ZIRAN through `adapters/scanner/ziran.py`; neither adapter changes.
Tests use `tests/fakes/vcs.py` (`Fake`, a recorder), real git in `tmp_path` for the one
worktree regression, and a patched `subprocess.run` answering `ziran --version` and
`ziran audit` with `tests/fixtures/scanner/audit.json` (the pattern of
`tests/test_ziran.py::test_audit_and_gate_fixed_commands`).

## Constitution Check

- I Stdlib only: no new import outside `wuwei`.
- II Three-state exits: a failed merge base stays exit 2 with a reason; a scanner that cannot
  run is `unmeasured`, never counted clean, and `wuwei discover` still exits 2 on it. `plan
  propose` exits 0 because design 5.7 makes an unmeasured source a sweep line, as for the
  tracker.
- III One behaviour, one function: the repository-of-a-worktree lookup stays in
  `commit_push.context`; scanner discovery stays in `discovery.discover()`.
- IV Test first: each behaviour in `tasks.md` is a failing test, then the code.
- V Ponytail: reuse `commit_push.context` instead of a new resolver in `workspace.py`; reuse
  the tracker branch's "unmeasured: reason" pattern; no wrapper types.
- VII Security: no trust decision depends on the new candidates; a scanner failure is never
  read as "no findings".

## Design

### 1. `cli/wuwei/brief.py` `write()`, lines 245-247

Replace the three lines with this shape (the local import follows `commands/build.py:_repo`,
which keeps `brief` free of an import-time dependency on the guards package):

```python
            repo = next((r for r in config['repos'] if (root / r['path']).resolve() == tree), None)
            if repo is None and config['repos']:
                from wuwei.guards.commit_push import context
                repo = context(tree, {}, {}, root, identity=False)[0]
            repo = repo or {}
            remote = config['brief']['remote']
            ref = remote + '/' + repo.get('default_branch', 'main')
            try:
                base = read(vcs.merge_base, tree, ref, root=root)['sha']
            except ValueError as exc:
                raise ValueError(f"no merge base with {ref} in {repo.get('name', tree.name)} ({exc}); "
                                 f'run git -C {tree} fetch {remote}, then write the brief again') from None
```

Notes for the builder:

- Keep the path-equality match first: it avoids two git reads for the configured checkout
  and keeps `test_repo_default_branch` and every fake-vcs brief test unchanged.
- The `config['repos']` guard keeps today's `origin/main` fallback when nothing is
  configured; tests with fake vcs objects that have no `repo_context` rely on it
  (`tests/test_templates_errors.py::test_dirty_gate_brief_names_paths`).
- `context()` raises `ValueError('repository is not configured in this workspace')` for a
  worktree of no configured repository; let it propagate (exit 2 through
  `commands/brief.py:47-49`).
- Catch only around the merge-base read. `Refused` is a `ValueError` subclass but the
  merge-base read never raises it.
- A scratch run of the full suite with exactly this change applied passed (7357 passed; the
  only failures were four tests that clone the repository itself, which the scratch copy
  without `.git` cannot do).

### 2. `cli/wuwei/discovery.py` `discover()`, lines 192-206

Replace the scanner block with this shape (names may differ; behaviour may not):

```python
    if config['repos'] and config['adapters']['scanner'] != 'none':
        scanner = ports.get('scanner') or registry.load('scanner', config)
        found = []
        for repo in config['repos']:
            result = scanner.audit(str((root / repo['path']).resolve()), root=root)
            valid = isinstance(result, registry.Result) and result.exit in (0, 1, 2)
            rows = result.data.get('findings') if (
                valid and result.exit != 2 and isinstance(result.data, dict)) else None
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                reason = (result.reason or 'scanner audit failed') if valid and result.exit == 2 \
                    else 'invalid scanner result'
                found = f'unmeasured: {repo["name"]}: {reason}'
                break
            found += [{'id': f'{repo["name"]}:scanner:{row["rule"]}:{row["file"]}:{row["line"]}',
                       'evidence': f'{row["severity"]} {row["rule"]} {row["file"]}:{row["line"]}: '
                                   f'{row["message"]}'} for row in rows]
        sources['scanner'] = found
```

Notes for the builder:

- The old `sources['scanner'] = 'unmeasured: scanner read failed'` pre-assignment and the
  `complete` flag go away: every path now assigns `sources['scanner']`.
- `dedupe()` already accepts a string as an unmeasured source and adds `source: scanner` to
  each candidate; it does not change.
- Row fields are read with `row[...]`: `ziran._report` already validated them. Do not
  re-validate rows in the core.

### What must not change

- `workspace.py` (the anchor lookup names the workspace only), `guards/commit_push.py`,
  `commands/build.py`, both adapters, `discovery.dedupe()`, `plan.propose()`,
  `commands/plan.py`, `commands/discover.py`.
- The brief header format (`Merge-base: <sha> (<ref>)`), the order of reads and refusals in
  `brief.write()`, and every existing test.
- The rule that `wuwei discover` exits 2 when any source is unmeasured.

## Tests

| Test | File | Covers |
| --- | --- | --- |
| `test_item_worktree_uses_repository_default_branch` | `tests/test_brief.py` | US1 AS1, real git |
| `test_missing_remote_branch_says_fetch` | `tests/test_brief.py` | US1 AS4, fake vcs |
| `test_worktree_of_unconfigured_repository_is_refused` | `tests/test_brief.py` | US1 AS5, fake vcs |
| `test_plan_propose_lists_scanner_findings` | `tests/test_plan.py` | US2 AS1, AS2 |
| `test_plan_propose_with_unrunnable_scanner` | `tests/test_plan.py` | US2 AS3 |
| `test_discover_marks_out_of_contract_scanner_unmeasured` | `tests/test_plan.py` | US2 AS4 |

US1 AS2 and AS3 are covered by `test_repo_default_branch` and the existing no-repository
brief tests. US2 AS5 is unchanged behaviour covered by `tests/test_linear_loop.py`.

## Deferred

- Setup asking before it sets `adapters.scanner = "ziran"`: the setup issue of the sweep.
- Rewording `repository is not configured in this workspace`: the refusal-catalogue issue
  of the sweep.

# Implementation Plan: A workspace is usable right after init

**Branch**: `228-init-integrity` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

`wuwei init` pins the key but never measures, so the PreToolUse gate finds no cached
verdict and refuses every tool with an errno. Init already runs on the host, so it calls
the existing producer, `integrity.check(root)`, as its last step (new workspace and
`--upgrade`) and prints the same line `wuwei integrity check` prints. The two
development-checkout reasons gain the reconfirm instruction at their one source in
`integrity.py`, which reaches init output and the PreToolUse denial through the cached
verdict. `read_tree` in the git adapter reads blobs with one `git cat-file --batch`
instead of one `git show` per file, so measuring a development checkout at init stays
fast (9 s to about 0.2 s on this repository).

## Technical Context

Python 3.11+ stdlib runtime, pytest for tests. Reuse: `integrity.check` (the only verdict
producer), `integrity.cached` (the gate, unchanged), the print line from
`cli/wuwei/commands/integrity.py:15`, `init._register_mcp`, git adapter `_run`,
`_records`, `_tree_path`, `_tree_ref` and `@_operation`. Test helpers in
`tests/test_integrity.py`: `plugin`, `workspace_root`, `core`, the hook payload pattern of
`test_integrity_hook_scope_and_session_exit`; `tests/fakes/replay.install_replay` in
`tests/test_vcs.py`. No new dependency, port operation, config key, state key or event
kind.

## Constitution Check

Stdlib only. Exits stay 0/1/2; init never reports clean when unmeasured (it prints the
unmeasured reason) and the gate still fails closed on a missing, failing or invalid
verdict. The verdict keeps its single producer (`integrity.check`); init calls it, it does
not write the file itself. The only new external command is `git cat-file --batch`,
added to the closed allowlist, with stdin built from already validated ref and paths.
Test first. Passes before and after design.

## Design

### 1. Init measures last (`cli/wuwei/commands/init.py`)

Add one helper next to `_register_mcp` and route both final returns through it:

```python
def _finish(root):
    code = _register_mcp(root)
    from wuwei import integrity
    result = integrity.check(root)
    print(result.reason or 'plugin integrity: clean')
    return code
```

- `run`: `return _register_mcp(destination.parent)` (line 86) becomes
  `return _finish(destination.parent)`.
- `upgrade`: `return CLEAN if args.dry_run else _register_mcp(destination.parent)`
  (line 224) becomes `return CLEAN if args.dry_run else _finish(destination.parent)`.
- Keep `_register_mcp` as is: `tests/test_env_credentials.py` monkeypatches it, and
  `_finish` still goes through it.
- Exit code is the MCP registration result, as today (FR-004). `integrity.check` catches
  `OSError`, `ValueError` and `TypeError` itself and returns exit 2 with a reason, so no new
  exception handling is needed in init.
- Do not touch `integrity.initialize`, the staging and rename, or the upgrade rule that
  security material and pins are not re-created for existing workspaces.

### 2. Reconfirm instruction at the source (`cli/wuwei/integrity.py`)

- Line 81, `measure`: `'development checkout requires host reconfirmation'` becomes
  `'development checkout requires host reconfirmation; run wuwei integrity reconfirm on the host'`.
- Line 160, `check`: `'page: plugin integrity: dirty development checkout; restore a clean commit'`
  becomes
  `'page: plugin integrity: dirty development checkout; restore a clean commit and run wuwei integrity reconfirm on the host'`
  (the wording `cached` already uses at line 189).

`cached` returns the recorded reason for a non-zero verdict, so the PreToolUse denial after
init carries this line. Nothing else in `integrity.py` changes.

### 3. One git process for tree blobs (`adapters/vcs/git.py`)

- `_run(repo, *args, settings=None, env=None, missing=False, local=False, input=None)`:
  pass `input=input` to `subprocess.run`.
- Allowlist: add `case ('cat-file', '--batch'): allowed = True`.
- `read_tree` (lines 586-592): keep the argument checks and the `ls-tree` call; validate
  every listed name with `_tree_path` before reading; return `{}` when there are none;
  otherwise send `''.join(f'{ref}:{name}\n' for name in names).encode()` to
  `cat-file --batch`, re-encode the output with `'utf-8', 'surrogateescape'` (lossless,
  `_run` decoded it that way) and parse, for each name in order, the header
  `<oid> <type> <size>\n`, `size` bytes of content, and one `\n`. A header that is not
  three fields (`<ref>:<name> missing`) or a type other than `blob` raises `ValueError`,
  which `@_operation` turns into exit 2. Decode content with `'utf-8', 'surrogateescape'`,
  as before.
- Names cannot contain a newline: `_tree_path` rejects control characters, so the
  line-based batch input is unambiguous.
- The port signature and return value are unchanged, so `cli/wuwei/closing.py`,
  `cli/wuwei/integrity.py` and `tests/fakes/vcs.py` need no change.

### 4. Docs

- `docs/integrity.md`, the paragraph starting "`wuwei init` copies the plugin public
  key": add that init and `init --upgrade` end by measuring the plugin and caching the
  verdict, printing `plugin integrity: clean` or the finding, so the first tool call is
  gated on a real measurement; a development checkout prints the reconfirm line.
- `README.md` "Quick start" and `docs/site/index.md` install step: drop the separate
  `../wuwei-plugin/bin/wuwei integrity check` line; say init prints
  `plugin integrity: clean` for an intact signed release. Keep every phrase
  `tests/test_docs.py` requires.

## What must not change

- `integrity.cached`, the PreToolUse and SessionStart guards, `measure` beyond the one
  string, `reconfirm`, `initialize`, `workspace_check`.
- Guard scope: outside a workspace the gate returns 0.
- No guard refuses less; #165 pinning and confirmation rules; the verdict's producer.
- `init --upgrade --dry-run` writes nothing and measures nothing.
- Init's exit codes for every existing path.

## Test notes for the builder

- The builder's worktree is dirty while building, so `integrity.check` on this repository
  takes the fast "dirty development checkout" path. CI and main are clean and take the
  `read_tree` path. Check the speed-up directly, independent of tree state:
  `python -P -c "import sys,time; sys.path[:0]=['cli','.']; from adapters.vcs import git; t=time.time(); r=git.read_tree('.', 'HEAD', ['.']); print(r.exit, len(r.data), round(time.time()-t,2))"`
  from the repository root (expect exit 0, several hundred files, well under 1 s).
- `test_init_pins_key_and_initializes_workspace_vcs` fakes the VCS port with only
  `workspace_init`; once init calls `integrity.check` on the real repository, `_checkout`
  needs `head`. Stub `integrity.check` in that test (T004).
- `integrity.check` catches `OSError`, `ValueError` and `TypeError` only. Any other test
  that replaces `registry.load` with a VCS fake missing `head` or `status` and then runs
  init would raise `AttributeError`; stub `integrity.check` in such a test rather than
  widening the catch. A workspace without `pinned.pub` (for example the upgrade fixtures
  in `tests/test_workspace.py` and `tests/test_env_credentials.py`) gets an unmeasured
  verdict and init prints that line; exit codes do not change.

## Build notes

- The `('show', object_name)` allowlist case in the git adapter had one caller,
  `read_tree`; with `cat-file --batch` it became dead, so it was removed to keep the
  allowlist closed.
- Init now prints the verdict after the status-line snippet, so two tests in
  `tests/test_signal_status.py` that read the snippet as the last stdout line read it as
  the second line instead. No document promises the snippet is last.
- Measured `read_tree` on this repository after the change: 771 files in 0.27 s.

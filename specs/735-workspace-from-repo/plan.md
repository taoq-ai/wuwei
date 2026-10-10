# Implementation Plan: owner commands work from any configured repository

**Branch**: `735-workspace-from-repo` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Two small changes at shared spots. (1) The lookup: `workspace.find_workspace` falls back to a
per-user index `~/.config/wuwei/workspaces.json` after its parent walk, and
`workspace.index(root, config)` writes that index from the two places that settle a
workspace's repositories, `config.offer` and `init --upgrade`. Every command and `scope` (the
guards) inherit it with no change of their own. (2) The printed form: `workspace.owner_cli(root)`
builds `bin/wuwei --workspace <quoted root>` once, and the `decide` and `drafts approve/drop`
texts the owner copies use it. The `--workspace` flag itself already exists (#354) and is not
touched.

## Technical Context

Python 3.11+, stdlib only (`json`, `shlex`, `pathlib`); pytest for tests. No adapter, no
subprocess, no new port. Tests isolate `HOME` per test (`tests/conftest.py`
`isolated_mcp_home`), so `Path.home()` is a tmp folder and the index never touches the
developer's home. `workspace.py` is on the hook path (#346, #516): `json` and `shlex` are
imported inside the new functions, and the index is read only after the parent walk fails.

## Constitution Check

- I (stdlib): `json`, `shlex`, `pathlib` only.
- II (exits, fail closed): an ambiguous checkout is exit 2 with a reason naming both roots
  (the existing `FileNotFoundError` path through `__main__._call`). A damaged index reads as
  empty on purpose: it is a per-user lookup aid, and raising there would fail every hook on
  the machine (spec Edge Cases). The command still exits 2 with today's "No .wuwei/ found"
  reason, so nothing reports clean when unmeasured.
- III (one behaviour, one function): lookup in `find_workspace`, index writes in
  `workspace.index`, the printed prefix in `workspace.owner_cli`.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new flag, no config key, no lock (`ponytail:` comment), no per-command
  path logic; `scope` gets the sibling checkout for free.
- VII (security): the index is not a trust anchor. It can only resolve to a root holding a
  real `.wuwei/` (the same check the env override makes), `scope` re-checks the live `repos`
  table before a guard acts, and no guard or decision rule changes (no 9.2 row).
- Design spec conflict: none. 9.1 already puts configured repos in guard scope; this makes
  `scope` reach a sibling checkout as 9.1 says. The issue's `~/.wuwei/` location is replaced
  (spec Clarifications), which the issue, not the design spec, named.

## Design

### 1. `cli/wuwei/workspace.py`: the index, its lookup and the printed prefix

Next to `find_workspace` (line 311):

```python
INDEX = '.config/wuwei/workspaces.json'  # #735: under the home folder; never a .wuwei/ there


def _indexed():
    """#735: the per-user index {root: [checkout]}, absolute strings; missing or damaged is empty."""
    import json
    try:
        data = json.loads((Path.home() / INDEX).read_text(encoding='utf-8'))
        return {root: list(checkouts) for root, checkouts in data.items()
                if Path(root).is_absolute() and isinstance(checkouts, list)
                and all(isinstance(path, str) and Path(path).is_absolute() for path in checkouts)}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}
```

`find_workspace`: replace the final `raise` (line 329) with the index lookup, then the same
raise:

```python
    roots = sorted(root for root, checkouts in _indexed().items()
                   if any(start.is_relative_to(path) for path in checkouts)
                   and (Path(root) / '.wuwei').is_dir() and not (Path(root) / '.wuwei').is_symlink())
    if len(roots) == 1:
        return Path(roots[0])
    if roots:
        raise FileNotFoundError(f'{start} is a configured repository of {len(roots)} workspaces: '
                                f'{", ".join(roots)}; pass --workspace <path> (or set '
                                'WUWEI_WORKSPACE=<path>) to pick one')
    raise FileNotFoundError(...)  # today's text, unchanged
```

The writer:

```python
def index(root, config):
    """#735: record root's configured checkouts in the per-user index find_workspace reads;
    the root itself and the home folder or its parents are never indexed."""
    import json
    root, home = Path(root).resolve(), Path.home().resolve()
    checkouts = sorted({str(path) for repo in config['repos']
                        if (path := (root / Path(repo['path']).expanduser()).resolve()) != root
                        and not home.is_relative_to(path)})
    data = _indexed()
    data.pop(str(root), None)
    if checkouts:
        data[str(root)] = checkouts
    path = Path.home() / INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    # ponytail: no lock; two writers at once can drop one root's entry until its next config
    # write or init --upgrade. Lock the file if several workspaces are set up concurrently.
    atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + '\n')
```

The repository path expression is the one `scope` uses (line 370); reuse it as written, no new
helper.

The printed prefix:

```python
def owner_cli(root):
    """#735: the owner command prefix that works from any folder (the leading flag, #354)."""
    import shlex
    return f'bin/wuwei --workspace {shlex.quote(str(root))}'
```

### 2. Index writers

- `cli/wuwei/commands/config.py` `offer` (line 275): inside `if text != raw:`, after
  `workspace.atomic_write(path, text)` (line 296), call
  `workspace.index(root, workspace.load_config(root, raw=text))`; on `OSError` print
  `wuwei {label}: warning: workspace index not written: {exc}` to stderr and continue. The
  config just loaded for `graph.sync` (line 293) may be hoisted into one variable and reused.
  Every owner config write (`config set`, `config add-repo`, `config promote`, `setup`,
  `outbound learn`, `grants revoke`, draft tier rows) goes through `offer`.
- `cli/wuwei/commands/init.py` `upgrade` (line 346): inside `if not args.dry_run:` (line 398),
  call `workspace.index(destination.parent, workspace.load_config(destination.parent,
  raw=migrated))`; on `OSError` print `wuwei init: warning: workspace index not written:
  {exc}` to stderr. It prints nothing on success and is not counted as a workspace change
  (the "No workspace changes needed" line is unchanged). Fresh `init` is not changed.

### 3. Printed owner commands (FR-007)

Each site builds the prefix with `workspace.owner_cli(root)`; `root` is already in scope at
every site below except `drafts.widget`, which gains it.

- `cli/wuwei/decision.py:214`: `RECORD = '{cli} decide {id} "<label>"'`.
  `record_widget(identifier, fields, record=RECORD, level='brief', hidden=False, *, root)`
  (line 246) formats `record.format(id=identifier, cli=workspace.owner_cli(root))` (line 259).
  Other record templates (`CONFIG_RECORD`, `mcp.RECORD`) have no `{cli}` and are unchanged;
  `str.format` ignores the extra keyword. Callers pass `root=root`:
  `commands/decision.py:164`, `grants.py:315`, `cruise.py:313`, `commands/outbound.py:370`,
  `mcp.py:408`, `calibrate.py:788`. `root` is keyword-only and required, so a missed caller
  fails loudly instead of printing a command without the flag.
- `cli/wuwei/drafts.py:174` `widget(row, config)` becomes `widget(row, config, root)`; its
  one caller `commands/drafts.py:35` passes `root`. Use the prefix in the four id-bearing
  owner commands: `drafts approve {draft_id} --file <file>` (line 194), `drafts drop
  {draft_id}` (lines 197 and 202-203), `drafts approve {draft_id} --always` (line 205) and
  the record `drafts approve {draft_id}` (line 215). `bin/wuwei drafts` (the list) and
  `bin/wuwei outbound learn` texts stay.
- `cli/wuwei/commands/decision.py`: lines 203 and 206 (`run`/`rerun ... decide ... in a host
  terminal`) and lines 274 and 277 (`reverse it with wuwei decide {id} <option>`), each as
  `f'{workspace.owner_cli(root)} decide ...'`.
- `cli/wuwei/commands/status.py:220`: `confirm with {workspace.owner_cli(directory.parents[2])}
  decide {identifier} {option}` (the root the file already derives as
  `directory.parents[2]`, line 179).
- `cli/wuwei/commands/dashboard.py:106`: `approve_command` is
  `f"{workspace.owner_cli(root)} drafts approve {row['id']}"` (`root` from line 32).

## What must not change

- `__main__.py`: the leading `--workspace` parsing (lines 8-9, 52-54) and the `_FAST`
  detection; no new flag position.
- `find_workspace` precedence: `WUWEI_WORKSPACE` first, then the parent walk, then the index;
  its existing error texts; the `.wuwei` symlink refusals.
- `workspace.scope`, `worktree_workspace`, `guard_scope`: no code change (FR-008 comes from
  the lookup). `protect_state._workspace` and its `.wuwei` prefilter stay as they are.
- `init.status_line` / `_status_command`: the `statusLine` command stays
  `<executable> status --line`.
- The guards' parsing of `--workspace` (`protect_state._positional`, `commands.read_only`).
- Texts outside FR-007 (spec Assumptions): the report's reverse line, `docs.findings`,
  `protect_state._OWNER_ACTIONS` and its host-terminal echo, `tracker` strict texts, the
  `mcp decide` family.
- Fresh `init` output and behaviour.

## Tests that will need updating

Exact-string assertions on the FR-007 texts change to the `--workspace` form (the builder
updates them in the task that changes the text): `tests/test_decision.py:741, 1236`,
`tests/test_outbound_learn.py:170`, `tests/test_card_confirms.py:358`,
`tests/test_cruise.py:343, 346`, `tests/test_remote.py:1018`,
`tests/test_signal_status.py:525, 549, 809`, `tests/test_drafts.py:388, 675, 682, 868`, and
every `record_widget(...)` call in tests (7) gains `root=`.

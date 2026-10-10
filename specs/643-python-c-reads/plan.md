# Implementation Plan: a read-only python -c on state.json is a read

**Branch**: `643-python-c-reads` | **Date**: 2026-10-10 | **Spec**: `specs/643-python-c-reads/spec.md`

## Summary

Teach the one shared read predicate, `shell.reads`, the `python -c` read form through one new
helper, `shell.snippet_write(argv)`, that returns the first write-like token of the snippet
(`''` when it only reads, `None` when argv is not `python [-flags] -c <code>`). The state
guard's interpreter refusal then passes a read snippet for free (it already asks
`reads`), and names the token when it refuses. No other caller changes.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only (`re`, already imported in `shell.py`)
**Testing**: pytest, in process; the hook through `wuwei.commands.hook.run` as the existing
`_hook` helper and the invariants `Rules.hook` do
**Constraints**: hook path latency: no new import; the pattern is a plain string compiled on
first use through `re`'s cache, as `protect_state._STATE_MENTION` is, so a Bash call that
never reaches it pays nothing

## Constitution Check

- I Stdlib only: yes, one `re` pattern.
- II Exits: a refused snippet stays exit 2 under the records floor; nothing new can raise.
- III One behaviour, one function: the token scan lives only in `shell.snippet_write`;
  `reads` and `check_bash` call it.
- IV Test first: tasks order each test before its code.
- V Ponytail: no parser (`ast`), no config, no new module. The token scan carries a
  `ponytail:` comment naming its ceiling.
- VII Security: the records floor keeps every write form it refuses today; the only new pass
  is a snippet with no write-like token, and the CLI import is a token so `_owner_action`
  never treats an in-process owner action as a read.
- Workflow: invariant I36 added to design spec 9.2 and `tests/test_invariants.py`.

## Design

### `cli/wuwei/shell.py`

1. Next to `_INTERPRETER` / `_SNIPPET` (line 559), add one pattern string (used with
   `re.search(_SNIPPET_WRITES, code)`):

   ```python
   # #643: what makes a python -c snippet more than a read; the leftmost match is named.
   # ponytail: a token scan, not a parser; a mode or name built at run time (concatenation,
   # chr, sys.argv, environ, stdin) is not seen, the 4.5 residual is_opaque already carries.
   # Parse with ast if a false read ever shows up.
   _SNIPPET_WRITES = (
       r"""(['"])[rbt]*[wax+][rbtwax+]*\1"""  # an open mode that writes: 'w', "a+", 'rb+'
       r'|\w*(?:write|remove|rename|replace|unlink|rmdir|mkdir|makedirs|touch|truncate|chmod|chown'
       r'|symlink|hardlink|inplace)\w*|os\.(?:link|open|fork)'
       r'|shutil|subprocess|system|popen|spawn|exec|eval|getattr|__import__|importlib|runpy|ctypes'
       r'|sqlite3|shelve|dbm'
       r'|(?<![\w/-])(?<![^\w.]\.)wuwei(?![\w/-])')  # the CLI imported; not .wuwei/ or cli/wuwei/
   ```

   Changed in implementation: `makedirs` (not matched by `mkdir`), `inplace` (fileinput),
   `ctypes`, and `sqlite3`, `shelve`, `dbm` (they create files) are tokens too. The `wuwei`
   lookbehind now excludes only a path dot (`'.wuwei'`, `/.wuwei`), so `import cli.wuwei.commands`
   is a token; the first draft let it through as a read.

   Checked against the spec's cases before writing this plan: the acceptance read, a `'rb'`
   read, `read_text()` and a `cli/wuwei/` path give no match; `'w'`, `"a+"`, `'r+'`,
   `write_text`, `replace`, `shutil`, `subprocess`, `system` and `wuwei` (import forms) match.

2. One function, placed before `reads`:

   ```python
   def snippet_write(argv):
       """#643: the first write-like token of python [-flags] -c <code>; '' when the code only
       reads; None for any other form (attached -c<code>, -i, -W, -X, -m, a script, stdin)."""
   ```

   Walk `argv[1:]`: each word must fullmatch `-[BEIOPSdqsu]+` until one fullmatches
   `-[BEIOPSdqsu]*c`; the next word is the code (missing: `None`). Any other word first:
   `None`. Program name check: `re.fullmatch(r'(?:python|pypy)[\d.]*', PurePosixPath(argv[0]).name)`
   (the same test `reads` uses at line 889). Return `match[0] if match else ''`.
   Words after the code are `sys.argv` data and are not scanned.

3. `reads` (line 876): fold the python branch into one:

   ```python
   if re.fullmatch(r'(?:python|pypy)[\d.]*', name):
       if args[:2] == ['-m', 'json.tool']:
           return len(args) < 4  # unchanged
       return snippet_write(argv) == ''  # #643
   ```

   Update the docstring to name the `python -c` read form. A python argv never reached the
   `known_cli` fallback as true, so returning here changes nothing else.

### `cli/wuwei/guards/protect_state.py`

`check_bash`, lines 616-622: keep the condition; build the reason from the token.

```python
token = snippet_write(command.argv)
return 2, (f'Opaque interpreter: {token} in the snippet is not a read; use the wuwei CLI '
           'for state changes.' if token else 'Opaque interpreter; use the wuwei CLI for state changes.')
```

Import `snippet_write` in the existing local `from wuwei.shell import ...` line of
`check_bash` (line 559). Update the comment at line 617 to name the read snippet.

### What does not change

- `shell.classify`, `inline_code`, `is_opaque`, `unread`, `unreadable`: a `-c` call stays
  inline code for the #347 and #530 paths.
- `_wuwei_action`, `_owner_action`, `_write_targets`: they already ask `reads`; a snippet that
  imports the CLI is not a read, so the `Opaque owner action` refusal stands.
- The redirect check (`command.writes` against `_protected`), the records floor and every
  posture line in `hook.py`.
- The `python -m json.tool` rule and the `test_issue_349_interpreter_operands_stay_refused`
  cases (`python3 w.py`, `node w.js`, `python3 read_reports.py`, `-m zipfile`, `-m tarfile`).

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 9.2: row I36 after I35:
  `| I36 | A python -c snippet with no write-like token passes the records guard in every
  posture; one with a write-like token is refused in every posture, naming the token | per
  posture, through the hook, a snippet printing a key of the day's state.json; check_bash on
  open(..., 'w') and Path(...).write_text snippets naming it | #643; one token scan in
  shell.snippet_write, shared through shell.reads; a name built at run time is the 4.5
  residual |`
- `docs/site/security.md` line 66: after the read-only words list, one sentence: a
  `python -c` snippet with no write-like token (no writing open mode, no `write_text`, `os.replace`,
  `shutil`, `subprocess`, `os.system` or the like, no CLI import) is a read too; a records
  refusal of any other snippet names the first such token.

## Tests

- `tests/test_shell.py`: one table test `test_issue_643_snippet_write` over argv, expected
  token: the acceptance read (`''`), a `'rb'` read (`''`), `Path(...).read_text()` (`''`),
  `-I -c` and `-Bc` reads (`''`); `open(p, 'w')` (`"'w'"`), `mode="a+"` (`'"a+"'`), `'r+'`,
  `Path(p).write_text(x)` (`'write_text'`), `os.replace` (`'replace'`), `shutil.copy`,
  `subprocess.run`, `os.system`, `from wuwei.commands import main` (`'wuwei'`),
  `import json, wuwei` (`'wuwei'`); `None` for `python3 x.py`, `python3 -m json.tool f`,
  `python3 -i -c x`, `python3 -cprint(1)`, `python3 -c` with no code, `node -e x`, `cat -c x`.
  Plus `shell.reads` true for the acceptance read and false for the `'w'` snippet.
- `tests/test_protect_state.py`:
  - extend `test_issue_349_shared_read_predicate` with a read and a write `-c` argv;
  - new `test_issue_643_python_c_read_passes` (parametrized observe, guarded, strict, on the
    `records` fixture): the acceptance command through `_hook` exits 0 and `_events` adds
    nothing; same for a read of `_STATE` (`DAY_349` state.json);
  - new `test_issue_643_write_snippet_names_token` (same postures): `check_bash` on
    `open("{_STATE}", "w")` and `Path("{_STATE}").write_text("x")` returns exit 2 with `'w'`
    and `write_text` in the reason; `_hook` exits 2;
  - one owner-action guard case: `python3 -c "from wuwei.commands import main; main(['decide','D-1','once'])"`
    still exits 2 through `check_bash` (Opaque owner action), and a read snippet redirected
    into `_STATE` exits 1;
  - update the exact reason in `test_issue_349_writes_refused_in_every_posture` (line 928)
    to the new token reason for `open("{_STATE}", "w")`.
- `tests/test_invariants.py`: `i36` reading posture `(0,)`: through `rules.hook(posture,
  rules.bash(cmd))` the read of the day `state.json` (path from `workspace.day_dir(rules.root)`
  relative to the root) exits 0; `check_bash(rules.bash(write))` for the `'w'` and `write_text`
  snippets returns 2 with the token in the reason. Memoize per posture like `opaque`. Add to
  `INVARIANTS` and `READS`.

## Project Structure

Files changed: `cli/wuwei/shell.py`, `cli/wuwei/guards/protect_state.py`,
`tests/test_shell.py`, `tests/test_protect_state.py`, `tests/test_invariants.py`,
`docs/specs/2026-09-24-wuwei-design.md`, `docs/site/security.md`. No new files outside this
feature directory.

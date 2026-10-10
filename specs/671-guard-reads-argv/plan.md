# Implementation Plan: the git and gh guard reads the executed command, not prose

**Branch**: `671-guard-reads-argv` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Every git and gh guard (`commit_push`, `pr`, `deploy`, and `protect_state`, `outward`,
`decision` through the same parser) reads a Bash call through `shell.normalize` and decides
relevance with `shell.mentions`. The fix goes there, once, and every guard inherits it:

1. `mentions` joins line continuations before matching (one regex).
2. `normalize` defers the mention check on a reader's text (its arguments and the here-doc
   body it reads) and runs it at the end only when the call also runs something that is not
   a reader or a guarded program.
3. `normalize` stops refusing a quote-split name before it parses an `eval` string or a
   `sh -c` script; the recursive parse already returns the resolved argv.
4. A new `shell.constructed(command)` names the git or gh command a call builds without
   spelling it. `shell.unreadable` returns `''` for such a call, so the hook keeps the
   refusal at its level instead of the opaque warning, and the hook adds `resolved: <cmd>`
   to a Bash refusal.

No guard module changes. The guards' own rules, the classifier (`classify`, `unread`) and
the hook's posture logic stay as they are.

A scratch copy of this design (never the repository) passed every test in
`tests/test_commit_push.py`, `test_pr_guards.py`, `test_deploy.py`, `test_parser_warns.py`,
`test_seat_command_forms.py`, `test_protect_state.py` and `test_scope_first.py` unchanged;
the only failures were 14 `tests/test_shell.py` cases, each one this issue flips on purpose
(tasks T005 and T008 move them).

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. No new module, port, event kind, state key or
config key. Touched: `cli/wuwei/shell.py`, `cli/wuwei/commands/hook.py`,
`docs/specs/2026-09-24-wuwei-design.md` (9.2 row), `docs/site/security.md` (one sentence),
tests.

## Constitution Check

- I stdlib: `itertools.product` only.
- II exits: nothing that refused before passes, except a reader's text in an all-reader
  call (the false refusal) and a resolved command its plain form allows; parse failures
  still raise `ParseError` and the guards still turn it into exit 2.
- III one behaviour, one function: relevance stays in `mentions`, argv in `normalize`,
  naming in `constructed`; no guard re-parses.
- IV test first: tasks.md orders each test before its code.
- V ponytail: reuse `shell.reads` (the #349/#471 reader rule), `_word`, the recursive
  `_parse`, `_cut`/`_simple`/`_strip`; no variable evaluator.
- VII security: the reader exemption is per call (any non-reader voids it), so a pipe into
  `sh`, `xargs ... sh -c @` or an interpreter is refused as today; variables are never
  resolved to a value, only named for a refusal.
- Workflow: the changed guard rule adds 9.2 row I41 and its `tests/test_invariants.py`
  check.

## Design

### cli/wuwei/shell.py

**`mentions`, line 99**: join continuations, as the shell does.

```python
unquoted = re.sub(r'''\\\n|['"\\]''', '', raw)
```

**Reader text is deferred** (a new keyword-only list `texts`, threaded exactly like
`words`):

- `normalize` (line 223): build `texts = []` and `protected = ('git', 'gh', *protected)`,
  call `_parse(..., texts=texts)`, then before returning:

  ```python
  # #671: a reader's text is data only when no command of the call can run it.
  if texts and any(item.argv and PurePosixPath(item.argv[0]).name not in protected
                   and not reads(item.argv) for item in found):
      for text in texts:
          _reject_mentions(text)
  ```

  `reads` is the existing `shell.reads(argv, cwd=None)`; it is defined later in the module
  and resolves at call time.
- `_parse` signature (line 283) gains `texts`; lines 323-324 append the body instead of
  rejecting it: `texts.append(body)` (same owner condition: a `git` or `gh` owner keeps its
  body exempt as today).
- `_unwrap` signature (line 423) gains `texts`; lines 494-495 become:

  ```python
  if reads(argv):
      texts += (' '.join(raw_argv), ' '.join(argv))
  else:
      _reject_mentions(' '.join(raw_argv))
      _reject_mentions(' '.join(argv))
  ```

- Pass `texts=texts` at every internal call: `group`'s `_unwrap` (line 384), `eval`'s
  `_parse` (line 455), `sh -c`'s `_parse` (line 486), `xargs`'s `_unwrap` (line 546).

**`eval` and `sh -c` resolve**: delete lines 452-454 (the `eval` split-quote loop) and
lines 482-485 (the `sh -c` split-quote check and the "obfuscated git/gh mention in shell
script" raise). Keep line 481 (mentions in the shell's other arguments), 477 (expanding
script) and 479 (positional expansion). The recursive `_parse` resolves the name through
`_word`, and the outer source/decoded check at line 337 still runs on the outer word.

**`constructed(command)`**, new, just above `unreadable`:

```python
def constructed(command):
    """#671: the git and gh commands this call runs under a name its text does not spell
    plainly ('git push; gh pr merge'), else ''. When the call does not parse, a program
    word built from variables counts if assignments in the call give it a git or gh value;
    it is named for the refusal, never resolved to one value."""
    try:
        runs = [item.argv for item in normalize(command)]
    except ParseError:
        runs = []
        try:
            stages = [_strip(argv) for argv, _, _ in _simple(_cut(command, []))]
        except ValueError:
            stages = []
        values = {}
        for found, _, _ in stages:
            for key, value in found:
                values.setdefault(key, set()).add(value)
        for _, argv, _ in stages:
            names = re.findall(r'\$\{?([A-Za-z_]\w*)\}?', argv[0]) if argv else []
            if names and all(name in values for name in names):
                for chosen in product(*(sorted(values[name]) for name in names)):
                    pick = iter(chosen)
                    runs.append([re.sub(r'\$\{?[A-Za-z_]\w*\}?', lambda _: next(pick), argv[0]),
                                 *argv[1:]])
    found = [' '.join([PurePosixPath(argv[0]).name,
                       *argv[1:3 if PurePosixPath(argv[0]).name == 'gh' else 2]])
             for argv in runs if argv and PurePosixPath(argv[0]).name in ('git', 'gh')]
    return '; '.join(dict.fromkeys(text for text in found if text not in command))
```

`from itertools import count, product` at the top. The plain-spelling test is a substring
check of `<program> <verb>` against the raw text, so `git push` and `/usr/bin/git push` name
nothing and `g""it push` names `git push`.

**`unreadable`, line 1005**: first line `if constructed(command): return ''` with the
comment `# #671: it names the command it runs`. Its only caller is `hook.posture`'s
`opaque_reason`; returning `''` keeps the refusal at its area level.

### cli/wuwei/commands/hook.py

Before `if reasons:` at line 132 (the PreToolUse return):

```python
if reasons and args.event == 'PreToolUse' and payload.get('tool_name') == 'Bash':
    from wuwei.shell import constructed  # #671: only once a Bash call is refused
    if (runs := constructed(payload['tool_input'].get('command', ''))):
        reasons[0] += f'\nresolved: {runs}'
```

`payload['tool_input']` is a dict for every validated Bash PreToolUse payload; guard it the
way `target` does if the builder finds a path where it is not.

### What must not change

- `shell.classify`, `shell.unread`, `shell.is_opaque`, `shell.reads`, `READ_ONLY`.
- `_reject_mentions` itself, and its calls on comments (296), redirect targets (317),
  continuation parts (332-334), assignments (427), program names (442), `xargs` (498),
  `command -v` (500), wrapper options (539), the shell's other arguments (481).
- The hidden-mention check at line 337 and every `ParseError` message.
- Every guard module and `hook.posture`.

## Test plan

- `tests/test_shell.py`: reader data and its fail-closed counterpart; resolved names;
  `mentions` with continuations; `constructed` and `unreadable`; the 14 flipped cases
  updated (T002).
- `tests/test_commit_push.py` and `tests/test_pr_guards.py`: resolved forms return what the
  plain forms return.
- `tests/test_parser_warns.py` (the in-process hook helper): the brief heredoc under each
  posture, and the `resolved:` line and level for constructed forms.
- `tests/test_hooks.py::test_unaccounted_shell_mention_blocks_hook`: its `echo "git push"`
  is now data; use a non-reader such as `awk 'BEGIN {system("git push")}'`.
- `tests/test_invariants.py`: `i41`.

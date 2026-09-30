# Implementation Plan: Ordinary seat command forms pass the commit, deploy and PR guards

**Branch**: `226-seat-command-forms` | **Date**: 2026-09-30 | **Spec**: `specs/226-seat-command-forms/spec.md`

## Summary

Four small fixes, each at the spot every caller already routes through:

1. `shell.mentions`: a leading `NAME=value` assignment word is not a command name.
   Fixes `x=$(pwd); echo $x` for commit/push, deploy and PR at once.
2. `shell.is_opaque(argv, stdin=True)`: an interpreter without a snippet or path is opaque
   only when its standard input is fed by the list. The deploy and PR guards pass that per
   command and name the command they refuse. Fixes `python3 -m pytest -q && git status`.
3. `commit_push.commit_options`: split any short bundle that starts with a no-value flag,
   not only `-a`. Fixes `git commit -qm`, `-sm`, `-vm`.
4. `adapters/vcs/git.py::_run`: say "not a git repository" when git says so.

Plus two message-only changes so every refusal names the guard and the command:
commit/push's non-git-command-in-list refusal, and protect_state's cd containment refusal
for a statically unresolvable `cd` (see the correction in the spec: that refusal stays).

The shell normaliser grammar does not change. Substitutions still raise `ParseError`; the
fix is that irrelevant text never reaches the normaliser.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only
**Testing**: pytest; in-process guard tables with the fakes in `tests/fakes/`, in-process
`wuwei.commands.hook.run` for acceptance, `fakes.replay.install_replay` for git
**Constraints**: three-state exits, fail closed, no subprocess in the core, no new config keys

## Constitution Check

- Reuse: relevance stays in `shell.mentions` (reusing `_ASSIGNMENT`), opacity stays in
  `shell.is_opaque`, standard-input facts come from the existing `Command.separator` and
  `Command.reads`. No guard re-parses shell text.
- Test first: every change below has a failing test task ordered before it.
- Fail closed: nothing that is relevant and unparseable starts passing; fed interpreters,
  snippets naming git or gh, and substitutions around guarded commands stay refused.
- Ponytail: no new module, no new helper, no config. One keyword argument, one regex
  change, one condition per guard, one string match in the adapter.

## Changes

### `cli/wuwei/shell.py`

- `mentions` (lines 113 to 114), command-text path only. The final scan becomes: at each
  command position, skip leading assignment words and check the first word after them.
  Prototyped and validated against the full suite:

  ```python
  # An assignment prefix is not a command name; the word after it is.
  return any(not _literal(word) for word in re.findall(
      r'(?:^|[;&|(\n])\s*(?:[A-Za-z_]\w*=[^\s;&|()]*\s+)*([^\s;&|()]+)', unquoted)
      if not _ASSIGNMENT.match(word))
  ```

  An assignment-only segment (`x=$substitution` before `;` or at the end) yields its own
  word, which the `_ASSIGNMENT` filter drops. Nothing else in `mentions` changes: the
  substitution bodies are still checked recursively (lines 103 to 105), nested
  substitutions still answer True (line 107), and a git or gh mention with any expansion
  still answers True (line 111). `script=True` is untouched.
- `is_opaque(argv, stdin=True)` (line 536): docstring gains one sentence ("stdin=False: the
  list does not feed this command's standard input, so an interpreter without a snippet
  cannot read guarded text from it"). The last line becomes
  `return stdin and not has_snippet and (len(argv) == 1 or argv[1].startswith('-'))`.
  The git/gh-in-argv branch and the snippet branch ignore `stdin`. Every existing caller
  keeps the default.

### `cli/wuwei/guards/deploy.py` `check` (lines 273 to 278)

```python
for index, command in enumerate(commands):
    argv, env = command.argv, command.env
    if not argv:
        continue
    fed = bool(command.reads) or index > 0 and commands[index - 1].separator == '|'
    if is_opaque(argv, fed) and mentions(raw, ('git', 'gh')):
        unknown(f'opaque deployment command: {" ".join(argv)}; use a plain command')
```

The `mentions(raw, ('git', 'gh'))` conjunct stays, so nothing becomes stricter
(`kubectl get pods | python3` still passes as today).

### `cli/wuwei/guards/pr.py` `check` (lines 372 to 377)

Same shape: `enumerate(commands)`, the same `fed` expression, `shell.is_opaque(command.argv, fed)`,
message `f'opaque command: {" ".join(command.argv)}; run gh as a plain command'`.

### `cli/wuwei/guards/commit_push.py`

- `commit_options` (lines 205 to 207): replace the `-a` special case with

  ```python
  if len(arg) > 2 and arg[0] == '-' and arg[1] in 'aenqsv':
      args.insert(index, '-' + arg[2:])
      arg = arg[:2]
  ```

  The loop then reads the remainder on the next pass, so `-qam` becomes `-q`, `-a`, `-m`;
  `-qn` reaches the `-n` refusal (exit 1); `-qC HEAD` reaches the reuse rule (exit 2);
  `-qZ` reaches "unsupported commit option" (exit 2); `-mq` stays `-m` with value `q`.
  `-S<keyid>` is untouched (it is not in the set).
- `check` line 367: the message names the command,
  `f'opaque interpreter command: {" ".join(command.argv)}; run git directly, for example git push origin HEAD:refs/heads/<branch>'`.
  The condition on lines 363 to 366 does not change (see spec Assumptions: identity and
  hooks are measured before the list runs).

### `adapters/vcs/git.py` `_run` (lines 176 to 177)

```python
if result.returncode:
    if b'not a git repository' in result.stderr:
        raise ValueError('not a git repository')
    raise ValueError(f'git exited {result.returncode}')
```

`result.stderr` is bytes here (no `text=`). Every other failure keeps "git exited <code>"
with no stderr text, so `tests/test_vcs.py::test_git_exit_is_explained` stays green.

### `cli/wuwei/guards/protect_state.py` `check_bash` (lines 301 to 310)

Split the cd clause out of the combined condition so its message is specific; decisions do
not change:

```python
except ParseError as exc:
    if (owner_edit_relevant or ... or (root is not None and _protected_name(...) and (...))):
        return 2, str(exc)
    if contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I):
        return 2, ('workspace guard: a top-level cd, pushd or popd to a directory that '
                   'cannot be resolved statically may leave the workspace; cd to a literal '
                   'directory inside it or use git -C')
    return 0, ''
```

## What must not change

- The normaliser grammar in `shell.normalize`, `_parse`, `_read_word`, `_unwrap`.
- `mentions(..., script=True)` and every other branch of `mentions`.
- The commit/push list rule (`len(commands) > 1` for non-git commands), push checks,
  identity checks and the `-S` handling.
- protect_state decisions, including every cd row in `tests/test_protect_state.py`.
- Every spec 4.5 bypass row in `tests/test_commit_push.py::test_bash_table`,
  `tests/test_deploy.py::test_decisions`, `tests/test_pr_guards.py::test_bypasses_and_relevance`
  and the tables in `tests/test_shell.py`, and `tests/test_guard_mutation.py`.
- No config keys, templates or docs pages (no user-facing configuration changes).

The one intended test reversal: `tests/test_shell.py::test_command_mentions_still_counts_substitutions`
(#205) asserts `mentions('x=$(pwd)', {'git', 'gh'}) is True`. Issue #226 requires the
opposite; replace it with the table in T001.

## Evidence for the builder

A scratch prototype of exactly these changes (without the two message-only edits) ran the
full suite: the only design-caused failure was the #205 pin above. In process against the
dry-run workspace it produced: `git commit -qm/-sm/-qam/-vqm` pass in the worktree; `-qn`
and `-nm` exit 1; `-qC HEAD` and `-qZ` exit 2; `x=$(pwd); echo $x` and
`x="$(pwd)"; echo "$x"` pass all guards; `python3 -m pytest -q && git status` and
`python3 -m pytest -q && gh pr view 1` pass; `git status | python3`, `python3 < d.py && git status`
and `git show HEAD:d.py | python3` are refused by deploy naming `python3`; `git push $(cat remote) main`,
`echo $(git push origin main)`, `x=$(pwd); $x push` and `a=gi; x=$(pwd) ${a}t push` stay
refused; the workspace root commit reports "not a git repository". Through
`wuwei.commands.hook.run` with `install_replay` (4 git calls, all exit 128 with the
not-a-repository stderr), the deny reason is
`commit/push guard could not run: git.commit_context: could not run: not a git repository`.

# Implementation Plan: read-only shell forms are not refused for being uninspectable, and shadow mode records them

**Branch**: `330-readonly-shell-forms` | **Date**: 2026-10-03 | **Spec**: `specs/330-readonly-shell-forms/spec.md`

## Summary

The shared spot is `shell.mentions` in `cli/wuwei/shell.py`: every Bash guard asks it
whether a call concerns it, before parsing and again after a parse failure. Its
constructed-name rule (lines 111-112) calls any git or gh text with any nonliteral word
relevant for every name. The fix narrows that one rule: a nonliteral word that is the
value of `-C`, `-R`, `--repo`, `--git-dir` or `--work-tree` cannot be a verb, so it no longer
counts. With that, the commit/push and deploy guards already fail closed only when their
own effect tokens are present, and need no code change. Two small guard edits finish the
issue: the deploy guard learns three read-only git commands, and the PR guard, on a parse
failure, fails closed only when `pr`, `api` or `alias` is mentioned (or an opaque relevant
script runs). Shadow mode, `NEVER_SHADOWED` and the state guard are untouched.

The design was checked before writing this plan on a scratch copy of main (not the
worktree): with exactly the three changes below, the full suite passed except four tests
that need the copy to be a git repository, and every form in spec US1 and US2 gave the
expected exit in enforce and shadow mode. A first design that judged only literal tokens
after a parse failure broke twelve pinned bypass rows (`${TOOL} ${VERB} -f`,
`git "$VERB" origin main`, `$DEPLOY apply`, ...) and was dropped.

## Technical Context

- Python 3.11+ stdlib only (`re`, already imported in every touched module).
- Reused: `shell.mentions`, `shell._literal`, `shell._GUARDED`, the PR guard's existing
  `script_relevant` and `possible_workspace_change`, `hook.shadow` and
  `guards.NEVER_SHADOWED` as they are.
- Tests: `tests/test_shell.py`, `tests/test_deploy.py`, `tests/test_pr_guards.py`,
  `tests/test_seat_command_forms.py` (its `workspace` fixture and `hook` helper run
  PreToolUse in process with seeded integrity evidence).
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I Stdlib only: yes.
- II Three-state exits, fail closed: unchanged. A relevant call that cannot be parsed is
  still exit 2 with the parser's reason. Only the relevance answer changes, and only for
  option values that cannot be a verb.
- III One behaviour, one function: relevance stays in `shell.mentions`; no guard gets its
  own copy of the rule.
- IV Test first: every change below has a failing test task before it (tasks.md).
- V Ponytail: three edits, about 12 lines; no new function, module or config. The known
  residual (an option value that word-splits into a verb) carries a `ponytail:` comment.
- VII Security first: no shadowing of the deployment ban or the merge policy (spec A1);
  every pinned bypass row stays green.
- Design spec 9.1 (relevance before parsing, a parse failure blocks only relevant calls):
  this fix is that rule, applied to option values.

## Changes

### 1. `cli/wuwei/shell.py`: narrow the constructed-name rule in `mentions`

Add next to `_GUARDED`:

```python
# git and gh options whose value is a directory or repository, never a verb.
_VALUES = ('-C', '-R', '--repo', '--git-dir', '--work-tree')
```

Replace lines 111-112:

```python
    if _GUARDED.search(unquoted) and not _literal(unquoted):
        return True
```

with:

```python
    # A word built at run time can be a git or gh verb; a directory or repository value cannot.
    # ponytail: an unquoted value can still word-split into a verb (r='. push'; git -C $r
    # origin main); the worktree pre-push hook and protected refs anchor that (spec 4.5).
    words = unquoted.split()
    if _GUARDED.search(unquoted) and any(
            not _literal(word) and not (index and words[index - 1] in _VALUES)
            and not re.match(r'-[CR]|--(?:repo|git-dir|work-tree)=', word)
            for index, word in enumerate(words)):
        return True
```

`unquoted` at that point is the quote-stripped text with substitutions replaced by
`$substitution` and redirect targets removed, exactly as today. Checking word by word on
the whole text (not per simple command) is deliberate: a quoted separator such as
`git -c "x.y=a;b" "$VERB" origin main` cannot hide `$VERB` from the rule. `-c` is
deliberately not in `_VALUES` (`sh -c "$CMD"`, `git -c` identity injection).

### 2. `cli/wuwei/guards/deploy.py`: three read-only git commands

In `git()`, the known set at lines 132-135 gains `'symbolic-ref', 'describe', 'show-ref'`.
The `unknown('unknown git command or alias')` refusal for anything else stays.

### 3. `cli/wuwei/guards/pr.py`: a parse failure blocks only a PR-relevant call

In `check`, the `except shell.ParseError:` branch at lines 357-360 becomes:

```python
        except shell.ParseError:
            # A parse failure blocks only a call that can reach a PR effect (#330).
            if (not script_relevant and not shell.mentions(raw, {'pr', 'api', 'alias'})
                    or initial is None and not possible_workspace_change(raw, {cwd})):
                return 0, ''
            raise
```

`script_relevant` must keep `sh push.sh` and `bash push.sh` (a script that runs
`gh pr merge`) refused: the pinned rows in `tests/test_pr_guards.py` fail without it.
`alias` keeps the existing `gh alias set|import|delete` refusal from being bypassed through
a loop.

## What must not change

- `guards.NEVER_SHADOWED`, `hook.shadow`, `hook.refuse` and the `guard.would_refuse`
  payload.
- Every rule in `cli/wuwei/guards/protect_state.py` (#222, #225), including its refusal of
  unparseable text that names `.wuwei`.
- `cli/wuwei/guards/commit_push.py` and the rest of `cli/wuwei/guards/deploy.py`
  (`DEPLOY_ACTIONS`, the `except ParseError` branch, `PERMISSIONS_DENY`).
- `shell.normalize` and the parser: control flow and substitution stay unsupported.
- Every other rule of `mentions`: ANSI-C `$'`, literal names, substitution bodies, the
  leftover `$(` and backtick rule, and the nonliteral command-word rule (lines 113-116).
- Every existing test row. New rows are added; none is edited or removed.

## Tests

- `tests/test_shell.py`: a new parametrized `test_command_mentions_ignores_directory_values`
  over the US3-2 texts with names `{'push', 'commit'}`.
- `tests/test_deploy.py`: new rows in the `test_decisions` table for the seven read-only
  git commands, the two read-only trial forms (0) and the push loop and merge (2).
- `tests/test_pr_guards.py`: new rows in `test_bypasses_and_relevance`: the `gh issue list`
  loop (0); the `gh pr list`, `gh api -X POST` and `gh alias set` loops (2).
- `tests/test_seat_command_forms.py`: the issue acceptance through PreToolUse
  (`test_issue_330_*`): the three trial forms exit 0 in enforce mode; the push loop and the
  merge exit 2 in enforce and shadow mode, with a `commit_push` `guard.would_refuse` in
  shadow and no `commit/push guard` text in the deny reason; the commit loop records and
  exits 0 in shadow mode. Shadow mode is set by writing `[guards]\nmode = "shadow"\n` to
  the fixture's `config.toml`; events are read from `.wuwei/days/*/events.jsonl`.

## Performance

`mentions` gains one `str.split` and a generator over the words, only when the text
mentions git or gh and the earlier rules did not already answer. Hook budgets under
`WUWEI_BENCH=1` are unaffected; `tests/test_hooks.py` budget tests must stay green.

## Complexity Tracking

None. No deviation from the constitution. The spec's conflict (A1) is resolved in favour
of the design spec and the constitution, not by new code.

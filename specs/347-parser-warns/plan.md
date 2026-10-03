# Implementation Plan: a command the parser cannot read warns instead of falling to the publish floor, and read-only commands are never opaque

**Branch**: `347-parser-warns` | **Date**: 2026-10-03 | **Spec**: `specs/347-parser-warns/spec.md`

## Summary

One classification in `cli/wuwei/shell.py`, consulted by every Bash guard at the points
where it fails closed today, and two reasons the hook levels by text. `shell.classify`
walks a command leniently (loops, conditionals, substitutions, here-docs, `sh -c`) and
answers four questions: are all words read-only, does a publisher word appear (or a word
it cannot pin), does it run inline interpreter code, and what text could a write in it
target. `shell.unread` turns that into the issue's decision table for the publish guards;
the state guard and the decision lint use `classify` with their own protected-path test.
`hook.posture` warns `UNPARSED` except under strict and warns the cd rule
(`WORKSPACE_ROOT`) in every posture. The floors, areas, postures, the parser and the
relevance helper are untouched; only the trigger of the floors narrows to calls that can
publish or write a record.

The design was checked before writing this plan on a scratch copy of main (not the
worktree): with exactly the changes below and the four test edits in spec A6, the full
suite passed (7407 passed, 10 skipped), the five shapes gave the spec's exits in all three
postures, and the publish and state-write forms of US2 refused in all three. Two earlier
variants were dropped there: putting the read-only check before the cd rule broke the
pinned `cd "$DEST"` and `CDPATH=..; cd other` rows, and judging stdin-fed interpreters as
inline downgraded the pinned `git status | python3` rows.

## Technical Context

- Python 3.11+ stdlib only: `shlex.shlex(punctuation_chars=...)`, `re`,
  `functools.lru_cache`, `pathlib.PurePosixPath`, `typing.NamedTuple`.
- Reused: `shell.normalize` and `ParseError` (for `Shape.parsed`), `shell.mentions(...,
  script=True)` (literal-token publisher scan), the guards' existing relevance and scope
  checks, `protect_state._STATE_MENTION`, `_STATE_GLOB` and `_owner_relevant`,
  `hook.posture`, the `guard.would_refuse` event, `heartbeat._hook` and `_exit`.
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I Stdlib only: yes.
- II Fail closed: a call the walk cannot read at all (unbalanced quotes, unterminated
  here-doc) counts as a publisher, so the guard refuses as today. `UNPARSED` is still exit
  2 from the guard; only the hook's level for it changes.
- III One behaviour, one function: classification lives only in `shell.classify`; guards
  consume it and add no parser (orchestrator note).
- IV Test first: tasks.md orders every test before its change.
- V Ponytail: one shared function plus one-to-four-line consults per guard; no new module,
  no config key. Residuals carry `ponytail:` comments (spec A11).
- VII Security first: the deployment ban, merge policy, commit and push rules and records
  floor still refuse every form in US2 in every posture; the hard boundaries of 9.1 are
  untouched.
- Design 9.1: relevance before parsing is kept; the classifier runs only after a guard
  found the call relevant and in scope. Design 4.5: the bypass table rows stay green
  (spec A6 lists the only edits, both from the issue's cd rule).

## Changes

### 1. `cli/wuwei/shell.py`: `classify`, `unread` and two reasons

Add `from functools import lru_cache`. Move the interpreter snippet flags in `is_opaque`
(`{'node': 'ep', 'perl': 'eE', 'ruby': 'e', 'php': 'r', 'lua': 'e'}`) to a module constant
`_SNIPPET` and use it in both places. Add at the end of the module:

```python
# Every cd, pushd and popd refusal of the state guard; the hook warns it in every posture.
WORKSPACE_ROOT = ('workspace guard: a top-level cd, pushd or popd may leave the workspace; '
                  'run it in a subshell, (cd <dir> && <command>), or use git -C <dir>')
# A relevant call the guards could not read and that names no publisher (#347).
UNPARSED = ('unparsed: write the commands to a file with the Write tool and run bash <file>; '
            'a plain git or gh command stays plain')
READ_ONLY = frozenset({'ls', 'cat', 'grep', 'head', 'tail', 'sed', 'wc', 'jq', 'diff', 'find',
                       'cd', 'pushd', 'popd'})
PUBLISHERS = ('gh', 'glab', 'hub')
# private: _GIT_READS (spec A3), _GIT_PUBLISH (the issue's verbs), _KEYWORDS, _WRAPPERS,
# _SHELLS, _FIND_ACTIONS, _INTERPRETER (the regex is_opaque already uses)


class Shape(NamedTuple):
    parsed: bool     # normalize read the whole command
    readonly: bool   # every command word is read-only and nothing is written
    inline: bool     # an interpreter runs code given inline (-c, -e, ...) or in a here-doc
    publishes: bool  # a publisher word, or a word the walk cannot pin to a safe form
    written: str     # the text a write in this call can target; '' when readonly
```

Functions (private helpers are short; names are a suggestion):

- `_cut(text, bodies) -> str`: one quote-aware pass. `$(...)` (balanced, quotes inside
  respected) and backticks become `$_<n>` with the body appended to `bodies`; a here-doc
  operator becomes ` << - ` and its body (up to the delimiter line) is cut; unquoted `#`
  comments are dropped; unquoted newlines become `;`. Raises `ValueError` on unbalanced
  quotes, substitutions or an unterminated here-doc.
- `_simple(text) -> list[(argv, writes, fed)]`: `shlex.shlex(text, posix=True,
  punctuation_chars=';&|()<>')`, `whitespace_split = True`, `commenters = ''`. Tokens made
  of `;&|()` end a simple command (`fed = 'pipe'` after `|`); tokens made of `<>&|` are
  redirects: the next token is the target, a `>` target is a write unless it is
  `/dev/null`, `/dev/stdout`, `/dev/stderr` or an fd duplication; `<<` sets
  `fed = 'heredoc'`, `<` sets `fed = 'pipe'`.
- `_git_publishes(args) -> bool`: skip `-C`, `-c`, `--git-dir`, `--work-tree`,
  `--namespace` with their values and other options; the first operand is the verb; true
  when it is nonliteral or not in `_GIT_READS`; false for bare `git`.
- `_names_publisher(text, publishers) -> bool`: `mentions(text, publishers, script=True)`
  or (`mentions(text, ('git',), script=True)` and `mentions(text, _GIT_PUBLISH,
  script=True)`).
- `classify(command, publishers=())`, `@lru_cache(maxsize=32)`: `parsed` from a
  `normalize` attempt; then `_classify(command, (*PUBLISHERS, *publishers))`; on
  `ValueError` or `RecursionError` return `Shape(parsed, False, False, True, command)`.
- `_classify(command, publishers) -> Shape`: cut the command and every substitution body
  (a queue), collect all simple commands, then for each:

| Simple command | Effect |
|---|---|
| leading `NAME=value` | recorded as an assignment, skipped |
| leading keyword (`if then else elif fi do done while until ! { } esac`) | skipped |
| starts with `for`, `select`, `case` (the header) | skipped |
| wrapper (`env command exec nohup time nice timeout sudo stdbuf setsid xargs`) | skipped with its options, assignments and a duration; `xargs` sets `publishes` |
| nonliteral command word (`$W`, `${W}`, `$_n`) | not read-only; `publishes` unless its variable is assigned in this call to text `_names_publisher` rejects and every argument is literal and not a publisher program, git verb or `git` |
| `sh bash zsh dash ksh` with a `-c`-style option and a script | recurse; merge `readonly`, `inline`, `publishes`, `written` |
| a shell without `-c`, `eval`, `source`, `.` | `publishes` |
| interpreter with a snippet flag, or reading a here-doc | `inline`; `publishes` if `_names_publisher(command)` |
| interpreter with no operand fed by a pipe or `<` | `publishes` (the code is never in the text) |
| `git` | `publishes` if `_git_publishes(args)` |
| a publisher program | `publishes` |
| `sed` | read-only only as `-n` with a `[0-9,$]+p` script and no `-i`/`--in-place` |
| `find` | read-only unless an action in `_FIND_ACTIONS` |
| any other word, or any redirect write | not read-only |

  For every simple command that is not read-only: `readonly = False`; its text (tokens and
  write targets, `$_n` expanded back to `$(body)`) is appended to `written`; `publishes`
  also when `_names_publisher(text)`; `whole` when an argument or write target is
  nonliteral. At the end: `readonly = readonly and not publishes and not inline`; when
  readonly return `Shape(False, True, False, False, '')`; otherwise append each assignment
  as `name=value` with `$_n` expanded unless that body classifies read-only, and set
  `written` to the whole command when `whole`, else the joined texts.
- `unread(command, publishers=()) -> tuple | None`:

```python
def unread(command, publishers=()):
    """#347 decision table for a relevant call a guard cannot read: (0, '') when every word
    is read-only; UNPARSED when the parser could not read it, or it runs inline code, and
    no publisher word appears; None when the guard decides as before."""
    shape = classify(command, tuple(publishers))
    if shape.readonly:
        return 0, ''
    if not shape.publishes and (not shape.parsed or shape.inline):
        return 2, UNPARSED
    return None
```

The `ponytail:` comment in `_classify` names the residuals of spec A11.

### 2. `cli/wuwei/commands/hook.py`: level two reasons by text

In `posture`, import `UNPARSED, WORKSPACE_ROOT` from `wuwei.shell` (not from a guard
module: hook tests replace the guards package), and in the loop:

```python
    enforced, shown, seen = [], None, set()
    for check, reason in refusals:
        guard, area, decided, line = level(check, levels)
        if reason in (UNPARSED, WORKSPACE_ROOT):  # #347: decided by the reason, not the area
            if reason in seen:
                continue
            seen.add(reason)
            decided = 'block' if reason == UNPARSED and name == 'strict' else 'warn'
            line = ''
```

The unchanged rest records `guard.would_refuse` (warn) or enforces (block). The
no-workspace and unreadable-config path still enforces everything, and heartbeat sessions
still skip `posture`.

### 3. `cli/wuwei/guards/commit_push.py` (`check`)

- In `except shell.ParseError:` (lines 282-298), each of the three `raise` statements
  (inside a session; a word that reaches a workspace; the `-C`/`cd` regex) becomes:

```python
                if (found := shell.unread(raw)) is None:
                    raise
                return found
```

- After `if not scoped: return 0, ''` (line 339-340), before `if opaque_script:`:

```python
        if (found := shell.unread(raw)) is not None:
            return found
```

  This fixes S2 (read-only list: `(0, '')`) and S4 (inline, no publisher: `UNPARSED`
  instead of "standalone environment assignment before Git").

### 4. `cli/wuwei/guards/deploy.py` (`check`)

- Import `unread`. In `except ParseError:` (lines 269-272), after the existing relevance
  return, replace `raise` with `if (found := unread(raw, protected[2:])) is None: raise`
  then `return found`.
- Directly after the `try`/`except` (before the `for index, command` loop):
  `if (found := unread(raw, protected[2:])) is not None: return found`.
  `protected[2:]` are the deploy programs and `[deploy].deny` programs (`git` and `gh` are
  handled by the classifier itself).

### 5. `cli/wuwei/guards/pr.py` (`check`)

- In `except shell.ParseError:` (lines 357-364), replace the final `raise` with the same
  three lines using `shell.unread(raw)`.
- After `if not contexts: return 0, ''` (line 383-384), before `if script_relevant:`:
  `if (found := shell.unread(raw)) is not None: return found`.

### 6. `cli/wuwei/guards/protect_state.py` (`check_bash`)

- Import `WORKSPACE_ROOT` from `wuwei.shell` at module level; import `UNPARSED` and
  `classify` with the other local shell imports.
- The parse-failure branch (lines 421-431) becomes:

```python
            shape = classify(script)
            # A word the walk cannot pin may be the CLI; otherwise only literal words count.
            if ((owner_relevant and guard_scope(payload) is not None
                 and (shape.publishes or _owner_relevant(script, script=True)))
                    or _STATE_MENTION.search(shape.written) or _STATE_GLOB.search(shape.written)
                    or (root is not None and _protected_name(cwd, directories=True)
                        and (isinstance(exc, NonliteralPathError)
                             or (_DYNAMIC.search(script) and _WRITE_CONSTRUCT.search(script))))):
                return 2, str(exc)
            if contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I):
                return 2, WORKSPACE_ROOT
            if shape.readonly:
                return 0, ''
            if _STATE_MENTION.search(script) or _STATE_GLOB.search(script):
                return 2, UNPARSED
            return 0, ''
```

  The cd check stays before the read-only check (pinned rows `cd "$DEST"`, `HOME=..; cd`,
  `CDPATH=..; cd other` keep exit 2 at guard level; the hook warns them).
- Parsed path: `'Unknown directory stack; ...'` (line 468) and `'Keep the workspace root;
  ...'` (line 476) return `WORKSPACE_ROOT` with their current codes (2 and 1); the
  `_cd_target(command)` call at line 471 is wrapped so its `ValueError` returns
  `(2, WORKSPACE_ROOT)`. The opaque interpreter rule at lines 442-445 is unchanged (inline
  code that names a state file keeps the floor, spec A4).

### 7. `cli/wuwei/guards/decision.py` (`check_write`)

- Import `UNPARSED` and `classify`.
- In `except ParseError:` (lines 56-68), before the final `raise ValueError(...)`:

```python
            shape = classify(raw)
            if shape.readonly:
                return 0, ''
            if shape.inline or 'D-' not in shape.written:
                return 2, UNPARSED
```

- Line 86-87: `results.append((2, UNPARSED))` instead of the opaque-command message; the
  day's records are still linted below it.

### 8. `cli/wuwei/heartbeat.py` and `cli/wuwei/commands/doctor.py`

- `heartbeat.READ_LOOP = 'for r in a b; do cat .wuwei/$r/report.json; done'` with a
  `#347` comment; a `PROBES` row `('read_loop', 'hook PreToolUse allows a for loop over cat
  in .wuwei (exit 0)')` placed right after `status_line` (existing positional assertions in
  `tests/test_heartbeat.py` keep holding); `measure` appends
  `_hook(root, 'Bash', {'command': READ_LOOP})` as the last call, unpacks a fifth result
  `loop`, sets `read_loop=_exit(loop, 0)` and adds `read_loop` to the unmeasured names.
- `doctor._guards`: add `'read_loop'` to the probe names, after `'state_write'`.

### 9. Docs

- `docs/site/reference.md`, Heartbeat table: a `read_loop` row (Bash
  `for r in a b; do cat .wuwei/$r/report.json; done` exits 0).
- `docs/site/security.md`, Security posture, after the floors list: one short paragraph:
  a relevant command the guards cannot read (a loop, a substitution, inline interpreter
  code) and that names no publishing tool and writes no record warns under observe and
  guarded and blocks only under strict, with the one accepted form; a command whose words
  are all read-only passes; a top-level cd, pushd or popd that may leave the workspace
  warns in every posture. No em-dashes.

## What must not change

- `shell.normalize` and its grammar, `shell.mentions`, `shell.is_opaque` (beyond reading
  `_SNIPPET`), `shell.script_text`.
- `guards.AREAS`, `OWNER_ONLY`, `level`; `workspace.POSTURES`, `FLOORS`, `posture`.
- Each guard's relevance and scope checks and their order (#323 scope first, #330), the
  owner-action table and `_owner_action`, the parsed-path logic after the new consults,
  and every Write/Edit guard.
- Every existing test row, except the four edits listed in spec A6.

## Tests

- `tests/test_shell.py`: `test_classify_table` over the plan table forms (the US1 shapes,
  the US2 forms, `$x push origin main`, `${TOOL} ${VERB} -f`, `$DEPLOY apply`,
  `timeout 5 git push origin main`, `find . -exec git push \;`,
  `sh -c 'for r in a; do git push; done'`, `for r in a b; do git -C $r log -1; done`,
  `for r in a b; do git -C $r config core.hooksPath x; done`, `for r in a b; do git -C $r p; done`,
  `echo "unterminated`, `for f in *.py; do wc -l $f; done`, `sed -n 1,40p x`,
  `sed -i s/a/b/ x`, `cat cmds.txt | xargs git`, `echo "gh pr merge 17"`,
  `grep -n "git push" notes.md`, `git show HEAD:d.py | python3`,
  `python3 - <<'PYEOF'` with a `gh` call), asserting `readonly`, `publishes`, `inline` and
  whether `written` mentions `.wuwei`; `test_unread_table` for the three answers.
- Guard tables: rows in `tests/test_commit_push.py`, `tests/test_deploy.py`,
  `tests/test_pr_guards.py`, `tests/test_protect_state.py`, `tests/test_decision.py`.
- `tests/test_parser_warns.py` (new): the five shapes under each posture through
  PreToolUse in process (fixture and `hook` helper as in `tests/test_seat_command_forms.py`,
  posture written as `[security]\nposture = "<name>"\n`); the publish and state-write forms
  in every posture; the heartbeat-session read loop; the decision lint through PostToolUse.
- `tests/test_heartbeat.py`, `tests/test_doctor.py`: fixtures for the fifth probe and a
  payload assertion for `READ_LOOP`; `tests/test_docs.py`: the security page names
  `unparsed`.

## Performance

`classify` runs only on a relevant call a guard could not read or judged opaque, and is
cached per command, so the four Bash guards share one walk. `tests/test_hooks.py` budget
tests stay green (checked on the scratch copy).

## Complexity Tracking

The classifier is the one sizeable addition (about 150 lines with its tables). The issue
asks for exactly this shared step; the alternative, extending `normalize` to accept loops
and substitutions, would change the parser every guard trusts for parsed calls and the
bypass tables pinned on it.

## Changes made during implementation

Each one makes the classifier stricter than the table above. None of them changes a pinned row.

- `commit_push` passes `('rm',)` to `unread`. That guard is relevant to `rm` because of the hook pointers, so `python3 -c '...'; rm wuwei-workspace` keeps its refusal and does not become `UNPARSED`.
- `git -c` and `--config-env` count as publishers, because a config value can define an alias or run a command.
- A nonliteral command word is pinned only when no assigned value mentions `git` or a publisher program and no argument is `git`, a publisher program or one of the issue's git verbs (`G=git; $G config core.hooksPath x` publishes).
- A `for` or `select` header counts as an assignment of its variable (`W=cat; for W in gh; do $W ...; done` publishes).
- An unquoted here-doc whose body contains `$(` or a backtick cannot be walked, so it counts as a publisher. When a command fed by a here-doc is not read-only, `written` is the whole command, so the state guard sees the body.

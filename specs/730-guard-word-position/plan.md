# Implementation Plan: the command guard judges words by position

**Branch**: `730-guard-word-position` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Two shared spots, no new module:

1. `cli/wuwei/shell.py`: one helper, `leading_variables(text)`, reads the literal values of a
   leading assignment statement. `_unwrap` uses it to resolve a program-position `$x` (the
   parser), and `mentions` uses it so a resolved `$x` is not a possible git or gh word (the
   relevance helper every Bash guard calls). The nonliteral-command refusal names the word and
   the stage.
2. `cli/wuwei/guards/protect_state.py`, `_owner_action`: two predicates decide by the stage's
   program whether its argument words are data: `_pattern_args` (grep, rg, `git grep`: words
   never reach the output) and `_text_script` (awk or sed with no run or write construct: a
   reader). Both Opaque owner action refusals append the stage and the word.

Relevance (`_owner_relevant`, `_CLI_NONLITERAL`, `_WUWEI`) does not change; only the parsed
decision does.

A scratch copy of this exact design (outside the repository) passed every test in
`tests/test_shell.py`, `test_protect_state.py`, `test_owner_actions.py`, `test_commit_push.py`,
`test_deploy.py`, `test_pr_guards.py`, `test_parser_warns.py`, `test_decision.py`,
`test_guard_mutation.py`, `test_vcs_guard.py`, `test_integrity.py`, `test_scope_first.py` and
`test_hooks.py` unchanged (3609 passed), exited 0 through the full hook on the three acceptance
rows, and kept every bypass probe in the spec at exit 2.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. No new module, port, event kind, state key or
config key. Touched: `cli/wuwei/shell.py`, `cli/wuwei/guards/protect_state.py`,
`docs/specs/2026-09-24-wuwei-design.md` (one 9.2 row), tests. Hook latency: one `re.sub` and
one `re.match` per `normalize` call and per `mentions` call that reaches its last clause;
no file read.

## Constitution Check

- I stdlib: `re` and `shlex` only.
- II exits: nothing that refused before passes except a search pattern (grep, rg, git grep,
  effect-free awk or sed) and a CLI path in a leading literal assignment; parse failures still
  raise `ParseError` and guards still return 2.
- III one behaviour, one function: variable resolution lives in `shell.leading_variables`,
  read by the parser and the relevance helper; argument-word judgement lives in
  `_pattern_args` and `_text_script`, read only by `_owner_action`.
- IV test first: tasks.md orders every test before its code.
- V ponytail: reuse `_ASSIGNMENT`, the `_variable_read` variable pattern, `git_kind`,
  `_READERS`, `_CLI_WORD`, `_WUWEI`; no variable evaluator, no awk or sed parser.
- VII security: owner-action floor unchanged. awk and sed are readers only when their script
  can neither run nor write; grep's words are data only because grep prints file lines (the
  same text `cat file` prints today without a mention); a variable resolves only from the
  first statement, which always runs before any later stage, and never to git, gh or another
  protected program.
- Workflow (#530): a changed guard rule adds 9.2 row I51 and its `tests/test_invariants.py`
  check (ids taken by sibling plans in this wave: I29, I30, I41, I47, I49, I50, I54, I56, I57,
  I58, I65; renumber on rebase if I51 is taken by then).

## Changes, by file

### `cli/wuwei/shell.py`

After `_ASSIGNMENT` (line 67) add:

```python
# #730: a whole word that is one plain variable (the _variable_read form).
_VARIABLE = re.compile(r'"?\$\{?([A-Za-z_]\w*)\}?"?')


def leading_variables(text):
    """#730: {name: value} of a leading assignment statement (x=bin/wuwei; ...) whose values are
    single literal words; a name assigned again anywhere in the text is left out."""
    text = re.sub(r'''['"\\]''', '', text)
    match = re.match(r'\s*((?:[A-Za-z_]\w*=[\w./][\w./:@+-]*[ \t]+)*[A-Za-z_]\w*=[\w./][\w./:@+-]*)'
                     r'[ \t]*(?:;|&&|\n)', text)
    pairs = dict(word.split('=', 1) for word in match[1].split()) if match else {}
    return {key: value for key, value in pairs.items()
            if len(re.findall(rf'(?<![\w$]){key}=', text)) == 1}
```

Why only the first statement: it always runs, in the outer shell, before every later stage,
so a later `$x` always sees that value unless the text assigns `x` again (then left out).
No scope tracking is needed. Optionally reuse `_VARIABLE` in `_variable_read` (line 840) in
place of its inline pattern; same regex.

`mentions` (line 134, the last `return`): a resolved variable is judged by its value:

```python
    variables = leading_variables(raw)
    return any(not _literal(word) and not ((name := _VARIABLE.fullmatch(word)) and name[1] in variables
                                           and not pattern.search(variables[name[1]]))
               for word in re.findall(
        r'(?:^|[;&|(\n])\s*(?:[A-Za-z_]\w*=[^\s;&|()]*\s+)*([^\s;&|()]+)', unquoted)
        if not _ASSIGNMENT.match(word))
```

`normalize` (line 230): pass `variables=leading_variables(command)` to `_parse`.

`_parse` (line 289): add keyword `variables=None`; pass `variables=variables` to `group`'s
`_unwrap` call (line 390). Do not pass it to the `eval` `_parse` (line 461) or the `sh -c`
`_parse` (line 492): a child shell does not inherit unexported variables, and eval keeps
today's refusal.

`_unwrap` (line 429): add keyword `variables=None`; pass it on in the `xargs` recursion
(line 552, the outer shell expands `$x` before xargs runs). Replace lines 442-443:

```python
        if not _literal(raw_argv[0]):
            name = _VARIABLE.fullmatch(raw_argv[0])
            value = (variables or {}).get(name[1]) if name else None
            if value is None or PurePosixPath(value).name in protected:
                raise ParseError(f'nonliteral command name {raw_argv[0]} in stage {" ".join(raw_argv)} is unsupported; '
                                 'assign it a literal path at the start of the command (x=bin/wuwei; $x ...), '
                                 'or write the command name literally')
            argv, raw_argv = [value, *argv[1:]], [value, *raw_argv[1:]]
            program = PurePosixPath(value).name
```

Everything after (path commands, `_reject_mentions`, control-flow words, wrappers, git and gh
protection) then runs on the resolved program, unchanged.

Coordination: #671 (`671-guard-reads-argv`) also adds a keyword to `_parse` and `_unwrap`
(`texts`) and touches `mentions`. The two are independent; whichever lands second merges both
keywords at each call site.

### `cli/wuwei/guards/protect_state.py`

After `_READERS` (line 144) add:

```python
# #730: what an awk or sed script runs or writes. ponytail: a token scan, not a parser; it
# over-matches (any e, w or W command or flag word, a pipe, a redirect), and a script it
# cannot clear keeps the refusal.
_SCRIPT_EFFECT = r'system|getline|[|>]|(?<![A-Za-z])[gpiImM0-9]*[ewW](?![A-Za-z])'


def _text_script(argv):
    """#730: awk or sed whose script runs nothing and writes no file only reads."""
    words = argv[1:]
    return (bool(argv) and Path(argv[0]).name in ('awk', 'sed')
            and all(re.fullmatch(r'-[nEr]+|-e|-F.*', word) for word in words if word.startswith('-'))
            and not re.search(_SCRIPT_EFFECT, ' '.join(word for word in words if not word.startswith('-'))))


def _pattern_args(argv):
    """#730: grep prints matched lines, never its pattern, so its words are data in any pipe or
    redirect; --label, rg --replace and rg --pre print or run their words.
    ponytail: -l and -H print file names, and a file named as a command must already exist;
    ls | tclsh reaches that today too."""
    from wuwei.shell import git_kind
    program = Path(argv[0]).name if argv else ''
    if program == 'git':
        return argv[1:2] == ['grep'] and git_kind(argv[1:]) == 'read'
    return (program == 'grep' and not any(word.startswith('--label') for word in argv)
            or program == 'rg' and not any(re.match(r'--(?:replace|pre)|-[A-Za-z]*r', word)
                                           for word in argv[1:]))
```

`_text_script` excludes `-i`, `-f`, `-v` and any other option by the option allowlist, so
`sed -i`, `awk -f prog.awk` and `gawk -i inplace` keep today's handling. `git grep -O...`
is not a read (`git_runs`), so it is not data.

In `_owner_action`:

- `readers` (line 243): add `or _text_script(c.argv) or _pattern_args(c.argv)` to the
  predicate. awk and sed then count as readers for their own words (line 267 skips them) and
  as non-executors downstream (`feeds`); they are readers only when they cannot write, which
  is the `_READERS` contract.
- The accounting (line 257): subtract a stage's mentions when
  `not readers[index] or _pattern_args(argv) or (<the stand-alone test as today>)`. Otherwise,
  when `named`, remember the stage for the reason:
  `kept = (shlex.join(argv), _WUWEI.search(' '.join([*argv, *command.env.values()]))[0])`
  (initialise `kept = None` before the loop).
- Line 281: bind the match first (`word = re.search(_CLI_WORD, ' '.join(words))`, then
  `if hidden or word:`) and append to the existing literal reason
  `f' Stage: {shlex.join(argv)}; word: {word[0] if word else program}.'`.
- Line 330: append `f' Stage: {kept[0]} feeds a pipe or file; word: {kept[1]}.'` when `kept`,
  else `' The mention sits in a here-doc, comment or input no stage shows.'`.

Keep both literal prefixes `'Opaque owner action: write bin/wuwei <group> <verb> as a plain
command so the '` in `_owner_action`: `test_owner_action_reasons_name_the_command` counts them.

### `docs/specs/2026-09-24-wuwei-design.md`

Append to the 9.2 table, after the I44 row (the table order must equal `INVARIANTS`):

`| I51 | A word is the CLI only in program position: a grep, rg or git grep pattern and an awk or sed script that can neither run nor write pass the records guard in every posture; an awk or sed that runs, and an argument-echoing stage piped into an executor, are refused in every posture; a CLI path in a leading literal assignment is judged as the CLI | per posture, through the hook, grep "wuwei decide" piped into sort, and x=bin/wuwei; $x state set a b; check_bash for a seat on awk system("bin/wuwei decide D-1 a") and on x=bin/wuwei; $x decide D-1 a | #730; argument words judged in protect_state._owner_action, variables resolved in shell.leading_variables |`

### Tests

- `tests/test_shell.py`: `leading_variables` table; `normalize` resolution table; the
  refusal text; `mentions` relevance rows.
- `tests/test_owner_actions.py`: new `SEARCH_FORMS` (pass, inside) and rows appended to
  `EXECUTOR_PROBES` (refused inside, 0 outside); acceptance rows through `hook`; reason text.
- `tests/test_invariants.py`: `i51`, registered in `INVARIANTS` and `READS` (`(0,)`).

## What must not change

- Relevance: `_owner_relevant`, `_WUWEI`, `_CLI_WORD`, `_CLI_NONLITERAL`, `_READERS` and its
  use in `_write_targets`.
- `classify`, `_classify`, `unread`, `_variable_read`'s behaviour, `is_opaque`,
  `snippet_write`.
- Every existing assertion: `forms()` (`X={group}; bin/wuwei $X {verb}` stays 2), the
  executor, interpreter and regression lists, `G=git; $G push origin main` (deploy refuses,
  test_deploy and test_parser_warns), `T="tee ..."; echo x | $T`, the CLASSIFY table.
- Interpreters (`python3 -m pytest -k "wuwei and decide"`, `perl -ne`) keep their refusal.
- Argument-position variables are not resolved (`cd $d`, `bin/wuwei $X verb`).

## Deferred

- An interpreter's non-code arguments (a pytest `-k` pattern) as data: needs a per-tool rule.
- Argument-position variables from the leading statement (`d=tests; cd $d`).

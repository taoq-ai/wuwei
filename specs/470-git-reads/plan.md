# Implementation Plan: every read-only git subcommand is known, unknown git subcommands warn, read loops pass

**Branch**: `470-git-reads` | **Spec**: `specs/470-git-reads/spec.md`

## Summary

Two root causes, two shared spots. (1) The deploy guard's private git subcommand tuple
(`guards/deploy.py:132-136`) drifted from the classifier's `_GIT_READS`; replace both with
one set of git tables and one function, `shell.git_kind`, and give its `unknown` outcome a
reason the hook levels by its text, like `UNPARSED`. (2) `echo` is missing from
`shell.READ_ONLY`; add it, and let a non-read fed by a pipe count its whole command as
written so echoed text piped into a shell keeps the records floor. The heartbeat and
doctor gain the two shapes.

## Technical Context

Python 3.11+, stdlib only. No new module, no new import on the hook path: `deploy` already
imports from `wuwei.shell`, and `hook.posture` already imports `UNPARSED` and
`WORKSPACE_ROOT` from `wuwei.shell` inside the function; the new names join those two
import lines.

## Constitution Check

- I stdlib only: yes.
- II exits: the unknown outcome is exit 2 with a reason, as every could-not-decide is; the
  hook decides warn or block by posture, as it does for `UNPARSED`.
- III one behaviour, one function: `shell.git_kind` is the one git outcome; the deploy
  guard and the classifier both call it, and the deploy tuple is deleted.
- IV test first: every behaviour below has a test task before its implementation task.
- V ponytail: the tables are data; one function; one word added to `READ_ONLY`; no change
  to `protect_state.py` or `commit_push.py`.
- VII security: an override that can define an alias keeps today's refusal; options that
  run a program make a read unknown; the reason-levelled downgrade applies to the deploy
  guard only; push and record writes in loops still refuse.

## Design

### 1. `cli/wuwei/shell.py`: the git tables and `git_kind`

Replace `_GIT_READS` (lines 605-609) with the block below. Keep `_GIT_PUBLISH` (line 610)
exactly as it is: it is the mention list `_names_publisher` and the `$var` check in
`_classify` match anywhere in text, not the argv table.

```python
# #470: git subcommands by outcome (data; tests/test_shell.py pins them). The deploy guard
# passes reads and writes; the classifier publishes anything not a read; any other
# subcommand, an alias included, is unknown (spec A3).
# ponytail: reflog and symbolic-ref with extra operands edit local refs; a local ref is not
# a publish, and the pre-push hook and protected refs anchor pushes (spec 4.5).
_GIT_READS = frozenset({
    'status', 'diff', 'log', 'show', 'rev-parse', 'ls-files', 'ls-remote', 'symbolic-ref',
    'describe', 'show-ref', 'blame', 'annotate', 'grep', 'cat-file', 'ls-tree', 'rev-list',
    'for-each-ref', 'shortlog', 'name-rev', 'reflog', 'merge-base', 'range-diff',
    'merge-tree', 'check-ignore', 'count-objects', 'var', 'whatchanged', 'cherry', 'fetch',
    'help', 'version'})
# Read only when the first word after the subcommand ('' when bare) and every flag are among
# these words; any other form writes.
_GIT_READ_FORMS = {
    'branch': ('', '--list', '-l', '-a', '--all', '-r', '--remotes', '-v', '-vv',
               '--show-current'),
    'tag': ('', '--list', '-l'),
    'remote': ('', '-v', '--verbose', 'show', 'get-url'),
    'stash': ('list', 'show'),
    'worktree': ('list',),
    'config': ('--get', '--get-all', '--get-regexp', '--list', '-l'),
    'bisect': ('log',)}
_GIT_WRITES = frozenset({
    *_GIT_READ_FORMS, 'push', 'commit', 'merge', 'rebase', 'reset', 'checkout', 'switch',
    'filter-branch', 'update-ref', 'am', 'cherry-pick', 'revert', 'notes', 'submodule', 'gc',
    'prune', 'clean', 'rm', 'mv', 'apply', 'add', 'restore', 'init'})
# Options that make a read run a program.
_GIT_RUNS = ('-O', '--open-files-in-pager', '--upload-pack')
# The deploy guard's reason for an unknown subcommand starts with this; the hook levels it.
UNKNOWN_GIT = 'unknown git subcommand '


def git_kind(args):
    """#470: 'read', 'write' or 'unknown' for git's argv after the program name."""
    args = list(args)
    while args and args[0].startswith('-'):
        if args[0].startswith(('-c', '--config-env')):
            return 'unknown'  # a config value can define an alias or run a command
        args = args[2:] if args[0] in ('-C', '--git-dir', '--work-tree', '--namespace') else args[1:]
    if not args:
        return 'read'
    verb, rest = args[0], args[1:]
    if '$' in verb or any(arg.startswith(_GIT_RUNS) for arg in rest):
        return 'unknown'
    if verb in _GIT_READS:
        return 'read'
    forms = _GIT_READ_FORMS.get(verb, ())
    if (rest[0] if rest else '') in forms and all(arg in forms for arg in rest if arg.startswith('-')):
        return 'read'
    return 'write' if verb in _GIT_WRITES else 'unknown'
```

`remote` leaves the read set (it is a form now). The builder may reorder or reflow the
literals; the members are the contract the table test pins.

Delete `_git_publishes` (lines 782-791) and change its one caller in `_classify` (line 906)
to `publishes |= git_kind(args) != 'read'`. Behaviour is today's: `-c`, a `$` subcommand and
any non-read publish; the only differences are the wider read set and the forms
(`git branch --list` in a loop is now a read, `git remote add` a publish).

Add `'echo'` to `READ_ONLY` (line 602). `echo ... > file` keeps its target through
`writes`, and a `$(...)` argument is classified as its own text.

Two companion edits keep the floor where `echo`'s arguments used to hold it (spec, "What
`echo` was silently holding up"; both prototyped on a scratch copy):

- `_classify` line 913: `whole |= not literal or fed == 'heredoc'` becomes
  `whole |= not literal or fed in ('heredoc', 'pipe')`. A non-read reading a pipe may run
  the piped text, so the whole command is what it can write. Read pipelines never reach
  this line (`safe` is true for read words).
- `reads` line 822: `return len(args) == 3` becomes `return len(args) < 4` (comment: no
  operand reads standard input; a second operand is json.tool's outfile), so
  `cat <file> | python3 -m json.tool` inside a loop stays a read under the pipe rule.

### 2. `cli/wuwei/guards/deploy.py`: use the table

Import line 10 gains `UNKNOWN_GIT, git_kind`. Replace lines 132-137 (the tuple test and the
final return) with:

```python
    if git_kind([action, *args]) != 'unknown':
        return 0, ''
    if override:  # -c, --git-dir, --work-tree or GIT_*: the override can define the alias
        unknown('unknown git command or alias')
    return 2, f'{UNKNOWN_GIT}{action}; if it publishes, run it as a plain literal command from a host terminal'
```

The global-option loop, `push` and `merge` handling above stay as they are. `override` is
the existing local (`GIT_*` env, `-c`, `--git-dir`, `--work-tree`, `--config-env`).

### 3. `cli/wuwei/commands/hook.py` `posture`: level the reason by its text

Line 244 becomes `from wuwei.shell import UNKNOWN_GIT, UNPARSED, WORKSPACE_ROOT`. Lines
250-255 become:

```python
        # #347, #470: decided by the reason, not the area; only deploy says unknown git
        if reason in (UNPARSED, WORKSPACE_ROOT) or guard == 'deploy' and reason.startswith(UNKNOWN_GIT):
            if reason in seen:
                continue
            seen.add(reason)
            decided = 'block' if reason != WORKSPACE_ROOT and name == 'strict' else 'warn'
            line = ''
```

`guard` is the module name `level` already returned. Scoping the prefix match to `deploy`
keeps any other guard's text from lowering its own level.

### 4. `cli/wuwei/heartbeat.py` and `cli/wuwei/commands/doctor.py`: the probes

- `PROBES`: `read_loop` description becomes `hook PreToolUse allows a for loop over echo and
  cat in .wuwei (exit 0)`; add `('git_read', 'hook PreToolUse allows git grep (exit 0)')`
  right after `read_loop`.
- `READ_LOOP = 'for r in a b; do echo "### $r"; cat .wuwei/$r/report.json; done'` (the
  comment gains `#470: the owner's echo shape`); add `GIT_READ = 'git grep -n probe'` next
  to it (no path operand: a git operand naming a protected file keeps the records floor).
- `measure`: append `_hook(root, 'Bash', {'command': GIT_READ})` to `calls`; unpack it as
  a sixth result; `found.update(..., git_read=_exit(git_read, 0))`; add `'git_read'` to the
  unmeasured list in the `except`. Do not add it to `timed` (telemetry and design 5.13 keep
  four timed probes).
- `doctor._guards` (line 570): the name tuple gains `'git_read'` after `'read_loop'`.

### 5. Docs

- `docs/site/reference.md`: the `read_loop` row shows the new command; a `git_read` row
  after it: `` `hook PreToolUse` with Bash `git grep -n probe` exits 0 `` with value
  `` `exit N`, plus the first stderr line when not ok ``. The paragraph under the table is
  unchanged (git_read has no `ms`).
- `docs/site/security.md` line 61: add `echo` to the read-only word list, and add after the
  read-only sentence: "A git subcommand that is neither a known read (`status`, `log`,
  `diff`, `show`, `grep`, `blame` and the rest) nor a known write (`push`, `commit`,
  `merge`, `add` and the rest) is an unknown git subcommand: it warns under `observe` and
  `guarded`, naming the subcommand, and blocks only under `strict`. With a `-c`,
  `--git-dir`, `--work-tree` or `GIT_*` override it stays refused, because the override can
  define an alias."
- The design spec is not edited (owner only).

## What must not change

- `shell.normalize`, `shell.unread`, `UNPARSED`, `WORKSPACE_ROOT`, `_GIT_PUBLISH`,
  `_names_publisher`, `mentions`; in `_classify` only the two lines named above change.
- `guards/protect_state.py` and `guards/commit_push.py` (no edits; they pick up `echo`
  through `shell.reads` and `classify`).
- `guards/__init__.py` (`OWNER_ONLY`, `AREAS`), `workspace.FLOORS`, `telemetry.PROBES`.
- Deploy's push and merge handling, its global-option loop, and its refusal of unknown
  subcommands under a config or repository override.
- The hook import graph (#346 tests in `tests/test_hooks.py` pass unedited).

## Existing test rows that change on purpose

- `tests/test_shell.py` `CLASSIFY`: `('echo "gh pr merge 17"', (False, True, False, False))`
  becomes `(True, False, False, False)`.
- `tests/test_decision.py` `test_relevant_opaque_or_unparseable_bash`: the row
  `'for x in D-3; do echo x; done'` becomes `'for x in D-3; do touch x; done'` (still
  `UNPARSED`, exit 2; the echo loop is now a read and exits 0).
- `tests/test_profiles.py` `test_hard_guards_under_each_profile`: the row
  `echo "gh pr merge 17"` becomes `printf "gh pr merge 17"` (found while building: the
  prototype did not run this file; printing a word with `echo` now passes, and `printf`
  keeps the row's intent, a non-read naming `gh` in quotes).

No other existing row changes. In the scratch prototype the suite showed exactly these two
plus `tests/test_protect_state.py` `echo .wuwei/config.toml | sh`, which the pipe rule
restores without editing the test. (`test_hooks.py::test_status_line_skips_parser_and_hashlib`
also failed there, from the scratch directory's surroundings; it passes in the worktree.)

## Tests (files)

- `tests/test_shell.py`: `git_kind` table over every set member and the form cases;
  main's deploy tuple stays known; `echo` read-word and pipe-rule cases through `classify`
  and `unread`.
- `tests/test_protect_state.py`: `test_issue_349_shared_read_predicate` gains
  `(['python3', '-m', 'json.tool'], True)`.
- `tests/test_deploy.py`: new rows in the `test_decisions` table.
- `tests/test_parser_warns.py`: the five owner rows per posture; unknown subcommand per
  posture; push and commit in loops; commit in `$(...)` per posture; both heartbeat probe
  commands per posture.
- `tests/test_hooks.py`: a non-deploy guard returning an `UNKNOWN_GIT` reason keeps its
  area level.
- `tests/test_heartbeat.py`, `tests/test_doctor.py`, `tests/test_docs.py`: the new probe
  row and the documented phrases.

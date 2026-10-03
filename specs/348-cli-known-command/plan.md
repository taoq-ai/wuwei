# Implementation Plan: the plugin's own CLI is a known command

**Branch**: `348-cli-known-command` | **Spec**: `specs/348-cli-known-command/spec.md`

## Summary

Teach the #347 classification one more read-only word: the plugin CLI with a read-only
subcommand. The CLI is recognised by the existing `shell._launcher` (recorded executable or
the running plugin's launcher, by realpath) or as bare `wuwei`; the subcommand is looked up in
one table in `cli/wuwei/commands/__init__.py`. Every guard already routes a relevant call
through `shell.unread`, so the read-only CLI passes there once, for every guard and posture.
Two local fixes follow the same table: the commit/push guard stops calling the recognised
launcher path opaque because it contains a `/`, and the state guard's owner rule lets
`--help` through. The skills name the Read-then-absolute-path form, and the doctor names a
stale recorded executable.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module, no new dependency. Hook latency:
the table lookup is a set scan of about 90 short strings, and `_launcher` (one small file
read) runs only for a command word named `wuwei` that contains a `/`.

## Constitution Check

- I (stdlib): yes. II (three-state exits): guard exits unchanged except the passes named in
  the spec. III/IV: every behaviour has a test task before its implementation task.
- V (ponytail): one shared helper (`known_cli`) wraps the existing `_launcher`; the table is
  data next to the command package; no new guard, no new class.
- VII (security): owner actions keep the host-terminal rule; an unrecognised `bin/wuwei`
  copy stays opaque; `$W` forms stay `unparsed`; unregistered verbs are not read-only
  (spec A3).

## Changes

### 1. `cli/wuwei/commands/__init__.py`: the table (FR-001, FR-002)

Keep the docstring. Add:

```python
# #348: every registered command path is in exactly one set (tests/test_cli_known_command.py).
# A positional named `action` is part of the path (mcp check, calibrate export).
READ_ONLY = frozenset({'board', 'calibrate', 'config check', 'doctor', 'heartbeat',
                       'integrity check', 'mcp check', 'sessions', 'shadow report', 'status',
                       'why'})
# calibrate only prints with --questions; doctor --fix writes (checked below).
_NEEDS = {'calibrate': '--questions'}
WRITES = frozenset({...})  # the 81 other paths, listed below


def read_only(args):
    """#348: True when a CLI call only prints: --help or -h before --, --version first, or a
    READ_ONLY path (the longest registered path the words start with)."""
    args = list(args)
    if '--' in args:
        args = args[:args.index('--')]
    if '-h' in args or '--help' in args or args[:1] == ['--version']:
        return True
    words = [arg for arg in args if not arg.startswith('-')]
    path = max((p for p in READ_ONLY | WRITES if p.split() == words[:len(p.split())]),
               key=lambda p: len(p.split()), default='')
    return path in READ_ONLY and '--fix' not in args and _NEEDS.get(path, '') in ('', *args)
```

The last line may be written plainer (`path not in _NEEDS or _NEEDS[path] in args`); either
is fine. `WRITES` is exactly these 81 paths (enumerated from the registered parsers on main):

`agents build`, `agents check`, `brief`, `build`, `calibrate export`, `calibrate import`,
`close`, `config add-repo`, `config promote`, `config set`, `consolidate`, `dashboard`,
`decision lint`, `decision outcome`, `decision route`, `decision show`, `decision template`,
`discover`, `dispatch discovery`, `dispatch next`, `dispatch opinion`, `dispatch receive`,
`drafts approve`, `drafts drop`, `event`, `fast-checks`, `git-hook`, `goals edit`, `hook`,
`index`, `init`, `integrity reconfirm`, `listen install`, `listen uninstall`, `mcp decide`,
`memory lint`, `merge`, `metrics`, `next`, `note add`, `nudges`, `outbound tier`, `payload`,
`plan add`, `plan approve`, `plan propose`, `plan session`, `plan template`, `pr act`,
`pr claim`, `pr disposition`, `pr ping`, `pr ping-check`, `pr raise`, `pr state`, `promote`,
`rank`, `remote ack`, `reply`, `report`, `retro`, `runtime continue`, `runtime dispatch`,
`runtime result`, `runtime status`, `setup`, `signal classify`, `state get`,
`state recover`, `state set`, `state transition`, `steward ack`, `steward run`,
`sweep obligations`, `sweep watch`, `verdict lint`, `voice edit`, `voice learn`,
`watch install`, `watch uninstall`, `worktree add`.

Why the words rule is safe: the top-level parser has no option before the command except
`--version` and `-h`, so `words[0]` is always the command; the longest match keeps
`calibrate export ... --questions` out (argparse runs the export); an option value that
happens to equal a verb can only make a read-only call look like a write (a false
negative, today's behaviour). Nothing in the CLI uses `argparse.REMAINDER`, so `--help`
before `--` always prints usage and runs nothing.

### 2. `cli/wuwei/shell.py`: recognise the CLI in `classify` (FR-003)

- New helper after `_launcher`:

```python
def known_cli(word, cwd):
    """#348: wuwei on PATH, the running plugin's bin/wuwei or the recorded executable."""
    return word == 'wuwei' or (cwd is not None and '/' in word
                               and PurePosixPath(word).name == 'wuwei'
                               and _launcher(Path(cwd, word), cwd))
```

- `classify(command, publishers=(), cwd=None)` (still `lru_cache`d; `cwd` joins the key) and
  `unread(command, publishers=(), cwd=None)` pass `cwd` to `_classify(command, publishers,
  cwd=None)`. `_classify` passes it to both of its recursive calls (the `sh -c` branch at
  `:862` and the assignment-substitution lambda at `:895`).
- In the per-command loop (`:848`):

```python
        safe = name in READ_ONLY or (literal and known_cli(argv[0], cwd)
                                     and commands.read_only(args))
```

  with `from wuwei import commands` imported lazily inside `_classify` (as `_launcher`
  imports `workspace`). `literal` is the existing "no `$` in args or writes" flag. A redirect
  that writes still makes the call non-read-only through the existing `if writes or not
  safe` branch.

### 3. Guards pass the payload cwd (FR-004, FR-005)

- `cli/wuwei/guards/commit_push.py`: the four `shell.unread(raw, ('rm',))` calls (`:285`,
  `:295`, `:303`, `:348`) add `cwd=payload['cwd']`. In the non-git branch (`:366-371`) the
  path test becomes `('/' in command.argv[0] and not shell.known_cli(command.argv[0],
  directory))`; `is_opaque`, `len(commands) > 1` and the interpreter regex stay.
- `cli/wuwei/guards/pr.py`: `shell.unread(raw)` at `:364` and `:387` add `cwd=cwd` (the
  `_cwd(payload)` value bound at `:348`).
- `cli/wuwei/guards/deploy.py`: `unread(raw, protected[2:])` at `:272` and `:275` add
  `cwd=payload['cwd']`.
- `cli/wuwei/guards/decision.py`: `classify(raw)` at `:68` adds `cwd=cwd`.
- `cli/wuwei/guards/protect_state.py`: `classify(script)` at `:447` adds `cwd=cwd`.

### 4. `cli/wuwei/guards/protect_state.py` (`_owner_action`): `--help` passes (FR-006)

After the "Not a literal owner action" check (`:177-178`) and before the owner reason
(`:179`):

```python
        if read_only(action):  # #348: --help prints usage and runs nothing
            continue
```

with `from wuwei.commands import read_only` added to the function's lazy imports. Only
`--help`/`-h` can reach it for an owner pair (the table test keeps owner pairs in `WRITES`).

### 5. `cli/wuwei/commands/doctor.py` (`_workspace`): the executable row (FR-008)

Right after the `template` row (`:231-238`), before the charter overrides:

```python
    launcher = integrity.PLUGIN / 'bin/wuwei'
    try:
        recorded = (root / '.wuwei/executable').read_text(encoding='utf-8').splitlines()[0]
    except (OSError, UnicodeError, IndexError):
        recorded = ''
    if recorded and Path(recorded).resolve() == launcher.resolve():
        rows.append(_row('workspace', 'executable', 'ok', recorded))
    else:
        rows.append(_row('workspace', 'executable', 'fail',
                         f'{recorded} is missing' if recorded and not Path(recorded).exists()
                         else f'{recorded} is not {launcher}' if recorded
                         else '.wuwei/executable is missing or empty',
                         'wuwei init --upgrade', apply='init-upgrade'))
```

`init-upgrade` is already in `FIXES` (`init.upgrade` rewrites the pointer from the running
plugin, `cli/wuwei/commands/init.py:261-283`). The row sits in the workspace section, so it
appears in the `config does not load` path too.

### 6. Skills, orientation and docs (FR-007, FR-009)

- `skills/wuwei-plan/SKILL.md:8`: replace "Use the executable recorded in `.wuwei/executable`
  for CLI calls." and, in `skills/wuwei-report/SKILL.md`, `skills/wuwei-retro/SKILL.md`,
  `skills/wuwei-consolidate/SKILL.md` line 8, "Run inside a WUWEI workspace using the
  executable recorded in `.wuwei/executable`." with (keeping "Run inside a WUWEI workspace."
  in the last three):

  > For CLI calls, read `.wuwei/executable` once with the Read tool and use the absolute
  > path it holds as the first word of a plain command, for example
  > `/opt/wuwei/bin/wuwei mcp check` when the file holds `/opt/wuwei/bin/wuwei`; never
  > through a shell variable or a command substitution.

  The sentence stays in the paragraph that names `wuwei next` (`tests/test_docs.py:733-735`
  reads that paragraph). No `$(` anywhere in the four files.
- `cli/wuwei/commands/next.py:129-130`: "(wuwei is the executable recorded in
  .wuwei/executable)" becomes "(wuwei is the absolute path in .wuwei/executable: read it
  once and use it as the first word of a plain command, never through a variable)".
- `docs/site/agent.md:20-21`: "`wuwei` means the executable recorded in
  `.wuwei/executable`, or `python3 -P -m wuwei`." becomes "`wuwei` means the absolute path
  in `.wuwei/executable`: read it once with the Read tool and use it as the first word of a
  plain command, never through a variable or a command substitution; or `python3 -P -m
  wuwei`." The page stays under 100 lines.
- `docs/site/security.md:67`: after the read-only program list add "The plugin's own
  read-only subcommands (`status`, `why`, `doctor`, `config check`, `mcp check`, `integrity
  check`, `shadow report`, `board`, `sessions`, `heartbeat`, `calibrate --questions`) and any
  `--help` pass too, through the recorded executable, the plugin's `bin/wuwei` or `wuwei` on
  PATH."

## What must not change

- `_OWNER_ACTIONS`, `_OWNER_VERB`, `_CLI_WORD` and the rest of the owner rule; owner actions
  through the launcher stay refused (`tests/test_launcher_relevance.py`).
- The program set `shell.READ_ONLY`, `shell.mentions`, `shell.normalize`, `is_opaque`.
- `$W` forms (`W=$(cat .wuwei/executable); $W ...`) stay `unparsed` in every guard
  (`tests/test_parser_warns.py` S3, `tests/test_commit_push.py:767`,
  `tests/test_pr_guards.py:737`, `tests/test_deploy.py:508`,
  `tests/test_protect_state.py:748`, `:754`, `tests/test_shell.py:651`, `:710`).
- `init` and `setup` writing `.wuwei/executable`; the doctor `template` row; `doctor --fix`'s
  own host-terminal check.
- A `bin/wuwei` that is neither the running plugin's launcher nor the recorded path is not the
  CLI.

## Tests

- New `tests/test_cli_known_command.py`: the table partition test (registered paths walked
  from the parsers as `__main__` registers them, with the `action` positional expanded), a
  `read_only` table, and the hook acceptance through `wuwei.commands.hook.run` in process
  (fixture as `tests/test_parser_warns.py`, plus a launcher copy under
  `tmp_path/plugin-cache/0.12.0/bin/wuwei` recorded in `.wuwei/executable`).
- `tests/test_doctor.py`: the `ws` fixture writes `.wuwei/executable` with
  `ws.plugin / 'bin/wuwei'`; `test_workspace_rows_healthy` and
  `test_workspace_config_does_not_load` gain `'executable'` after `'template'`; a new
  `test_workspace_executable_pointer`.
- `tests/test_docs.py`: `test_skills_use_the_recorded_executable_directly` and one phrase in
  `test_unparsed_commands_are_documented`; `test_agent_guide_ships_and_is_linked` keeps
  passing.
- `tests/test_next.py`: `test_orientation_block` asserts the new phrase.

## Complexity Tracking

None. `WRITES` is long because the notes ask for a test that every registered command is in
exactly one of two sets; it is data, and it lets `read_only` pick the longest path.

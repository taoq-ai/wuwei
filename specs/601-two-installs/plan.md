# Implementation Plan: Two installs named, traces warns below strict, one credential reader, every backlog discovered

**Branch**: `601-two-installs` | **Date**: 2026-10-10 | **Spec**: `specs/601-two-installs/spec.md`

## Summary

Five small changes at the shared spots the root cause names: the traces guard sends every
failure through its existing tail with a named reason and decides strict itself; helpers
in `integrity.py` give the registered install and the canonical launcher, used by init,
init --upgrade and doctor; doctor gains two rows that appear only on a finding (installs,
credentials); the heartbeat config probe reloads `.wuwei/env`; the GitHub tracker backlog
reads every configured repository and discovery derives `repo` from the candidate id and
takes `--repo`.

## Technical Context

Python 3.11+, stdlib only at runtime, pytest for tests. No new dependency, module, config
key or event kind (`traces.gap` exists and has its producer). Line numbers are main at
0.24.1.

## Constitution Check

- Test first: every behaviour has a test task before its implementation (tasks.md).
- Stdlib only; ports unchanged (the tracker port keeps `backlog(filter, *, root)` and its
  row keys).
- Fail closed: a traces posture read that fails keeps the refusal; a backlog read that
  fails for one repository makes the tracker source unmeasured.
- Principle VII (#530): the change removes a wall below strict and adds none. Principle
  II's "exit 2 blocks" still holds under strict; below strict the warning is the stderr
  reason plus the `traces.gap` record, as #530 amends.
- Workflow: the changed guard rule gets 9.2 row I54 and its check.
- No owner paths or repositories in fixtures.

## Design

### 1. Traces guard (`cli/wuwei/guards/traces.py`, `check`, lines 84-138)

- A local `step` string the try block sets before each read:
  `'the security material (.wuwei/security.json)'` before `security.load` (`:99`),
  `'the tool call for canary and honeytoken findings'` before `security.trace_findings`
  (`:100`), `'the events log (events.jsonl)'` before `security.record` (`:101`),
  `'the tool payload for redaction'` before the agent id and redaction lines (`:102-119`).
- Replace the early `return 2, ...` at `:121-122` with a reason
  `f'wuwei traces: {type(exc).__name__}: could not read {step}'` and a flag that this was
  an inspect failure, then fall through to the existing tail (stderr line, `traces.gap`).
  Never interpolate the exception message (`tests/test_traces.py` bars private details).
- Recording path (`:126-127`): `f'wuwei traces: {type(exc).__name__}: could not record the
  tool span in traces.jsonl'` (keeps the type name the tests assert).
- Mismatch clause, built only on this failure path: when `integrity.recorded(root)` is
  non-empty and does not resolve to `integrity.PLUGIN / 'bin/wuwei'`, append
  `f'; this hook runs {integrity.PLUGIN / "bin/wuwei"} but .wuwei/executable names {recorded}'`.
  Always end the reason with `'; run bin/wuwei doctor, which names the fix'`.
- The return at `:138`: `code = 2` for an inspect failure, else today's
  `2 if security_data is not None else 0`; then `return (code, reason) if code and
  _strict(root) else (0, '')`. Module-level `_strict(root)` returns
  `workspace.posture(workspace.load_config(root))[0] == 'strict'` and True on any
  exception (fail closed, today's refusal).
- Unchanged: the `guard_scope` failure at `:95-96` (exit 2, no root to read a posture
  from; `tests/test_guard_mutation.py` pins it), `AREAS['traces']`, `FLOORS`,
  `hook.posture`, `hook.run`.

### 2. Install helpers (`cli/wuwei/integrity.py`)

```python
def development():
    """A git checkout without a signed manifest: loaded per session with --plugin-dir."""

def recorded(root):
    """The launcher .wuwei/executable names, or '' when missing, empty or unreadable."""

def registered(root=None, config=None):
    """The install Claude Code registered for wuwei: the first wuwei@* entry in the plugins
    file whose installPath has bin/wuwei, or None when the file is missing or lists none.
    Other read or shape errors raise (OSError, ValueError, KeyError, TypeError, AttributeError)."""

def launcher(root=None, config=None):
    """The canonical launcher (#601): this one for a development checkout, else the
    registered install's, else this one; never raises on a broken plugins file."""
```

- The plugins file resolves as doctor does today (`doctor.py:147-150`):
  `(root or Path.cwd()) / Path(name).expanduser()` with `name` from
  `config['scanner']['mcp']['plugins_file']`, else `mcp.DEFAULTS['plugins_file']` (import
  `mcp` inside the function; `mcp` imports `integrity`).
- `development()` is doctor's `_checkout()` body (`doctor.py:88-89`); doctor's `_checkout`
  becomes `_checkout = integrity.development` so the rule lives once.
- `recorded` is the read at `doctor.py:260-263`, moved; doctor's executable row and the
  traces guard call it.

### 3. init (`cli/wuwei/commands/init.py`)

- `create` (`:82`): `executable = integrity.launcher(destination.parent)`.
- `upgrade` (`:381`): `executable = integrity.launcher(destination.parent, <config>)`, where
  `<config>` is the `load_config` result at `:362`, kept in a name instead of loaded twice.
  `pointer_changed` (`:393`), the write (`:408`), the status line (`:452`) and the allow
  rules follow. `plugin` stays the running plugin for templates, charters and agents.

### 4. doctor (`cli/wuwei/commands/doctor.py`)

- `_hooks` (`:138-160`): replace the inline parse at `:147-152` with
  `listed = integrity.registered(root, config) is not None`; the `FileNotFoundError` case
  is the helper's None, and other errors keep the `unmeasured` row.
- New `_installs(root, config)`, appended in `_install` after `_hooks` (`:128`). Collect
  resolved plugin directories with roles: `integrity.PLUGIN` ("this launcher"), the
  registered install ("registered in Claude Code; its hooks run"; skipped when the plugins
  file is broken, the hooks row reports that), and `Path(recorded).resolve().parents[1]`
  when the recorded launcher exists ("named by .wuwei/executable"). Fewer than two distinct
  directories: return `[]`. Otherwise one row
  `_row('install', 'installs', 'warn', '<dir> (<roles>); <dir> (<roles>)',
  f'{canonical} init --upgrade, then remove {others} if you do not use it')` with
  `canonical = integrity.launcher(root, config)`. Absolute paths are not rewritten by
  `_row`'s launcher regex (a `/` precedes `bin/wuwei`).
- Executable row (`:259-271`): `recorded = integrity.recorded(root)`, compared with
  `integrity.launcher(root, config)` instead of `integrity.PLUGIN / 'bin/wuwei'`; messages
  unchanged except that they name the canonical launcher.
- `_day` (`:576`), after the heartbeat row (`:610-611`): when `probes.get('config')` and
  `watch.saved(root).get('heartbeat', {}).get('probes', {}).get('config')` both exist and
  differ, add `_row('day', 'credentials', 'warn', "the watch's last heartbeat read
  <result> <value>; doctor reads <result> <value>", 'the next heartbeat rereads .wuwei/env;
  if this row stays, wuwei watch uninstall, then wuwei watch install')`. A read error of
  the saved beat skips the row (the heartbeat row reports it).

### 5. heartbeat (`cli/wuwei/heartbeat.py`, `_config`, `:80-86`)

Call `env.load(root)` before `missing(...)`; its `ValueError` (unreadable or unsafe
`.wuwei/env`) returns `('failed', str(exc))` like a `ConfigError`.

### 6. GitHub tracker and discovery

- `adapters/tracker/github.py`: `_repos(root)` returns
  `list(dict.fromkeys(name for name in (tracker.project, *(row['name'] for row in
  config['repos'])) if name))`, each checked with `_repo`'s pattern (a `Failure` naming the
  bad one; an empty list keeps `_repo`'s message). `backlog` (`:99-114`) loops over it,
  one query per repository with the existing `hasNextPage` check, and returns the rows of
  all. Row shape unchanged (ids already carry the repository). `_repo` and `create` stay.
- `cli/wuwei/discovery.py` `discover(root=None, *, ports=None, repo=None)` (`:67`): with
  `names` the configured repository names plus a GitHub `tracker.project`, a `repo` not in
  `names` raises
  `ValueError(f'--repo {repo} is not a configured repository; pass one of: {", ".join(names)}')`
  before any read. After `dedupe` (`:211`), each candidate whose id starts with
  `name + '#'` or `name + ':'` for a configured name gets `'repo': name`; with `repo` set,
  keep candidates where `candidate.get('repo', repo) == repo`. One loop; no adapter or
  scanner row change.
- `cli/wuwei/commands/discover.py`: `parser.add_argument('--repo', help='narrow to one
  configured repository (<org>/<name>)')` and `discovery.discover(repo=args.repo)`.

### 7. Lead charter and agents

`charters/lead.md` step 2: replace "Query the tracker backlog, ... through configured
adapters." with "Run `wuwei discover`: it reads every configured repository's tracker
backlog (`--repo <org>/<name>` narrows to one) and the other sources through configured
adapters; each candidate carries the `repo` it came from, keep it in the candidate." Step 4
already asks for `repo`. Bump `version` to 1.5.1, then `bin/wuwei agents build` to
regenerate `agents/lead.md`. `docs/site/configuration.md:467`: one sentence after
"`wuwei discover` reports unavailable sources as `unmeasured`." saying it reads every
configured repository's backlog and `--repo` narrows to one.

### 8. Invariant I54

Design spec 9.2 row after I35 (after I36 if #636 lands first):
`| I54 | Under observe and guarded the traces guard never fails a tool call: an inspection
or recording failure is a warning naming what it could not read, recorded as traces.gap;
strict refuses it | per posture, traces.check on a PostToolUse payload in a workspace with
security required and unreadable security material | #601; the guard decides its own
posture; an unreadable config keeps the refusal |`.

`tests/test_invariants.py`: `i54(case, rules)` with `READS['I54'] = (0,)` and the
`INVARIANTS` key. Its workspace is built once (memo key) beside `rules.root`
(`[security]\nrequired = true` and `.wuwei/security.json` holding `{}`, so
`security.load` raises without a mock); per posture write `posture = "<p>"`, call
`traces.check` once (memo per posture) and expect `(0, '')` below strict and exit 2 naming
`the security material` under strict. No mock, no `main()`, no doctor import in the walk
(the 1.0 s CPU budget, #627). Renumber if another branch takes I54 first.

## What must not change

- `hook.posture`, `hook.run`, `AREAS`, `FLOORS`, `OWNER_ONLY`, `RECORDS_FLOOR`.
- The tracker port signature and row keys, the Linear and Jira adapters, `github.create`,
  `github._repo`.
- `shell._launcher` (it already accepts the recorded executable).
- The exit codes of the hook's own could-not-run paths for PostToolUse and of the traces
  `guard_scope` failure.
- Healthy doctor row lists: the two new rows appear only on a finding.
- `plan.py`'s #603 `repo` handling (it already reads the candidate's `repo`).

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/guards/traces.py` | step label, common tail, `_strict`, mismatch clause |
| `cli/wuwei/integrity.py` | `development`, `recorded`, `registered`, `launcher` |
| `cli/wuwei/commands/init.py` | canonical launcher in create and upgrade |
| `cli/wuwei/commands/doctor.py` | `_checkout` alias, `_hooks`, `_installs`, executable row, credentials row |
| `cli/wuwei/heartbeat.py` | `env.load` in `_config` |
| `adapters/tracker/github.py` | `_repos`, backlog over all |
| `cli/wuwei/discovery.py` | `repo` parameter and candidate `repo` |
| `cli/wuwei/commands/discover.py` | `--repo` |
| `charters/lead.md`, `agents/lead.md` | discover sentence, version, regenerated agent |
| `docs/specs/2026-09-24-wuwei-design.md` | I54 row |
| `docs/site/configuration.md` | one sentence at the `wuwei discover` line |
| tests | `test_traces.py`, `test_invariants.py`, `test_integrity.py`, `test_canary.py` or `test_workspace.py` (init in process), `test_doctor.py`, `test_heartbeat.py`, `test_tracker_adapters.py`, `test_linear_loop.py`, `test_agents.py` |

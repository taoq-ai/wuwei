# Implementation Plan: wuwei doctor

**Branch**: `339-doctor` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

One new command module, `cli/wuwei/commands/doctor.py`, that calls the checks WUWEI already
has, adds the install and host rows nothing measures today, attaches a fix line to every
row, and, with `--fix`, applies the allow-listed fixes through each command's own
confirmation after one batch digest. Everything else is one line in `commands/event.py`,
one call in `commands/setup.py` (#327), docs, and one test file.

No new adapter operation, no new config key, no new state key, no change to any guard or
to `heartbeat.py`.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. The core never imports `subprocess`: every
external tool is reached through an existing adapter (`code_host.auth_status`,
`vcs.identity`, `vcs.branches`, `host.free_memory`, `watch_service.probe`, the integrity
signature adapter). PATH presence uses `shutil.which`.

## Constitution Check

- I stdlib: yes; no new dependency.
- II three-state exits: findings (`warn`, `fail`) exit 1 before unmeasured exits 2, as
  `heartbeat.health` does; a not-applicable row is `ok` with its reason, a row that could
  not measure is `unmeasured`. Exceptions escape to `__main__`, which exits 2 with the
  reason.
- III one behaviour, one function: doctor owns only row building and the fix batch; every
  measurement stays in the function that already makes it.
- IV test first: tasks.md orders each test before its code.
- V ponytail: one module, plain functions, one fix table; previews reuse each command's own
  dry run or confirmation callback instead of a second implementation.
- VII security: `--fix` applies nothing without the typed batch digest at
  `integrity._host_confirm`; each fix is additionally bound to the value its preview
  showed. Decisions (`mcp decide`, posture, `merge.auto`, `shepherd.autostart`, anything
  that writes to the code host) are never applied.

## Reproduction (read-only)

In the trial workspace, the worktree's `bin/wuwei doctor` exits 2 with
`invalid choice: 'doctor'`. The installed v0.11.0 plugin's PreToolUse hook refused a `Read`
in this session with `page: plugin integrity: .in_use/15760; .in_use/16824` (#324, live).
See spec Root cause for file and line.

## Design

### 1. `cli/wuwei/commands/doctor.py` (new)

Module docstring: `"""Owner diagnostic: every problem in the install, host, workspace, gates,
day and guards, with its fix; --fix applies the deterministic ones after one digest."""`

Constants:

```python
SECTIONS = {'install': 'Install', 'host': 'Host', 'workspace': 'Workspace',
            'gates': 'Gates and adapters', 'day': 'Day and sessions', 'guards': 'Guards'}
DOCS = {'install': 'docs/site/recovery.md#integrity-reconfirm',
        'host': 'docs/site/daily.md#1-install-the-signed-release',
        'workspace': 'docs/site/configuration.md',
        'gates': 'docs/site/configuration.md#mcp-registry-checks-s3',
        'day': 'docs/site/reference.md#watch-state',
        'guards': 'docs/site/reference.md#heartbeat'}
CODES = {'ok': 0, 'warn': 1, 'fail': 1, 'unmeasured': 2}
OUTSIDE = "python3 - <<'EOF'\nprint('gh pr list')\nEOF"  # #323: a heredoc that mentions gh
```

`FIXES` (the allow list; a test pins its keys) maps id to `(command, preview, apply)`:

| id | command shown | preview(root) returns (text, token) | apply(root, token) returns exit |
| --- | --- | --- | --- |
| `integrity-reconfirm` | `wuwei integrity reconfirm` | `result = integrity.check(root)`; `None` when `not result.data` (dirty tree), else text naming the fingerprint, token `result.data` | `integrity.reconfirm(root, confirm=lambda value: value == token).exit` |
| `init-upgrade` | `wuwei init --upgrade` | captured `init.upgrade(Namespace(path=str(root), dry_run=True))`, token = that text | rerun the dry run; if it differs from token, return 1 with `changed since the preview`; else `init.upgrade(Namespace(path=str(root), dry_run=False))` |
| `config-promote` | `wuwei config promote` | captured `config.promote(Namespace(), confirm=lambda digest, **_: seen.append(digest))` (promote passes `prompt=`; the callback returns None, so promote declines and writes nothing); text = captured stdout, token = `seen[0]`; `None` when promote returned before asking (no repositories, unreadable files) | `config.promote(Namespace(), confirm=lambda digest, **_: digest == token)` |
| `calibrate` | `wuwei calibrate` | fixed text `profile the configured repositories; writes today's calibration.md and charter proposals; config.toml unchanged`, token None | `calibrate.run(Namespace(action=None, target=None, repo=None, skip=[], interview=None, questions=False, answer=None))` (the `commands.calibrate` module) |
| `watch-install` | `wuwei watch install` | captured `watch.service(Namespace(watch_action='install', once=False, dry_run=True), 'watch', None)` (the `commands.watch` module; the loop argument is unused for install) | dry-run compare as `init-upgrade`, then the same call with `dry_run=False` |
| `listen-install` | `wuwei listen install` | as `watch-install` with `listen_action`, name `'listen'` | as `watch-install` |
| `config-set` | `wuwei config set <key> <value>` (#327) | #327's proposal function for the key and value the row carries, with its confirm callback declining to reveal the digest | the same function with `confirm=lambda digest: digest == token` |

`config-set` exists only if #327 shipped a callable `config set` path with a `confirm`
parameter (the `config promote` digest pattern its issue names). If not, leave the id out
of `FIXES`, keep those rows as printed fixes, and list it under Deferred.

Helpers (each a few lines):

- `_row(section, name, status, value, fix='', apply=None, detail=(), docs=None)` returns
  the row dict; `fix`, `apply` and `docs` (default `DOCS[section]`) are kept only when
  `status != 'ok'`; `detail` only when non-empty.
- `_capture(function, *args, **kwargs)` runs it under `contextlib.redirect_stdout` and
  `redirect_stderr` into one `io.StringIO` and returns `(code, text)`.
- `outcome(rows)`: `1` if any `warn`/`fail`, else `2` if any `unmeasured`, else `0`.
- `render(rows)`: per section a header line (`SECTIONS[...]`), then
  `  <status:<10><name>: <value>`, then for non-ok rows `      fix: <fix>` and
  `      docs: <docs>`, then each `detail` line indented. Last line:
  `doctor: <n> fail, <n> warn, <n> unmeasured` or `doctor: ok`.

`diagnose()` (no arguments; finds the workspace like every command) returns the rows:

1. `root = workspace.find_workspace()`; `FileNotFoundError` makes `root = None`; a
   `ValueError` (symlinked `.wuwei`) is a `fail` workspace row and `root = None`.
2. When `root`: `config = workspace.load_config(root)`; `ConfigError` keeps
   `error = str(exc)` and `config = None`. Defaults for the host rows when there is no
   config: `workspace._validate({}, workspace.SCHEMA, (), '')`.
3. When `root`: `probes = heartbeat.measure(root)` once (it never raises; its rows carry
   `unmeasured` on failure).
4. Rows: `_install(root)`, `_host(root, config or defaults)`,
   `_workspace(root, config, error)`, then when `config` loaded `_gates(root, config)` and
   `_day(root, config, probes)`, else one `unmeasured` row each for gates and day
   (`config.toml does not load`); `_guards(root, probes)`.

Section functions. Every fix line below is exact; `<i>` is the repository index, `<name>`
its `name`.

`_install(root)`:
- `plugin`: `ok`, `<integrity.PLUGIN> <version from .claude-plugin/plugin.json>`
  (`signed release` when `MANIFEST.sha256.sig` exists, `development checkout` when `.git`
  exists, else `fail` `neither a signed release nor a checkout`, fix
  `reinstall the signed release`).
- `integrity`: with `root`, `integrity.fresh(root)` (the heartbeat probe's function, read
  only); without, `integrity.measure()` for a signed release, and `ok` `development
  checkout; confirmed per workspace` for a checkout. Exit 0 `ok`; exit 1 or 2 `fail` with
  the reason, fix `wuwei integrity reconfirm`, and `apply='integrity-reconfirm'` only for a
  development checkout with a workspace. A release finding prints
  `review the files named, then wuwei integrity reconfirm; or reinstall the signed release`
  (a decision, not applied). A reason containing `run wuwei integrity check` is
  `unmeasured` with fix `wuwei integrity check`.
- `in_use`: `ok`, `<n> Claude Code process markers (expected)` counting entries of
  `PLUGIN/.in_use` (`0` when absent). Never a finding.
- `hooks`: `hooks/hooks.json` parses and has `hooks.PreToolUse`, else `fail` fix
  `reinstall the signed release`. Then the installed plugins file (the config's
  `scanner.mcp.plugins_file`, else `mcp.DEFAULTS['plugins_file']`, expanded as
  `mcp.discover` does) lists an entry whose `installPath` resolves to `PLUGIN`: `ok`
  `registered in Claude Code`; not listed and a checkout: `ok`
  `development checkout (loaded per session with --plugin-dir)`; not listed and a release:
  `fail` fix `/plugin install wuwei@wuwei in Claude Code`; file unreadable: `unmeasured`.
- `launcher`: `os.access(PLUGIN / 'bin/wuwei', os.X_OK)`, else `fail` fix
  `chmod +x <path>`.
- `python`: `sys.version_info >= (3, 11)`, else `fail` fix `install Python 3.11 or newer`.

`_host(root, config)`:
- `gh`: `adapters.code_host != 'github'` is `ok` `not used`. Else `shutil.which('gh')`
  missing: `fail` fix `install the GitHub CLI, then gh auth login`; then
  `registry.load('code_host', config).auth_status()`: 0 `ok` `authenticated`, 1 `fail`
  fix `gh auth login`, 2 `unmeasured` with its reason.
- `git identity`: `registry.load('vcs', config).identity(str(root / '.wuwei' if root else Path.cwd()))`;
  exit 0 `ok` `<name> <email>`; else `fail` fix
  `git config --global user.name "<name>" and git config --global user.email "<email>"`.
- `ziran`: only when `adapters.scanner == 'ziran'` (else `ok` `not used`):
  `shutil.which('ziran')` present `ok` `on PATH (version checked by every call, minimum
  0.39.0)`, else `fail` fix `install ZIRAN 0.39.0 or newer`.
- `claude`: `shutil.which('claude')`; absent and `adapters.inbound != 'none'`: `fail` fix
  `install the Claude Code CLI (the listener starts headless sessions with it)`; absent
  otherwise: `ok` `not on PATH; only the listener needs it`.
- `codex`: needed when `adapters.runtime == 'codex'` or `gates.second_opinion` starts with
  `codex:`; absent and needed: `fail` fix `install the Codex CLI`; otherwise `ok` with the
  path or `not used`.
- `memory`: `adapters.host == 'none'` is `unmeasured` `adapters.host = "none"` (fix
  `set adapters.host = "local"`); else `registry.load('host', config).free_memory()`:
  below `host.free_memory_mb` MiB `fail` fix
  `free memory, or lower host.free_memory_mb in .wuwei/config.toml`; exit 2 `unmeasured`.
- `service manager`: `shutil.which('launchctl' if sys.platform == 'darwin' else
  'systemctl')`; absent `fail` fix `the watch and listener need launchd (macOS) or
  systemd --user (Linux)`.

`_workspace(root, config, error)`:
- No root: one `fail` row `workspace`: `no .wuwei/ found from <cwd>`, fix
  `wuwei setup --shadow in the directory that holds your repositories`. Return.
- `workspace`: `ok` `<root>/.wuwei`.
- `config`: `ok` `loads`, or `fail` with `error`; fix `wuwei init --upgrade` and
  `apply='init-upgrade'` when `error` contains `delete that line before using [[repos]]
  tables` (the #326 hint), else fix `edit .wuwei/config.toml: <error>`.
- `template`: `_capture(init.upgrade, Namespace(path=str(root), dry_run=True))`. Exit 0:
  lines starting `Would upgrade` make one `warn` row `<n> changes` with the lines as
  detail, fix `wuwei init --upgrade`, `apply='init-upgrade'`; lines starting
  `Charter override needs review` make one `warn` row `charter overrides` with them as
  detail, fix `update each override's version line after reviewing the plugin charter`,
  docs `docs/site/charter-overrides.md`; otherwise `ok` `current`. Exit 1 or 2:
  `unmeasured` with the captured text as detail.
- When `config` is `None`, stop here.
- Per repository `<name>`, rows named `<name> path`, `<name> git`, `<name> branch`,
  `<name> identity`, `<name> fast_checks`; `path = (root / Path(repo['path']).expanduser()).resolve()`:
  - path: `is_dir()` else `fail` fix `edit repos.<i>.path in .wuwei/config.toml`.
  - git: `(path / '.git').exists()` else `fail` fix
    `clone the repository at <path>, or fix repos.<i>.path`. Skip the next two rows when
    path or git failed.
  - branch: `registry.load('vcs', config).branches(str(path), branch)` lists it: `ok`;
    else `fail` fix `git -C <path> fetch origin <branch>:<branch>` (touches the code host,
    printed only).
  - identity: config `identity.name` and `identity.email` set: `ok`; else
    `vcs.identity(str(path))` resolves: `warn` `empty; the repository resolves <name>
    <email>`, fix `wuwei config set repos.<i>.identity.name "<name>"` and the same for
    email, `apply='config-set'` (when present); else `fail` fix
    `set repos.<i>.identity in .wuwei/config.toml`.
  - fast_checks: any non-empty entry `ok` (the list joined); else `warn` `empty`, fix
    `wuwei config promote (fills it from the calibration; read wuwei calibrate's report
    first)`, `apply='config-promote'`.
- `calibration`: `.wuwei/calibration.json` absent: `warn` `never applied`, fix
  `wuwei calibrate, then wuwei config promote`; present: `ok` with each repository's
  `date`; unreadable: `unmeasured`.
- `drift`: today's `calibration.drift` events (`watch.records(workspace.day_dir(root) /
  'events.jsonl')`): none `ok`; else `warn` naming the repositories, fix `wuwei calibrate`,
  `apply='calibrate'`.
- `interview`: `ok`, `<n> answers today` or `none today (wuwei calibrate --interview asks
  again)` from `interview.load(root, config)`.
- `profile`: `ok`, `guards profile <config['profile']>; calibration profile <name or none>`
  from `profiles.load(root, config)`.
- `shadow`: enforce: `ok` `enforce`. Shadow: days since `guards.shadow_since`, left =
  `guards.shadow_days - days`; left > 0 `ok` `shadow, <left> days left`; else `warn` with
  `status.SHADOW_NUDGE.format(days=days)` as the value, fix
  `set guards.mode = "enforce" in .wuwei/config.toml, or raise guards.shadow_days` (a
  decision, printed only).

`_gates(root, config)`:
- `config check`: `code, text = _capture(config_command.run, Namespace())` (the
  `commands.config` module); `ok` / `fail` / `unmeasured` for 0 / 1 / 2, value
  `exit <code>`, detail = the non-empty lines, fix
  `apply the fix each detail line names`, docs `docs/site/configuration.md`.
- `mcp gate`: `mcp.cached(root)`: 0 `ok` (its reason or `clean`); 1 `fail` with the reason,
  fix `review the decision named, set Outcome: proceed, then wuwei mcp decide`; 2
  `unmeasured` with the reason, fix `wuwei mcp check`.
- Per server from `record = mcp._read(root)` when its `day` is today:
  - each `[name, digest]` in `record['unmeasured']`: `warn` `<name>: unmeasured`, fix
    `wuwei mcp decide proceed-unmeasured <name> (or fix the server, then wuwei mcp check)`;
  - each in `record['decided']`: `ok` `proceeding unmeasured by owner decision`;
  - each `'; '`-separated note in `record['reason']` ending `: not attached (unapproved)`:
    `ok` with that note.
  An unreadable record is one `unmeasured` row with the error.

`_day(root, config, probes)`:
- `state`: from `probes['state']` (`failed` is `fail`, fix
  `wuwei state recover in a host terminal`).
- `planner`: from `probes['planner']` (`failed` fix
  `wuwei plan session <session id> --take-over from the live session`).
- `rows, watch_health, listen_health, beat, _ = status.scan(workspace.day_dir(root))`; an
  exception is one `unmeasured` row `day` with the error and the section stops.
- `watch`: `alive` `ok`; `off` `warn` `not installed`, fix `wuwei watch install`,
  `apply='watch-install'`; `dead` `fail`, fix
  `wuwei watch uninstall, then wuwei watch install (read .wuwei/watch.stderr.log first)`;
  `unmeasured` `unmeasured`.
- `listener`: `adapters.inbound == 'none'` is `ok` `not used`; otherwise as `watch` with
  `listen` and `apply='listen-install'`.
- `heartbeat`: `None` `ok` `none today`; `ok` `ok`; `degraded` `fail` fix
  `wuwei heartbeat names the failed probe`; `unmeasured` `unmeasured`.
- one `fail` row per scan row with `tier == 'page'`: name = its `source`, value = its
  `reason`, fix `wuwei nudges`.
- `nudges`: `ok`, `<n> open (wuwei nudges lists them)`.

`_guards(root, probes)`:
- With `root`: rows `refused`, `allowed`, `state_write`, `status_line` from `probes`
  (`ok`, `failed` is `fail`, `unmeasured`); fix for `fail`:
  `the hook no longer behaves as shipped; run wuwei integrity check and reinstall the
  signed release`.
- Always: `outside workspace`: in a `tempfile.TemporaryDirectory()`,
  `(result,), _ = registry.watch_service().probe([(('hook', 'PreToolUse'), payload)], outside)`
  with `payload = json.dumps({'session_id': HEARTBEAT_SESSION, 'transcript_path':
  os.devnull, 'cwd': outside, 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
  'tool_input': {'command': OUTSIDE}})`. Exit 0 `ok`; another exit `fail` with the first
  stderr line, fix `upgrade WUWEI: outside a workspace every hook must allow (#323)`;
  `None` (timeout) or `OSError`/`ValueError` `unmeasured`.

`fix(rows, confirm)`:
1. `root = workspace.find_workspace()`.
2. `wanted = dict.fromkeys(row['apply'] for row in rows if row.get('apply'))`; ids not in
   `FIXES` and every non-ok row without `apply` go to the `Not applied` list with their
   fix.
3. Preview each id in `FIXES` order; a preview returning `None` or raising `OSError` or
   `ValueError` moves to `Not applied` with `cannot be applied now: <reason>`.
4. Nothing to apply: print the `Not applied` list and `Nothing to apply` and return
   `outcome(rows)`.
5. Batch text: for each fix `[<id>] <command>` then its preview text; then the
   `Not applied` list. Print it. `digest = hashlib.sha256(text.encode()).hexdigest()[:12]`.
6. `confirm = confirm or (lambda value: integrity._host_confirm(value, prompt='Review the
   fixes above. To apply them all, type:'))`. `OSError`: print the reason
   (`integrity.HOST_TERMINAL`) to stderr, return 2. False: print
   `wuwei doctor: declined; nothing applied` to stderr, return 1.
7. For each fix: `code = apply(root, token)`, where `OSError` or `ValueError` is exit 2
   with its message printed; print `<id>: exit <code>`;
   `state.append_event('doctor.fixed', {'fix': id, 'exit': code}, root)`. One failed fix
   never stops the others.
8. `rows = diagnose()`; print `render(rows)`; return `outcome(rows)`.

`register(subparsers)`: parser `doctor`, help `Find install, host, workspace and guard
problems and their fixes`; mutually exclusive `--fix` (`apply the allow-listed fixes after
one host confirmation`) and `--json`; argparse's exclusive group gives the exit 2 usage
error for `--fix --json`.

`run(args, confirm=None)`: `rows = diagnose()`; `--json` prints
`json.dumps({'exit': outcome(rows), 'rows': rows})`; otherwise `print(render(rows))`; then
`return fix(rows, confirm) if args.fix else outcome(rows)`.

Imports stay inside functions where a module is heavy or only one section uses it
(`init`, `commands.calibrate`, `commands.config`, `commands.watch`, `interview`,
`profiles`, `mcp`, `status`), the pattern `config.promote` and `heartbeat` already use.

### 2. `cli/wuwei/commands/event.py`

Add `'doctor.fixed': 'owner host wuwei doctor --fix'` to `EVENT_PRODUCERS`.

### 3. `cli/wuwei/commands/setup.py` (#327, only if present on main)

Last step of setup's run: `print(doctor.render(doctor.diagnose()))` (no `--fix`, setup
already confirmed its own proposal). Setup's exit stays its own.

### 4. Docs

- `docs/site/reference.md`: Commands row
  `| \`bin/wuwei doctor\` | Finds install, host, workspace, gate, day and guard problems and prints each fix; \`--fix\` applies the allow-listed ones after one host confirmation. | [Doctor](#doctor) |`
  (alphabetical, after `discover`/`dispatch`, before `drafts`), and a `## Doctor` section
  after `## Heartbeat`: the six sections, the four statuses, the exit rule, the fix allow
  list table (id, command, when), that decisions stay printed, that `--fix` asks for one
  digest on `/dev/tty` and exits 2 without a terminal, the `doctor.fixed` event, and
  `--json`.
- `docs/site/recovery.md`: after the intro paragraph: `Start with \`bin/wuwei doctor\`: it
  names each problem with its fix, and \`bin/wuwei doctor --fix\` applies the
  deterministic ones after one confirmation. See [doctor](reference.html#doctor).`
- `docs/site/daily.md` section 2: after the `config check` sentence: `Then run
  \`bin/wuwei doctor\`; it checks the install, host, workspace, gates and guards in one
  pass and prints the fix for anything that is not ok.`

## What must not change

- `heartbeat.py` and its probe table, the watch tick, and `wuwei heartbeat` output.
- Every guard module, `commands/hook.py` and `guards/protect_state.py` (no new owner-action
  entry; see spec Assumptions). Doctor is imported by no hook path.
- `config check`, `integrity`, `mcp`, `init`, `calibrate` and `watch` behaviour and output.
  Doctor calls them; it does not alter them.
- No adapter gains an operation; `registry.PARAMETERS` is unchanged.
- Doctor without `--fix` writes no workspace file and appends no event.

## Project Structure

```
cli/wuwei/commands/doctor.py      new: rows, render, outcome, diagnose, FIXES, fix, run
cli/wuwei/commands/event.py       doctor.fixed producer
cli/wuwei/commands/setup.py       last step prints the doctor report (#327, if present)
docs/site/reference.md            Commands row, Doctor section
docs/site/recovery.md             point to doctor first
docs/site/daily.md                run doctor after configuring
tests/test_doctor.py              new
tests/test_docs.py                doctor named in recovery, daily and the reference
```

## Test approach

In process through `wuwei.__main__.main(['doctor', ...])` with `capsys`, like
`tests/test_env_credentials.py`. Fixture `ws` (in `tests/test_doctor.py`): a workspace
under `tmp_path` with `WUWEI_WORKSPACE` and `WUWEI_NOW` set, `fakes.integrity.seed`, a fake
`integrity.PLUGIN` directory, `heartbeat.measure` replaced by a dict of ok probes,
`registry.watch_service` replaced by the `Service` fake pattern of
`tests/test_heartbeat.py` (the outside probe), `registry.load` returning `fakes.host.Fake`
for `host`, `fakes.code_host.Fake` for `code_host` (auth and protection results), and a
small vcs stub for `identity` and `branches`; a `bin/` directory on `PATH` with empty
executable stubs for `gh`, `launchctl`, `systemctl` and `ziran`. No network, no real
`gh`, no real ZIRAN, no real launcher (one test may keep the real outside probe through
`bin/wuwei` as the smoke for #323 if #323 is on main).

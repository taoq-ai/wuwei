# Implementation Plan: wuwei setup, one command with one confirmation

**Branch**: `327-setup` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

`setup` is orchestration over code that exists: `init`, `calibrate.survey`, the interview,
profiles, the `config promote` proposal and digest, `config check` and `mcp check`. New code
is one discovery function, one text function for `[[repos]]` tables, the two config
commands, two port reads and three owner-table rows.

Shared spots, one change each:

1. `cli/wuwei/commands/config.py`: split `promote` (lines 114-171) into three helpers that
   `promote`, `config set`, `config add-repo` and `setup` all call: `read` (path checks and
   the raw text), `proposal` (the calibration summary, now over a staged base text) and
   `offer` (the digest path). `promote` keeps its behaviour and output byte for byte.
2. `cli/wuwei/commands/setup.py` (new, the one module): `register`, `discover`,
   `repo_tables`, `set_value`, `add_repo`, `run`. `config.py` registers `set` and `add-repo`
   with `setup.set_value` and `setup.add_repo` as their functions.
3. `cli/wuwei/commands/calibrate.py`: extract the report and charter-proposal writing of
   `run` (lines 57-72) into `record(root, results, diff, edits, error)` so `setup` writes the
   same `calibration.md` and proposals.
4. Ports: code_host `default_branch(repo)`, vcs `remote_url(repo)`.
5. `cli/wuwei/guards/protect_state.py`: three owner-table rows and a group-wide match.

## Technical Context

Python 3.11+ stdlib only (`tomllib`, `difflib`, `hashlib`, `shutil.which`, `re`, `json`);
pytest for tests. No new state key, no new event kind, no new dependency. The core still
never imports `subprocess`: `shutil.which` only reads PATH.

## Constitution Check

- I stdlib: yes.
- II fail closed: every refusal before the confirmation is exit 1 with the reason; no host
  terminal, an unreadable file, a symlink or a file changed during the confirmation is exit
  2 with nothing written; an unmeasured default branch is never guessed (the repository is
  owed); `config check` and `mcp check` keep their exits and `setup` returns the larger.
- III one behaviour, one function: the digest path lives in `config.offer`; the TOML
  placement stays in `calibrate.settle` and `calibrate.apply`; table text in
  `setup.repo_tables`; discovery in `setup.discover`.
- IV test first: tasks.md orders each test before its code.
- V ponytail: no new placement engine (reuse `settle`/`apply`); no default-branch fallback
  from local refs; adapter proposals limited to `scanner`; no new config keys.
- VII security: the three commands are owner actions in the #222 table; discovered text is
  written only through `json.dumps` after validation; instruction-like identity text is
  dropped (#278); `--posture` refuses URLs, so discovery makes no network call beyond `gh`.

## Design

### 1. Shared helpers: `cli/wuwei/commands/config.py`

Move code out of `promote` without changing what it prints or writes.

- `read(root)` returns `(path, raw)`: the two symlink checks of lines 120-121 and the
  `read_text` of line 122.
- `proposal(root, raw, base, config, results, extra=())` returns
  `(text, diff, edits, summary, snapshot)`: lines 130-151 of `promote`, with three changes:
  - `calibrate.propose(base, results, settings)` where `settings` is
    `[s for s in extra if s[:2] not in owner_keys] + imported + asked` and `owner_keys` is the
    `(path, key)` set of `imported + asked` (an interview answer or a profile key wins over a
    setup default, as the interview already wins over the profile);
  - the diff is `difflib.unified_diff(raw, text, 'config.toml', 'config.toml (proposed)')`,
    from the file on disk, not from `base` (for `promote`, `raw == base`, so the output is
    unchanged);
  - `results` and `config` come from the caller.
- `offer(root, raw, text, summary, *, label, what, confirm=None, snapshot=None)`:
  lines 152-165. Print `summary`; `digest = sha256(summary)[:12]`;
  `(confirm or integrity._host_confirm)(digest, prompt=f'Review the {what} above. To apply it, type:')`;
  declined prints `wuwei {label}: declined; nothing written` to stderr and returns
  `FINDINGS`; re-read and compare with `raw` (raise `ValueError` as now); write `text` when
  it differs; write `snapshot` to `.wuwei/calibration.json` when given; print
  `Applied the {what}` plus ` and recorded .wuwei/calibration.json` when a snapshot was
  written (so `promote`, with `label='config promote'`, `what='calibration'`, prints exactly
  what it prints today); return `CLEAN`. Labels: `config promote`, `config set`,
  `config add-repo`, `setup`; `what`: `calibration`, `change`, `repository`, `setup`.
- `promote(args, confirm=None)` becomes: `root`, `read`, `load_config`, `NO_REPOS` check,
  `survey(style=False, measure=...)`, `proposal(root, raw, raw, config, results)`, `offer`.
  Its `except` clauses stay.
- `register`: add
  - `set` with positionals `key`, `value`, help `set one config value (owner, host terminal)`,
    `func=setup.set_value`;
  - `add-repo` with required `--name`, `--path`, `--branch` and optional `--identity`
    (`"Name <email>"`), help `add one repository (owner, host terminal)`,
    `func=setup.add_repo`.
  Import `setup` inside `register` (setup imports config at module level).

### 2. `cli/wuwei/commands/setup.py` (new)

Module docstring: `One-shot workspace setup and the owner config edits.`

Constants:

```python
GITHUB = re.compile(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)'
                    r'([^/\s]+/[^/\s]+?)(?:\.git)?/?')
IDENTITY = re.compile(r'(.+?) <([^<>\s]+@[^<>\s]+)>')
KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*(?:\.(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+))*')
TOOLS = ('claude', 'gh', 'ziran')
```

`repo_tables(raw, repos)` returns `raw` (ending in a newline) plus, per repo dict, a block:

```
\n[[repos]]\nname = <json>\npath = <json>\ndefault_branch = <json>\n
identity = {name = <json>, email = <json>}\n   (only when the repo has an identity)
```

Values go through `json.dumps` (the same escaping `calibrate.apply` uses). Appending at the
end is valid TOML after any table; the caller validates with `load_config(root, raw=text)`.

`set_value(args, confirm=None)`:

1. `root = workspace.find_workspace()`, `path, raw = config.read(root)`,
   `workspace.load_config(root, raw=raw)` (a broken file is exit 1 with its reason).
2. `KEY.fullmatch(args.key)` else `ValueError('<key>: expected a dotted key such as owner.name or repos.0.merge_deploys')`.
   Digit parts become `int`; `path, key = tuple(parts[:-1]), parts[-1]`; the last part must
   not be a digit.
3. `parsed = tomllib.loads(f'value = {args.value}\n')`; refuse unless `list(parsed) == ['value']`
   (`expected one TOML value`).
4. `additions, edits = calibrate.settle(raw, [(path, key, value)])`. An edit is refused:
   when the current value is a table, `<dotted>: a table; set one of its keys, for example <dotted>.default`
   for `owner.verbosity` (generic: `<dotted>: a table; set one of its keys`), else
   `<dotted>: not a one-line assignment; edit config.toml by hand`. No additions: print
   `No config.toml changes`, return `CLEAN` (no confirmation).
5. `text = calibrate.apply(raw, additions)` (it already runs the schema check and the
   value-preservation proof), then `workspace.load_config(root, raw=text)` for the
   cross-field checks.
6. `return config.offer(root, raw, text, diff, label='config set', what='change', confirm=confirm)`
   with the unified diff (`config.toml` to `config.toml (proposed)`) as the summary.

Exits: `ConfigError` and any `ValueError` (including `tomllib.TOMLDecodeError` and
`calibrate.LAYOUT`) before the offer are `FINDINGS` printed as `wuwei config set: <reason>`;
`OSError` (no terminal, unreadable file) is `UNRUN`.

`add_repo(args, confirm=None)`: same frame. Validate `--name` with
`references.repository`, `--identity` with `IDENTITY.fullmatch` (else
`--identity: expected "Name <email>"`), then `text = repo_tables(raw, [repo])`,
`load_config(root, raw=text)` (duplicate name or path is its existing `ConfigError`), then
`offer(..., label='config add-repo', what='repository')`.

`discover(root, dirs, config)` returns
`{'repos': [...], 'lines': [...], 'owed': [...], 'tools': {name: bool}}`:

- Host lines: `Host: <sys.platform>`, one `<tool>: on PATH|missing` per `TOOLS` via
  `shutil.which`, `code host auth: set|missing|unmeasured` from `code_host.auth_status()`
  (exit 0, 1, 2; a missing `gh` is already exit 2 in the adapter), `free memory: <n> MiB|unmeasured`
  from `host.free_memory()` (bytes divided by 1048576).
- Candidates: `root` itself when `root/.git` exists, then for each `dir` in `dirs` the sorted
  direct children that are directories, not symlinks, not dot-named, with a `.git` entry.
  Deduplicate by resolved path. A `.git` that is a file is a linked worktree: line
  `<rel>: worktree, not added`, no repo.
- Skip a candidate whose resolved path or parsed name matches a configured repository
  (idempotency).
- Per repository: `vcs.remote_url(path)` -> `GITHUB.fullmatch(url)` ->
  `references.repository(name)`; else owed. Default branch: `code_host.default_branch(name)`
  when auth is set; exit 0 gives `data['branch']`, anything else is owed. Identity:
  `vcs.identity(path)`; exit 0 gives `{'name', 'email'}`; when
  `calibrate.instruction_like(name + ' ' + email)` hits, drop it and add the line
  `<rel>: identity flagged (<rule>), not proposed`.
- `path` in the table: `os.path.relpath(resolved, root)` when inside `root`, else the
  resolved absolute path (an owner-local value in the owner's own config, never in the
  repository).
- Owed line for a repository not proposed:
  `bin/wuwei config add-repo --name <name or owner/repo> --path <path> --branch <branch or default branch>`
  with what was measured filled in and `shlex.quote` on each value.

`run(args, confirm=None)` (the `setup` command):

1. `if not sys.stdin.isatty(): raise OSError(integrity.HOST_TERMINAL)` (the interview and the
   digest both need the terminal; nothing is written yet).
2. Workspace: `find_workspace()`; on `FileNotFoundError` call
   `init.run(SimpleNamespace(path='.', shadow=args.shadow, upgrade=False, dry_run=False, menu_bar=False, honeytoken_path=security.DEFAULT_HONEYTOKEN_PATH))`,
   then `find_workspace()` again. Init's own exit is not used (its MCP line is repeated by
   step 9); an exception from it ends setup with exit 2. Without `--shadow`, print one line
   suggesting `bin/wuwei setup --shadow` for a first week (only when init ran).
3. `path, raw = config.read(root)`; `cfg = load_config(root, raw=raw)`;
   `found = discover(root, args.repos or [root], cfg)`; print `found['lines']` now, before
   the interview; `staged = repo_tables(raw, found['repos'])`;
   `staged_cfg = load_config(root, raw=staged)`.
   No repositories in `staged_cfg`: print the owed commands, return `FINDINGS`.
4. Extra settings: `(('adapters',), 'scanner', 'ziran')` when `found['tools']['ziran']` and
   `cfg['adapters']['scanner'] == 'none'`; with `--shadow` and `cfg['guards']['mode'] != 'shadow'`,
   `(('guards',), 'mode', 'shadow')` and `(('guards',), 'shadow_since', today)`.
5. `--posture`: refuse a value with a URL scheme (`--posture: a starter name or a local file; use calibrate import for a URL`);
   `profiles.read`, `profiles.review(profile, staged_cfg, names)`; refused rows print and
   return `FINDINGS`; `profiles.record(root, accepted, names)` (the day's `profile.json`,
   read back by `proposal` through `profiles.load`).
6. Interview when `found['repos']` is non-empty or `.wuwei/calibration.json` is absent:
   `interview.record(root, staged_cfg, interview.ask([], names))`. `EOFError` is exit 2,
   `interview interrupted; nothing written` (as `calibrate --interview`).
7. `results = calibrate.survey(root, staged_cfg, list(enumerate(staged_cfg['repos'])), style=True)`;
   `text, diff, edits, summary, snapshot = config.proposal(root, raw, staged, staged_cfg, results, extra)`.
8. Nothing new (`text == raw` and `calibration.json` exists): print `Nothing to propose`.
   Otherwise `code = config.offer(root, raw, text, summary, label='setup', what='setup',
   confirm=confirm, snapshot=snapshot)`; declined returns `FINDINGS`. After an applied offer,
   `calibrate_command.record(root, results, diff, edits, None)` writes `calibration.md` and
   the charter proposals (only now, so a second run never re-proposes a landed block).
9. Checks: `check = config.run(SimpleNamespace())`; `gate = mcp.check(root)`, print its
   reason to stderr as `commands/mcp.py` does.
10. Owed, one line each, printed under `Still owed:`: the discovery owed commands;
    `config.missing(load_config(root))` names as `set <NAME> in .wuwei/env`;
    `bin/wuwei config set owner.name '"<your name>"'` when `owner.name` is empty;
    `bin/wuwei promote` when today's `proposals/` has files; MCP:
    `bin/wuwei mcp decide proceed-unmeasured <server>...` for `mcp.unmeasured(root)` when the
    check exited 2, `bin/wuwei mcp decide` when it exited 1. Then `Next: /wuwei plan`.
11. Return `max(check, gate.exit)`.

Exceptions as in `promote`: `ConfigError` is `FINDINGS`; `OSError`, `ValueError`,
`UnicodeError` are `UNRUN` with `wuwei setup: <reason>`.

`register(subparsers)`: `setup` with `--shadow`, `--posture PROFILE`,
`--repos DIR [DIR ...]` (`nargs='+'`), help
`discover repositories, write config, calibrate and interview, apply once (owner, host terminal)`.

### 3. `cli/wuwei/commands/calibrate.py`

`record(root, results, diff, edits, error)` holds lines 57-72 of `run` (charter proposal files
and `calibration.md`) and returns `(evidence, written)`. `run` calls it; its prints stay.

### 4. Ports

- `cli/wuwei/registry.py`: `'default_branch': ('repo',)` under `code_host`,
  `'remote_url': ('repo',)` under `vcs`.
- `adapters/code_host/github.py`: `default_branch(repo)` decorated with `_operation`, returns
  `{'branch': b}` from `_api(f'repos/{_repo(repo)}')['default_branch']`, refusing a value
  that is not a non-empty string matching `[A-Za-z0-9._/-]+` or starts with `-`. In `_run`,
  allow a GET of exactly `repos/<owner>/<name>` with the no-cache header (today the pattern at
  line 73 needs a trailing path); POST still needs one of the listed sub-paths.
- `adapters/code_host/none.py`: `default_branch` returns
  `record_none('code_host', 'default_branch', root, measurement=True)`.
- `adapters/vcs/git.py`: allowlist `('config', '--get', 'remote.origin.url')`; `remote_url(repo)`
  returns `{'url': _run(repo, 'config', '--get', 'remote.origin.url', missing=True).strip()}`
  (empty when unset).
- `tests/fakes/code_host.py` and `tests/fakes/vcs.py`: one recorder method each.
- `tests/fixtures/code_host/recordings.json`: one `default_branch` recording.

### 5. Owner-action table: `cli/wuwei/guards/protect_state.py`

- Rows: `('config', 'set')`, `('config', 'add-repo')` with
  `Config edits are an owner action on the host, outside agent tools.`, and `('setup', '')`
  with `Setup writes config.toml; it is an owner action on the host, outside agent tools.`
  An empty verb means the whole group, because `setup` flags take values and `_pair` would
  read a flag value as the verb.
- One lookup, used at line 150 and at line 121:
  `_OWNER_ACTIONS.get((group, verb)) or _OWNER_ACTIONS.get((group, ''))`.
- `_OWNER_VERBS` (line 63) and the dotted names in `_WUWEI` (line 71-72) skip empty verbs, so
  relevance keeps requiring a real verb word. Do not add `setup` as a verb token: the
  literal `bin/wuwei setup ...` is refused through the parsed argv, which needs no relevance.
- Docs table of host terminal actions gains the three rows.

### 6. Docs

- `README.md` `## Quick start` and `docs/site/index.md` `## Start here`: install, then
  `../wuwei-plugin/bin/wuwei setup --shadow` from the project directory, then `/wuwei plan`.
  One sentence each for what setup does and that `config set` / `config add-repo` change one
  value later.
- `docs/site/daily.md` sections 1-2: `setup` replaces the init, edit, calibrate, promote and
  interview steps; keep the shadow paragraph.
- `docs/site/reference.md`: Commands rows for `setup` and the `config` row
  (`check`, `promote`, `set`, `add-repo`); Host terminal actions rows for `config set`,
  `config add-repo`, `setup` (digest: yes).
- `docs/site/concepts.md`: the same three host terminal rows.
- `docs/site/configuration.md` `## Calibration`: `setup` runs it; `config set` and
  `config add-repo` with one example each.

## What must not change

- `config promote` output, digest text and files written (tests in `tests/test_calibrate.py`,
  `tests/test_interview.py`, `tests/test_profiles.py`).
- `calibrate` command output and files.
- `init` behaviour; `setup` only calls it.
- Guard decisions for every existing row and every command in
  `tests/test_owner_actions.py::test_ordinary_work_passes`; relevance of existing text.
- `config check` output; `mcp check` behaviour.
- Hook latency (`WUWEI_BENCH=1`): the guard change is two dict lookups.

## Risks

- The worktree directory is named `327-setup`: any test command that embeds the repository
  path contains the word `setup`. Because `setup` is a group, not a verb token, this alone
  does not make text owner-relevant. Name new guard test functions without the words `set`,
  `setup` or `add-repo` (pytest puts the test name in `tmp_path`, which reaches payloads).
- `load_config(root, raw=text)` memoizes by text under the real path; that is correct (the
  memo is keyed on the text) and needs no change.

## Implementation notes

- `calibrate.apply` read `path[0]` to decide whether a key is quoted, so a top-level key
  (`config set nonsense 1`, path `()`) raised `IndexError`. It now reads `path[:1]`; nothing
  else in `apply` changed, and the schema check then refuses the unknown key before the
  confirmation.
- `config set` and `config add-repo` share one small frame in `setup.py` (`_edit`): reading
  `config.toml` (a symlink or an unreadable file) is exit 2, every validation failure is exit
  1, and the digest path is `config.offer`.
- The guard lookup is one helper, `_owner_reason(pair)`, used at both match sites.

# Implementation Plan: shareable calibration profiles: export a promoted calibration and interview, import as a proposal

**Branch**: `313-calibration-profiles` | **Spec**: `specs/313-calibration-profiles/spec.md`

## Summary

One new core module, `cli/wuwei/profiles.py`, holds the two tables (private keys, denied
keys) and the plain functions that read them: export, read, review, settings, record and
load. `wuwei calibrate` gains two positional actions, `export NAME` and `import SOURCE`,
plus `--skip KEY`. Config changes land only through the existing owner action
`wuwei config promote`, which gets one more settings source (today's `profile.json`) in
front of the interview settings. Charter changes land only through `wuwei promote` as
ordinary `add` proposals. Two starter profiles ship under `templates/profiles/`. No new
config key, charter, owner action, port, event kind or state key.

## Technical Context

Python 3.11+, stdlib only at runtime (`json`, `re`, `fnmatch`, `tomllib`,
`urllib.request`). pytest for tests. The only port call is the existing redactor port
(`registry.load('redactor', config).redact(text, root=root)`), default `builtin`.

## Constitution Check

- I Stdlib only: yes. The https fetch is `urllib.request.urlopen`, not a subprocess.
- II Three-state exits: export 0 written, 2 could not run (no workspace, bad name, unknown
  repository, file exists, symlinked override or ledger, malformed ledger, redactor exit 2
  or malformed data). Import 0 proposed, 1 refused (nothing written) or flagged (the rest
  written), 2 could not run (unreadable source, not https, over 1 MiB, bad JSON, bad shape,
  unknown `--skip`, `NO_REPOS`, unknown repository, preview `propose` fails). `config
  promote` keeps 0, 1, 2; a malformed or refused `profile.json` is 2.
- III One behaviour, one function: private and denied keys only in `profiles.PRIVATE` and
  `profiles.DENIED`, refusal only in `profiles.refusal`; config placement stays only in
  `calibrate.propose`/`settle`/`apply`; charter landing stays only in `promotion.promote`;
  the instruction scan stays only in `calibrate.instruction_like`; redaction stays only in
  the redactor port.
- IV Test first: every task pair in `tasks.md` is test then code.
- V Ponytail: one module of plain functions and two tuples, no classes, no new port. Reuse
  `calibrate.propose`, `calibrate._table`, `calibrate.instruction_like`,
  `calibrate.MAX_BYTES`, `calibrate.NO_REPOS`, `workspace._validate`, `workspace.SCHEMA`,
  `workspace.atomic_write` (its `replace=False` refuses an existing export file),
  `workspace.day_dir`, `promotion.safe_path`, `promotion._lines`, `notes.SLUG_RE`,
  `decision.level`, and the proposal JSON format as they are.
- VII Security: export output passes three filters (private literals, absolute paths, the
  redactor) and fails closed when the redactor cannot run; import refuses the whole
  profile on any denied or private key, flags instruction-like text, writes only proposals,
  and `config promote` re-validates `profile.json` before showing the digest. A refused key
  is checked before `--skip`, so skipping cannot launder it.

## Profile file format

```json
{
  "wuwei_profile": 1,
  "name": "python-library",
  "config": {
    "repos": {"fast_checks": ["python3 -m pytest -q"],
              "gates": {"trust_paths": [".github/*", "pyproject.toml"]}},
    "deploy": {"deny": ["twine upload*"]}
  },
  "charters": {
    "builder": {"text": "- Write the failing test first.\n", "reasons": ["starter profile"]}
  },
  "dropped": [{"where": "config.owner.name", "why": "personal"},
              {"where": "charters.builder:3", "why": "secret"}]
}
```

- `config` is nested exactly like `config.toml`, except `repos` is one table (no list)
  that import applies to each target repository.
- `charters` keys are shipped role names (`charters/<role>.md` in the plugin whose stem
  matches `notes.SLUG_RE`). `text` is the lines; `reasons` is a list of strings.
- `dropped` is informative; import ignores it. Export never writes a dropped value.
- Today's `profile.json` is the accepted part of an import in the same shape plus a
  top-level `repos` list of target repository names.

## Design

### 1. `cli/wuwei/profiles.py` (new)

Constants:

- `PLUGIN = Path(__file__).resolve().parents[2]`, `STARTERS = PLUGIN / 'templates/profiles'`.
- `ROLES`: sorted stems of `PLUGIN / 'charters' / '*.md'` that match `SLUG_RE` (the
  underscore files are excluded by the regex).
- `PRIVATE`: the dotted key prefixes listed under Assumptions in the spec (`owner`,
  `control_plane.owner`, `repos.name`, `repos.path`, `repos.default_branch`,
  `repos.identity`, `repos.merge.bot_login`, `voice`, `outbound.work_channels`,
  `outbound.external_channels`, `outbound.company_domains`, `outbound.code_host_orgs`,
  `outbound.people`, `shepherd.review_channel`, `shepherd.lead_login`, `shepherd.authors`,
  `tracker.backlog_filter`, `retro.repo`, `metrics.transcripts`, `scanner.mcp`, `guards`).
  A dotted key is private when it equals a prefix or starts with `prefix + '.'`.
- `FLOORS = workspace.SCHEMA['repos'][0]['gates']['floor'][2]` (light, standard, full).
- `DENIED`: tuple of `(fnmatch pattern, refused(new, current))`, with a one-line comment
  citing #313:
  - `('decisions.cruise.enabled', lambda new, old: new is True and old is False)`
  - `('decisions.cruise.levels.*', lambda new, old: new > old)`
  - `('repos.gates.floor', lambda new, old: FLOORS.index(new) < FLOORS.index(old))`
  - `('repos.merge.auto', lambda new, old: new is True)`
  - `('shepherd.autostart', lambda new, old: new is True)`
  - `('adapters.*' | 'calendar.url' | 'watch.ping_url' | 'codex.command', always)`
- `ABSOLUTE`: a regex for a token that starts (at the start of the text or after
  whitespace, a quote, a backtick, `=`, `(` or `,`) with `~/`, a drive letter and a slash
  or backslash, or `/` plus one segment plus `/`. It carries a `ponytail:` comment: a
  one-segment `/name` (a slash command) is not a path, and a path-shaped CODEOWNERS key
  such as `/src/api/` is dropped, which is conservative.

Functions:

- `_leaves(tree, path=())`: yield `(path, key, value)` for every non-dict value; an empty
  dict yields nothing.
- `_nest(rows)`: the inverse, rows to a nested dict.
- `_strings(value)`: every string in a value (lists and dicts recursively, dict keys too).
- `_changed(current, base)`: nested dict of leaves of `current` whose value differs from
  `base` (missing in `base` counts as different).
- `_current(config, path, key)`: `decision.level(config, key)` when
  `path == ('decisions', 'cruise', 'levels')`, else
  `(calibrate._table(config, path) or {}).get(key)`.
- `refusal(dotted, new, current)`: `'personal'` for a private key; `'outside what a
  profile may carry'` when a `DENIED` row matches (`fnmatch.fnmatchcase`) and its rule
  holds; else `None`.
- `_template()`: the shipped `templates/workspace/config.toml` through `tomllib` and
  `workspace._validate(parsed, workspace.SCHEMA, (), text)`, with `repos` replaced by one
  default repository: `workspace._validate({'name': '-', 'path': '-', 'default_branch':
  '-'}, workspace.SCHEMA['repos'][0], ('repos', 0), '')`.
- `_why(text, private, redactor, root)`: `'personal'` when a private literal occurs as a
  whole word (`(?<!\w)<literal>(?!\w)`); `'absolute path'` when `ABSOLUTE` matches; the
  sorted finding kinds joined by `, ` when `redactor.redact(text, root=root)` exits 1;
  raise `OSError(reason)` when it exits 2 or its data is not `{'text', 'findings'}`;
  `None` when clean.
- `export(root, config, name, repo=None)`: `ValueError` for a name not matching `SLUG_RE`
  or an unknown `repo`. `base = _template()`; `mine = {**config, 'repos': selected repo or
  base['repos']}`. Private literals (`_literals`): every string with a word character from
  `_strings` of each private leaf of `config` that differs from the template (every
  configured repository, not only the selected one), except `owner.verbosity`, `guards`
  and `repos.default_branch` (values such as `full`, `enforce` or `main` would drop
  ordinary words everywhere; corrected during implementation), plus the keys
  of `outbound.people` and `shepherd.authors`, plus `str(root)` and `str(Path.home())`.
  For each leaf of `_changed(mine, base)`: drop with `refusal(dotted, value,
  _current(base, path, key))`, else with the first `_why` over the dotted key and each of
  `_strings(value)`; keep the rest (`_nest`). Charters: for each
  `.wuwei/charters/<role>.md` with `role in ROLES` (path through `promotion.safe_path`),
  the non-blank lines whose stripped casefold is not in
  `promotion._lines(<shipped charter text>)`, each kept or dropped by `_why`
  (`where = charters.<role>:<line number in the override>`); reasons from
  `.wuwei/memory/ledger.jsonl` (through `safe_path`; absent is none) rows with
  `status == 'landed'` and `target == '.wuwei/charters/<role>.md'`, unique, each kept or
  dropped by `_why` (`where = charters.<role> reason <n>`). A role with no kept line is
  left out. Returns `{'wuwei_profile': 1, 'name', 'config', 'charters', 'dropped'}`.
- `read(source)`: a starter (`SLUG_RE` match and `STARTERS / f'{source}.json'` is a
  file), an `https://` URL (`urllib.request.urlopen(source, timeout=30)`, the final
  `geturl()` must still be https, read `MAX_BYTES + 1`), any other `scheme://` is
  `ValueError('only https URLs')`, else a local file. Over `calibrate.MAX_BYTES` is
  `ValueError`. Returns `_shape(json.loads(data))`.
- `_shape(profile)`: `ValueError` unless it is a dict with `wuwei_profile == 1`, a
  `SLUG_RE` `name`, a dict `config` (default `{}`) whose `repos`, if present, is a dict,
  and a dict `charters` (default `{}`) of `role in ROLES` to `{'text': str, 'reasons':
  [str, ...]}`. Returns the profile.
- `review(profile, config, names)`: target indices are the configured repositories whose
  name is in `names`; a `repos` part with no target raises `ValueError(calibrate.NO_REPOS)`.
  For each config leaf, expand a `repos` path to `('repos', index, ...)` per target;
  `refused` is the sorted dotted keys where `refusal` holds against any expanded current
  value. `flagged` is `(where, rule)` for each `calibrate.instruction_like` hit in the
  dotted key or a string of the value (`where` = dotted key), and in each role's `text`
  (`charters.<role>:<line>`) and reasons (`charters.<role> reason <n>`). Returns
  `(accepted, refused, flagged)`, `refused` as sorted `(key, why)` pairs, where `accepted` is the profile with only the unflagged
  config leaves and unflagged roles (no `dropped`).
- `skip(profile, accepted, keys)`: remove each dotted config key or `charters.<role>` from
  `accepted`; a key that names nothing in `profile` raises `ValueError` (so skipping a
  flagged key is not an error).
- `settings(accepted, config, names)`: the accepted config leaves as calibrate settings
  `(path, key, value)`, `repos` expanded per target index in configuration order.
- `record(root, accepted, names)`: write today's `profile.json`
  (`{**accepted, 'repos': names}`, `json.dumps(indent=2, sort_keys=True)`); for each role
  in `ROLES`, the role's non-blank lines not already in the target (the workspace
  override when it exists, else the shipped charter, via `promotion._lines`): write
  `proposals/profile-<role>.json` as `{'target': '.wuwei/charters/<role>.md', 'action':
  'add', 'text', 'reason': 'profile <name>' + (': ' + '; '.join(reasons) if reasons),
  'evidence': '.wuwei/days/<date>/profile.json'}`, or unlink a stale file of that name.
  Returns the written proposal paths relative to the workspace.
- `load(root, config)`: today's `profile.json`; absent gives `(None, [])`; a symlink,
  bad JSON, a bad shape, `repos` not a list of configured names, any refusal or any flag
  raises `ValueError('profile.json: ...')`. Returns `(name, settings(...))`.

### 2. `cli/wuwei/commands/calibrate.py`

- `register`: add `parser.add_argument('action', nargs='?', choices=('export',
  'import'))`, `parser.add_argument('target', nargs='?', metavar='NAME|SOURCE')` and
  `parser.add_argument('--skip', action='append', default=[], metavar='KEY')`.
- `run`: first line `if args.action: return _profile(args)`.
- `_profile(args)` (lazy `from wuwei import profiles`): `ValueError` when `target` is
  missing or an interview flag is also given. Export: `profiles.export(...)`, then
  `workspace.atomic_write(Path(f'{name}.json'), json.dumps(profile, indent=2,
  sort_keys=True) + '\n', replace=False)`; print `Wrote <name>.json` and one
  `Dropped <where>: <why>` line per drop; return 0. Import: `names` from `--repo` (unknown
  is exit 2) or all configured; `profiles.read`, `profiles.review`; when refused, print
  `wuwei calibrate: refused: <key> (<why>)` per key to stderr and return 1 with nothing
  written; then `profiles.skip`, preview `calibrate.propose(raw, [],
  profiles.settings(...))`, `profiles.record`; print the diff (or `No config.toml
  changes`), `Config differs; edit by hand: <key>` lines, one line per proposal path, one
  `Flagged <where> (<rule>), not proposed` line per flag, and the next step (`bin/wuwei
  config promote` in a host terminal, then `bin/wuwei promote`); return 1 when flagged,
  else 0. `OSError` and `ValueError` (including `ConfigError` from the preview) print
  `wuwei calibrate: <reason>` and return 2.

### 3. `cli/wuwei/commands/config.py` `promote`

After `answers = interview.load(root, config)`:
`name, imported = profiles.load(root, config)`; `asked = interview.settings(answers,
config)`; settings passed to `calibrate.propose` become `[s for s in imported if s[:2] not
in {a[:2] for a in asked}] + asked`. The summary gains, after the interview lines,
`Profile <name>: <path.key> = <json value>` per imported setting. Nothing else in
`promote` changes; the existing `ValueError` handler already turns a bad `profile.json`
into exit 2.

### 4. `cli/wuwei/guards/protect_state.py`

Add `'profile.json'` to the day-file tuple at line 194.

### 5. Starter profiles: `templates/profiles/python-library.json`, `templates/profiles/cli-tool.json`

Derived from WUWEI's own configuration and charters, each in the format above with
`"dropped": []`:

- `python-library`: `repos.fast_checks = ["python3 -m pytest -q"]`;
  `repos.gates.trust_paths` adds packaging and CI to the trust surface (`.github/*`,
  `ci/*`, `pyproject.toml`, `setup.py`, `setup.cfg`); `deploy.deny` adds package
  publishing (`twine upload*`, `uv publish*`, `poetry publish*`, `flit publish*`); a
  builder block (test first with the red run kept, no runtime dependency the item does
  not name, a public API change carries a changelog line) and a sentinel-quality block
  (block a public API change without a test and a changelog line).
- `cli-tool`: the same fast check; trust paths add `bin/*` to CI and packaging;
  `deploy.deny` adds package publishing; a builder block (every command exits 0 clean,
  1 findings, 2 could not run and prints why; tests run the installed entry point so a
  file in the working directory cannot shadow it) and a sentinel-quality block (a changed
  command, flag or exit code updates its reference docs in the same change).
- Each line must pass `calibrate.instruction_like`, the deny table and `_shape`, and must
  not duplicate a line of the shipped charter.

### 6. Docs

- `docs/site/configuration.md`: `## Calibration profiles` after `## Owner interview`:
  export (what it carries, what it drops and the `dropped` list), import (sources:
  starter name, https URL, file; the proposal; `--skip`; `--repo`; exit codes), the
  refused keys, the instruction-like rule, `profile.json` and the promote path, the two
  starters under `templates/profiles/`.
- `docs/site/reference.md` line 19: the calibrate row names `export` and `import`.

### What must not change

- `calibrate.propose`, `settle`, `apply`, `proposal` and `instruction_like`: signatures
  and behaviour; every existing test in `tests/test_calibrate.py` and
  `tests/test_interview.py` passes unchanged.
- `promotion.promote` and the proposal format; `interview.py`; the redactor adapter.
- The default `wuwei calibrate` path and the `--interview`, `--questions`, `--answer`
  flags.
- `workspace.SCHEMA`, `templates/workspace/config.toml`, `hooks/hooks.json`, the event
  kinds and state keys.

## Files

| File | Change |
|---|---|
| `cli/wuwei/profiles.py` | new |
| `cli/wuwei/commands/calibrate.py` | `export`/`import` actions, `--skip`, `_profile` |
| `cli/wuwei/commands/config.py` | `promote` reads `profiles.load`, summary lines |
| `cli/wuwei/guards/protect_state.py` | `profile.json` is a protected day file |
| `templates/profiles/python-library.json`, `templates/profiles/cli-tool.json` | new |
| `docs/site/configuration.md`, `docs/site/reference.md` | profiles section, calibrate row |
| `tests/test_calibrate.py` | profile tests (reuses `workspace_root`, `ports`, `configure`, `promote`) |
| `tests/test_protect_state.py`, `tests/test_hooks.py`, `tests/test_docs.py` | one test each, or one word in the existing hook-path test |

## Test notes

- Tests run in-process (`main('calibrate', ...)`, `profiles.*` directly); the only
  subprocess test stays the existing hook-path test.
- The `ports` fixture patches `registry.load` with a dict; profile tests add a
  `'redactor'` entry: the real builtin module (loaded with `importlib.util` from
  `adapters/redactor/builtin.py`, or the original `registry.load` captured before the
  patch) for redaction, and a stub returning `Result(2, None, 'down')` for the
  cannot-run case.
- Export tests `chdir` to `tmp_path` (monkeypatch) so `<name>.json` lands there.
- The URL tests monkeypatch `urllib.request.urlopen`; no network.
- Build secret-shaped fixture values by concatenation (for example `'ghp_' + 'a' * 36`)
  so the repository text holds no literal token.

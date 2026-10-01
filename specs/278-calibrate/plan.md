# Implementation Plan: calibrate profiles the project and proposes the workspace configuration

**Branch**: `278-calibrate` | **Spec**: `specs/278-calibrate/spec.md`

## Summary

One new core module, `cli/wuwei/calibrate.py`, holds the detector table, the
instruction-like scan, the additive config proposal and its application, the report, and
the drift check. One new command, `wuwei calibrate`, writes the report and charter
proposals. `config.py` gains the owner action `config promote`, the only writer of the
calibrated config and of `.wuwei/calibration.json`. Two port reads are added (vcs
`recent_commits`, code_host `merged_prs`). The steward runs the drift check on its sweep.
No new config keys, no new adapter kinds, no change to `wuwei promote`.

## Technical Context

Python 3.11+, stdlib only at runtime (`re`, `json`, `tomllib`, `difflib`, `statistics`,
`fnmatch`, `pathlib`). pytest for tests. No YAML parser: workflow files are read with a
few line regexes (ceiling noted below). Subprocesses only in `adapters/vcs/git.py` and
`adapters/code_host/github.py` behind their closed allowlists.

## Constitution Check

- I Stdlib only: yes. Detectors read files; `git log` and `gh api graphql` go through
  ports.
- II Three-state exits: calibrate 0/1/2 (FR-001); config promote 0 applied, 1 declined,
  2 could not run; an unmeasured read is exit 2 and labelled `unmeasured` in the report,
  never clean; drift on an unreadable checkout is reported as `unmeasured`.
- III One behaviour, one function: profiling lives only in `calibrate.profile`; calibrate,
  config promote and the steward all call it. The proposal is built only in
  `calibrate.proposal` and applied only in `calibrate.apply`.
- IV Test first: every task pair in `tasks.md` is test then code.
- V Ponytail: one module, plain functions in a tuple, no classes. Reuse
  `init._sections` and `init._preserves_values`, `workspace._validate` and `SCHEMA`,
  `workspace.MERGE_SCHEMA` defaults, `guards.deploy.VERBS`, `integrity._host_confirm`,
  `workspace.atomic_write`, `state.append_event`, `watch.records`, the proposal JSON
  format of `promotion.promote`.
- VII Security: repository text is data. Commands come from a fixed table; repository
  values pass a charset check and the instruction-like scan; flagged text is never
  echoed. The config writer is an owner action with a terminal digest; its snapshot is a
  protected path. Never proposes a weakening value (`merge_deploys = false`,
  `merge.auto`, removals).

## Design

### 1. `cli/wuwei/calibrate.py` (new)

Module constants:

- `SAFE = re.compile(r'[A-Za-z0-9 ._/()*@+-]{1,100}')` for repository-derived values.
- `INSTRUCTION_LIKE`: a tuple of `(rule, compiled regex)`, case-insensitive:
  - `override`: `\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|all|your|system)\b[^.\n]{0,20}\b(?:instructions?|rules|prompts?|guidelines)\b`
  - `role`: `\byou are now\b|\bnew instructions\s*:|\bsystem prompt\b`
  - `exfiltrate`: `\b(?:send|post|upload|exfiltrate)\b[^.\n]{0,40}\b(?:tokens?|secrets?|credentials|api keys?)\b`
  - `push`: `\bpush\b[^.\n]{0,30}\b(?:main|master|default branch)\b`
  - `bypass`: `\b(?:disable|bypass|skip|turn off)\b[^.\n]{0,30}\b(?:hooks?|guards?|review|checks?)\b|--no-verify`
  - every finding value (file names included) is also checked; a hit drops that finding.
  Probed on main: no hit in `AGENTS.md`, the constitution, `README.md`, `docs/site/*.md`
  or `charters/*.md`; the issue's phrase hits `override`. A `bypass` rule was dropped
  because it flags negated rules ("never bypass branch protection") in `_common.md`.
  `# ponytail: phrase list flags the obvious; route convention files through the scanner port if injections get subtler.`
- `CONVENTION_FILES`, `INFRA_PATHS` (`k8s`, `kubernetes`, `helm`, `charts`, `terraform`,
  `ansible`, `kustomize`, `fly.toml`, `vercel.json`, `netlify.toml`, `Procfile`,
  `app.yaml`, `serverless.yml`, `skaffold.yaml`), `DEPLOY_NAMES = ('deploy', 'release', 'publish')`.

Helpers:

- `_read(checkout, relative, findings)`: returns text or `None`; skips (and records a
  `skipped` finding) symlinks, non-files, files resolving outside the checkout (a symlinked
  parent directory) and files over 1 MiB; reads UTF-8 with `errors='replace'`.
- `_line(text, pattern)`: 1-based line of the first regex match, for sources.
- `instruction_like(text) -> list[(line, rule)]`.

Detectors, `fn(checkout: Path, repo: dict) -> list[dict]`, finding
`{'kind', 'value', 'source'}`, collected in `DETECTORS = (toolchain, ci_checks,
conventions, deploy_signals)`:

- `toolchain`: `pyproject.toml` (python; `pytest` mention or `pytest.ini` gives
  `python3 -m pytest -q`; `[tool.ruff` gives `ruff check .`; `[tool.black` gives
  `black --check .`), `package.json` (javascript; `json.loads`; `scripts.test` other than
  npm's "no test specified" placeholder gives `npm test`, `scripts.lint` gives
  `npm run lint`), `Cargo.toml` (`cargo test`), `go.mod` (`go test ./...`), `Makefile`
  targets `test|lint|check` (`make <t>`) only when no language was found.
- `ci_checks`: for each `.github/workflows/*.yml|*.yaml`, keep it when its `on` value or
  block names `pull_request` or `pull_request_target`. Jobs are the keys one indent level
  under `jobs:`; a job's `name:` one level deeper replaces the id. Findings: `ci_check`
  (job-level name), plus `required_check` values: the name, or `<name> (<v>)` per value
  when the job's `matrix:` has exactly one key with an inline `[a, b]` list; no
  `required_check` for `continue-on-error: true` jobs or other matrix forms.
  `# ponytail: line regexes over workflow YAML; anchors, multi-document files and flow mappings are not read. Add a YAML reader if a real repository needs them.`
- `conventions`: each existing `CONVENTION_FILES` path gives `convention`; each CODEOWNERS
  rule other than `*` gives `boundary` with value `(pattern, 'owned by <owners>')`.
- `deploy_signals`: a workflow triggered by `push` (default branch or tags) or `release`
  with a job `environment:`, a `uses:` matching `deploy|release-please|gh-release|publish`,
  or a `run:` containing a `wuwei.guards.deploy.VERBS` program and verb or
  `gh release create` gives `deploy_workflow` (file name). Its `environment:` name
  (inline or `name:` under the block; an expression is a `skipped` finding) and its push
  branches other than `repo['default_branch']` give `environment`. Makefile targets and
  `package.json` scripts in `DEPLOY_NAMES`, or Makefile recipes running a deploy verb,
  give `deploy_deny` (`make <target>*`, `npm run <script>*`). Existing `INFRA_PATHS`
  not matched by the default `MERGE_SCHEMA['never_auto_paths']` give `never_auto`
  (`<dir>/*` or the file name).

`profile(checkout, repo) -> dict`: run every detector; scan each distinct source file once
with `instruction_like`; drop every finding from a flagged file and add an
`instruction_like` finding (`source`, `value` = rule); drop repository-derived values
(`ci_check`, `required_check`, `environment`, `boundary`, scope words) that fail `SAFE`
and add an `unsafe` finding by source. Returns `{'findings': [...], 'facts': {...}}`
where facts are the sorted, de-duplicated lists `languages`, `fast_checks`, `ci_checks`,
`required_checks`, `conventions`, `deploy_workflows`, `environments` (dict),
`deploy_deny`, `never_auto`, `boundary` (dict) and `merge_deploys` (bool).

`DRIFT = ('fast_checks', 'ci_checks', 'deploy_workflows', 'environments', 'deploy_deny', 'never_auto')`;
`drift_facts(facts)` returns those keys (environments as sorted names).

Pure functions over port data:

- `commit_style(commits)`: `commits` is `[{'subject', 'signed_off'}]`; returns
  `{'conventional': bool, 'scopes': top five, 'sign_off': bool, 'commits': n}` using
  `^[a-z]+(?:\(([^)]+)\))?!?: ` and the 80 percent rule; scopes must match
  `[a-z0-9][a-z0-9-]{0,30}`.
- `baseline(prs)`: `prs` is `[{'additions', 'deletions', 'created_at', 'merged_at'}]`;
  returns `{'prs': n, 'median_changed_lines': int, 'median_cycle_hours': float}` with
  `statistics.median`; `{'prs': 0}` when empty.

Proposal and application:

- `proposal(raw, targets) -> (additions, hand_edits)` with `targets = [(repo index, facts)]`
  (changed during implementation: root-level values such as `deploy.workflows` are merged
  across every calibrated repository, so one call covers them all): reads presence from
  `tomllib.loads(raw)` (never from `load_config`, which fills defaults). `additions` is a
  list of `(path, key, value)` with `path` one of `('repos', index)`,
  `('repos', index, 'merge')`, `('deploy',)`, `('environments',)`, `('boundary',)`.
  Rules in FR-010. `hand_edits` is `[(dotted key, current, detected)]`.
- `apply(raw, additions) -> str`: split with `init._sections`; give each section a path
  (count `[[repos]]` labels for the index; a `repos.merge` label belongs to the latest
  repo; other labels split on `.`). Append `key = <value>` lines under one
  `# Added by wuwei config promote from calibration.` comment to the matching section;
  create a missing `[repos.merge]` section right after that repo's last section and a
  missing root table at the end. Replace a `deploy.workflows`/`deploy.deny` line only when
  it fullmatches `key\s*=\s*\[\]\s*(#.*)?`. Values render with `json.dumps` (keys too,
  quoted). Validate: `tomllib.loads`, `init._preserves_values(before minus replaced keys,
  after)`, `workspace._validate(parsed, workspace.SCHEMA, (), text)`. Any failure raises
  `ValueError('cannot place calibration keys in this config.toml layout; edit by hand')`
  or the validator's message. No placeable `[[repos]]` (inline array) is the same error.
- `charter_proposals(repo, facts, style) -> dict[role, text]` for `builder` and
  `sentinel-quality`: heading `## Repository conventions: <repo name>`, then at most three
  bullets: convention sources (paths), commit style (fixed phrase plus scope words, sign-off
  phrase), fast checks (commands). Empty when there is nothing to say.

Shared steps (added during implementation so the command, `config promote` and the steward
call one function each):

- `survey(root, config, selected, *, style=True)`: profiles every selected `(index, repo)`
  (a missing checkout raises `OSError` before any port call), then reads commit style
  (vcs, skipped for `config promote`) and the PR baseline (code host); a failed read is `None`,
  reported as `unmeasured`.
- `propose(raw, results) -> (text, diff, hand_edits)`.
- `approved(root)`: reads `.wuwei/calibration.json` (absent: `{}`; symlink or malformed:
  `ValueError`).

Report and drift:

- `report(results, diff, hand_edits, written) -> str`: markdown with one section per
  repository (toolchain, CI checks with matrix and informational notes, conventions,
  commit style, deploy signals, PR baseline, instruction-like and unsafe findings by
  source, skipped files), then the proposed diff (`difflib.unified_diff` of raw and
  applied text), hand edits, the charter proposal paths, and the next step
  (`bin/wuwei config promote` in a host terminal; `wuwei promote` for charters).
- `drift(root) -> list[dict]`: load `.wuwei/calibration.json` (absent: `[]`; symlink or
  malformed: `ValueError`); for each repository there and still in `load_config(root)`
  recompute `drift_facts(profile(...)['facts'])` (an `OSError` gives
  `changed = ['unmeasured']`), compare, and for each non-empty `changed` not already in
  today's `calibration.drift` events (`watch.records(day / 'events.jsonl')`) call
  `state.append_event('calibration.drift', {'repo': name, 'changed': changed}, root)`.
  Returns the payloads.

### 2. `cli/wuwei/commands/calibrate.py` (new)

`register` adds `calibrate` with `--repo`. `run(args)`:

1. `root = workspace.find_workspace()`, `config = load_config(root)`, `raw` = the
   `config.toml` text. No repos: exit 2 with the "add name, path and default_branch"
   reason. `--repo` unknown: exit 2.
2. For each selected repo: `checkout = (root / Path(repo['path']).expanduser()).resolve()`;
   not a directory: exit 2 before writing. `profile`; `registry.load('vcs', config)
   .recent_commits(str(checkout), root=root)` then `commit_style` or `unmeasured`;
   `registry.load('code_host', config).merged_prs(repo['name'], root=root)` then
   `baseline` or `unmeasured`.
3. Proposal for all selected repos, `apply` (a `ValueError` is reported, exit 2), diff.
4. Write `workspace.day_dir(root) / 'calibration.md'` and, per repo and role with text,
   `proposals/calibration-<slug>-<role>.json` with `{'target': '.wuwei/charters/<role>.md',
   'action': 'add', 'text', 'reason': 'calibration of <repo>: repository conventions',
   'evidence': '.wuwei/days/<date>/calibration.md'}` (slug: repo name with every
   non-`[a-z0-9]` run replaced by `-`). `workspace.atomic_write` for all; `mkdir`
   parents.
5. Print the report path, the diff and the next step. Exit as FR-001.

### 3. `cli/wuwei/commands/config.py`

Add `promote` to the `config` subparsers (`set_defaults(func=promote)`), no options.
`promote(args, confirm=None)`:

1. Load config and raw text; for every configured repo compute `profile`, `baseline`
   (code host; `unmeasured` on failure) and the proposal; `apply`.
2. Print the diff (or `No config.toml changes`), hand edits, flagged findings and the
   snapshot it will record.
3. Digest: first 12 hex of `sha256` over the printed text. `confirm or
   integrity._host_confirm` with prompt `Review the calibration above. To apply it, type:`.
   Declined: exit 1. `OSError` (no terminal): exit 2 with the reason.
4. Re-read `config.toml`; changed since step 1: exit 2. Else `atomic_write` it (only when
   the text changed) and `atomic_write(root / '.wuwei/calibration.json', ...)` with
   `{name: {**drift_facts, 'baseline': ..., 'date': workspace.now().date().isoformat()}}`.
5. `ConfigError` exit 1, `ValueError`/`OSError` exit 2, as the existing check does.

### 4. Guards and events

- `cli/wuwei/guards/protect_state.py`: add `('config', 'promote'): 'Calibration promotion
  is an owner action on the host, outside agent tools.'` to `_OWNER_ACTIONS`, and
  `('calibration.json',)` to the `tail in (...)` tuple in `_protected_name` (line 175).
- `cli/wuwei/commands/event.py`: `'calibration.drift': 'wuwei steward run'` in
  `EVENT_PRODUCERS` (every kind but `note` is already refused; this names the producer).
- `cli/wuwei/signal.py`: no change; an unlisted kind is already a nudge. A table row
  proves it.

### 5. Steward

`cli/wuwei/steward.py:run` after `queue = decision_queue(root)`: when
`trigger == 'sweep'`, `from wuwei import calibrate` (local import, off the hook path),
`drift = calibrate.drift(root)`; read the baseline from `.wuwei/calibration.json` when
present; add one `Calibration: <json of baseline and drift>` line to `body`. Close and
tool-call triggers are unchanged.

### 6. Ports

- `adapters/vcs/git.py`: `_RECENT_FORMAT = '--format=%s%x1f%(trailers:key=Signed-off-by,valueonly,separator=%x2c)'`;
  allowlist case `('log', '-z', '--max-count=100', _RECENT_FORMAT, 'HEAD', '--')`;
  `@_operation def recent_commits(repo, root=None)` returning
  `[{'subject': s, 'signed_off': bool(trailer.strip())}]` from `_records(output)` split on
  `\x1f` (a record without exactly one `\x1f` is `ValueError`).
- `adapters/code_host/github.py`: `_MERGED = 'query($o:String!,$r:String!){repository(owner:$o,name:$r){pullRequests(states:MERGED,first:30,orderBy:{field:CREATED_AT,direction:DESC}){nodes{additions deletions createdAt mergedAt}}}}'`;
  add it to the graphql allowlist tuple; `@_operation def merged_prs(repo, root=None)`
  with `_repo(repo)` and strict `_field` reads. `adapters/code_host/none.py`:
  `record_none('code_host', 'merged_prs', root, measurement=True)`.
- `cli/wuwei/registry.py`: `'recent_commits': ('repo',)` under `vcs`,
  `'merged_prs': ('repo',)` under `code_host`.
- `tests/fakes/vcs.py`, `tests/fakes/code_host.py`: one `_call` method each.

### 7. Docs

- `docs/site/daily.md` section 2: after `config check`, run `bin/wuwei calibrate`, read
  `.wuwei/days/<date>/calibration.md`, then `bin/wuwei config promote` in a host terminal
  and `bin/wuwei promote` for the charter proposals.
- `docs/site/configuration.md`: a `## Calibration` section: what each detector reads,
  the report, the additive proposal rule, owner values never changed, instruction-like
  and unsafe text, `config promote`, `.wuwei/calibration.json`, `calibration.drift`.
- `docs/site/reference.md` host terminal table: `bin/wuwei config promote` | yes.
  `docs/site/concepts.md` host terminal sentence: add `wuwei config promote`.

## Data shapes

`.wuwei/calibration.json`:

```json
{"acme/widget": {"fast_checks": ["python3 -m pytest -q"], "ci_checks": ["test"],
  "deploy_workflows": ["docs.yml"], "environments": ["github-pages"],
  "deploy_deny": [], "never_auto": [],
  "baseline": {"prs": 30, "median_changed_lines": 210, "median_cycle_hours": 5.5},
  "date": "2026-10-01"}}
```

`calibration.drift` payload: `{"repo": "acme/widget", "changed": ["ci_checks"]}`.

## Must not change

- `wuwei promote`, `promotion._target` and the proposal lint: charter proposals use them
  as they are; `config.toml` never becomes a promote target.
- `init._migrated_config` and `init --upgrade` behaviour (only its helpers are imported).
- `workspace.SCHEMA` (no new keys), the template `config.toml`, and every hook, guard
  selection and latency budget. No hook module imports `wuwei.calibrate`.
- `config check` output and exits.
- The checkout: calibrate opens files read-only and runs only the two port reads.

## Files

New: `cli/wuwei/calibrate.py`, `cli/wuwei/commands/calibrate.py`,
`tests/test_calibrate.py`, fixture directories under `tests/fixtures/calibrate/`
(`python`, `node`, `node-placeholder`, `rust-go-make`, `workflows`, `conventions`, `deploy`, `injected`,
`unsafe`). Fixtures contain no `AGENTS.md` or `CLAUDE.md`.

Changed: `cli/wuwei/commands/config.py`, `cli/wuwei/steward.py`,
`cli/wuwei/guards/protect_state.py`, `cli/wuwei/commands/event.py`,
`cli/wuwei/registry.py`, `adapters/vcs/git.py`, `adapters/code_host/github.py`,
`adapters/code_host/none.py`, `tests/fakes/vcs.py`, `tests/fakes/code_host.py`,
`tests/fixtures/vcs/recordings.json`, `tests/fixtures/code_host/recordings.json`,
`tests/test_adapters.py` (CALLS rows), `tests/test_code_host.py` (read set),
`tests/test_owner_actions.py`, `tests/test_protect_state.py`,
`tests/test_signal_status.py`, `tests/test_steward.py`, `tests/test_hooks.py`,
`tests/test_docs.py`, `docs/site/daily.md`, `docs/site/configuration.md`,
`docs/site/reference.md`, `docs/site/concepts.md`.

## Deferred

- Ruleset-aware required check names and branch protection as a source for CI names
  (`config check` already compares them, #243).
- A YAML reader for workflows beyond the line regexes.
- Applying the baseline in steward metrics; today it is brief input only.

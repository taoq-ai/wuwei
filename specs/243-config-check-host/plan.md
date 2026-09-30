# Implementation Plan: config check verifies the host protections and seat credential layout

**Branch**: `243-config-check-host` | **Spec**: `specs/243-config-check-host/spec.md`

## Summary

Extend the existing `config check` (`cli/wuwei/commands/config.py`) with two sections that
read through the code_host port: host protections per configured repository (reusing the
existing `protection` read) and seat credentials (one new port read, `token_scopes`).
Add two booleans to the GitHub protection read, narrow its "absent" classification to
gh's real "Branch not protected" message, print the layout once on fresh `wuwei init`,
and document it. No new config keys, no new modules.

## Technical Context

Python 3.11+, stdlib only at runtime, pytest for tests. Subprocesses only in
`adapters/code_host/github.py` behind its closed `_run` allowlist. Tests use the recording
fake (`tests/fakes/code_host.py`) and `fakes.replay.install_replay`; no network, no real
`gh`.

## Constitution Check

- I Stdlib only: yes. II Three-state exits: every new line is ok, missing or unmeasured;
  a failed read is exit 2 with the reason on stderr; unmeasured is never ok.
- III One behaviour, one function: the check lives only in `commands/config.py`; the
  merge policy and shepherd keep their own reads of the same port operation.
- IV Test first: every task pair below is test then code.
- V Ponytail: one new port operation (the core may not run `gh`), no helper module, no
  config key (the solo-owner exemption reuses `shepherd.min_reviewers = 0`, the check
  names reuse `repos.review_required_checks`).
- VII Security: token values are never printed; the measuring subprocess sees only the
  measured token; the new `_run` case is read-only (`GET /user`).

## Design

### 1. `adapters/code_host/github.py`

- `_run(args, payload=None, *, json_output=True, env=None)`: pass `env=env` to
  `subprocess.run`. Add one allowlist case:
  `case ['api', '--include', 'user']: allowed = payload is None and not json_output`.
  On the non-JSON path return `result.stdout` instead of `None` (the only other non-JSON
  caller, `merge`, ignores the return value).
- 404 classification (lines 86-89): keep the endpoint regex and `HTTP 404`, and also
  require `Branch not protected` in `result.stderr`. Any other 404 falls through to
  `gh exited <n>` (unmeasured).
- `protection`: add to `result`
  `'allow_force_pushes': _field(value['allow_force_pushes'], 'enabled', bool)` and
  `'allow_deletions': _field(value['allow_deletions'], 'enabled', bool)` (strict, like
  `enforce_admins`: github.com always returns both). In the rules loop add
  `elif kind == 'non_fast_forward': result['allow_force_pushes'] = False` and
  `elif kind == 'deletion': result['allow_deletions'] = False`.
- New read, `token_scopes(variable, root=None)`, wrapped in `@_operation`:
  - `variable` must be `'GH_TOKEN'` or `'GITHUB_TOKEN'` and set in `os.environ`, else
    `ValueError('expected a set GH_TOKEN or GITHUB_TOKEN')`.
  - child env: `os.environ` minus both names, plus `GH_TOKEN = os.environ[variable]`
    (so gh measures exactly that value; `GH_TOKEN` wins over `GITHUB_TOKEN` in gh).
  - `_run(['api', '--include', 'user'], json_output=False, env=child)`; take the header
    block (text before the first blank line), find `X-OAuth-Scopes:` case-insensitively,
    split on commas, strip, drop empties.
  - No header or an empty list raises `ValueError('token scopes unmeasured')`
    (fine-grained and app tokens do not report scopes). Return `{'scopes': [...]}`.
  - Needs `import os`. Never include the header or body in a reason.

### 2. Port declaration and the other implementations

- `cli/wuwei/registry.py`: add `'token_scopes': ('variable',)` to
  `PARAMETERS['code_host']`.
- `adapters/code_host/none.py`: `def token_scopes(variable, root=None): return
  record_none('code_host', 'token_scopes', root, measurement=True)`.
- `tests/fakes/code_host.py`: `def token_scopes(self, variable, root=None): return
  self._call('token_scopes', (variable,), root)`. No recording is added, so the fake's
  default is exit 2 until a test sets `host.results['token_scopes']`.

### 3. `cli/wuwei/commands/config.py`

After the existing adapter loop, before `return status`:

```python
host = registry.load('code_host', config)
print('Host protections:')
for repo in config['repos']:
    status = max(status, _protection(host, repo, config['shepherd']['min_reviewers'] == 0))
print('Seat credentials:')
for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
    status = max(status, _token(host, name))
```

`_protection(host, repo, solo)`: label `f"  {repo['name']} {branch}"`.
- `result = host.protection(repo['name'], branch)`.
- exit 2 and `'branch protection absent' in result.reason`: print
  `<label>: protected ref: missing (protect <branch>: require status checks and at least
  1 approving review, block force pushes and deletions)`; return 1.
- any other non-zero exit: print `<label>: protection: unmeasured`, reason to stderr;
  return 2.
- exit 0: inside `try`, evaluate five rows `(name, ok, fix)` and print
  `<label>: <name>: ok` or `<label>: <name>: missing (<fix>)`; return 1 if any missing,
  else 0. `except (KeyError, TypeError, ValueError)`: unmeasured line, return 2.
  - protected ref: ok.
  - required checks: `names = {c['name'] for c in data['required_checks']}`,
    `absent = [n for n in repo['review_required_checks'] if n not in names]`;
    ok when `names and not absent`; fix `require status checks on <branch>` plus
    `: <absent names>` when any.
  - required reviews: ok when `data['approvals'] >= 1`; else ok with text
    `ok (solo owner: shepherd.min_reviewers = 0)` when `solo`; else fix
    `require at least 1 approving review on <branch>, or set shepherd.min_reviewers = 0
    for a solo owner`.
  - force pushes: ok when `not data['allow_force_pushes']`; fix
    `block force pushes on <branch>`.
  - deletions: ok when `not data['allow_deletions']`; fix `block deletions of <branch>`.

`_token(host, name)`:
- not `os.environ.get(name)`: print `  <name>: not set`; return 0.
- source: `'.wuwei/env'` if `name in env._loaded` else `'the environment'` (import
  `env` from `wuwei`; `_loaded` is the set `env.load` fills).
- `result = host.token_scopes(name)`; non-zero or data not a dict with a `scopes` list:
  `  <name> (<source>): unmeasured`, reason to stderr; return 2.
- all scopes start with `read:`: `  <name> (<source>): read-only`; return 0.
- else `  <name> (<source>): write scopes <comma list>; remove it from <source>, seats
  can read it (publish from the owner's own gh login)`; return 1.

Exit is `max` over all lines, as the credential section already does.

### 4. `cli/wuwei/commands/init.py`

In `run` (fresh init only), after the `statusLine` print and before `_finish`, print a
module constant `LAYOUT` (a few lines):

```
Recommended publishing layout (design 4.5, 9.1):
  protect each repository's default_branch: required status checks including the test
  jobs, at least 1 approving review (or shepherd.min_reviewers = 0 for a solo owner),
  no force pushes, no deletions
  keep write-scoped GH_TOKEN and GITHUB_TOKEN out of .wuwei/env and the environment
  seats inherit; publish from the owner's own gh login
Verify with: bin/wuwei config check
```

`upgrade` does not print it.

### 5. Docs

- `docs/site/configuration.md`, section "Private workspace environment": after the
  existing `config check` paragraph add a short subsection "Host protections and seat
  credentials" stating: what each of the five protection lines checks, the token lines,
  ok / missing / unmeasured, exit 0 / 1 / 2 (unmeasured wins over missing), that every
  missing line names the setting to change, that `code_host = "none"` makes them
  unmeasured, and why: design 4.5 and 9.1 put the publishing guarantee in the host rules
  and the credential layout, not in the hooks.
- `docs/site/adapters.md:56`: keep the auth requirement; add that a write-scoped
  `GH_TOKEN` or `GITHUB_TOKEN` in `.wuwei/env` or the environment is readable by seats
  and is reported by `wuwei config check`.

### 6. Tests (all offline)

- `tests/conftest.py`: in the existing autouse fixture (or a new autouse one next to it)
  `monkeypatch.delenv('GH_TOKEN', raising=False)` and the same for `GITHUB_TOKEN`, so a
  developer's shell never reaches the new scope read. Tests that need a token set it.
- `tests/test_env_credentials.py` (holds the existing `config check` tests and the
  `case` fixture): new tests use `code_host="none"` in config plus
  `monkeypatch.setattr(registry, 'load', ...)` returning `fakes.code_host.Fake()` for
  `code_host` (and the real loader otherwise), and a `[[repos]]` entry
  (`name = "acme/widget"`, `path = "repo"`, `default_branch = "main"`).
- `tests/test_code_host.py`: `token_scopes` replay tests and the narrowed 404.
- `tests/test_merge_ports.py`: ruleset rules turn the two new booleans off.
- `tests/fixtures/code_host/recordings.json`: the `protection` case stdout gains
  `"allow_force_pushes": {"enabled": false}, "allow_deletions": {"enabled": false}` and
  its `data` gains both keys as `false`.
- `tests/test_adapters.py`: `CALLS` gains `('code_host', 'token_scopes', ('variable',),
  True)` (the none-adapter and signature contract tests then cover it).
- `tests/test_shepherd.py:544-550`: stderr becomes `gh: Branch not protected (HTTP 404)`.
- `tests/test_workspace.py:200-211` (`test_all_config_fields`): its two `[[repos]]`
  entries now make `config check` exit 2 (unmeasured: names are not `owner/repo`, so the
  adapter refuses before any subprocess); assert 2 and `unmeasured` in stdout.
- `tests/test_docs.py`: one test that `configuration.md` names the check, the three
  states, the exit codes and design 4.5 and 9.1.

## Must not change

- The merge policy (`cli/wuwei/merge.py`) and the shepherd (`cli/wuwei/shepherd.py`):
  no edits. Their protection reads keep the same `branch protection absent` contract for
  an unprotected branch; the new keys are extra and unread by them.
- The existing credentials section output and its tests (the `auth_status` call and
  lines stay byte for byte).
- `env.child_environment()`, `env.CREDENTIALS` and `.wuwei/env` loading.
- The `_run` allowlist beyond the one `api --include user` case; no write endpoint, no
  change to the protection or rulesets endpoints.
- No new `config.toml` key and no template change.

## Evidence

Read-only scratch reproduction (see spec Root cause): exit 0, only
`gh auth status --hostname github.com` called, `GH_TOKEN` in `.wuwei/env` unreported.

## Deferred

- Ruleset-only protection read as protected (changes merge policy input).
- Checking the credential stored by `gh auth login`, which Claude seats share with the
  host session (needs a separate OS user for seats, design 9.1 later option).

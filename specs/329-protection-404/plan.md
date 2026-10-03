# Implementation Plan: branch protection read falls back to rulesets on a classic 404 and reports each source

**Branch**: `329-protection-404` | **Spec**: `specs/329-protection-404/spec.md`

## Summary

Fix it once at the shared spot: the GitHub adapter's `protection()`. Any 404 on the
classic endpoint becomes "classic not visible": the adapter substitutes the settings of an
unprotected branch, reads the rulesets as it does today, and adds one boolean `classic` to
its result. `config check` then prints a `classic protection: none visible` line instead of
`protected ref: ok`, lists the required check names, and names the review gate check on a
missing reviews line. Its old `branch protection absent` branch becomes unreachable and is
deleted. No new config key, port operation, event, state key or `gh` allowlist entry.

## Technical Context

Python 3.11+, stdlib only. The only external tool is `gh`, reached through the existing
`_run()` allowlist; both endpoints (`repos/<r>/branches/<b>/protection` and
`repos/<r>/rules/branches/<b>?per_page=100`) are already allowed. Tests replay `gh` with
`tests/fakes/replay.py` (`install_replay`) or use `tests/fakes/code_host.py` (`Fake`).

## Constitution Check

- I Stdlib only: no new import.
- II Three-state exits: a classic 404 is now measured data, not an error; every other
  classic failure and every rulesets failure (including a rulesets 404) stays exit 2. An
  invisible repository therefore stays unmeasured: its rulesets read 404s too.
- III One behaviour, one function: the 404 decision stays in `_run()` (the existing
  protection-endpoint special case); the fallback lives only in `protection()`; the
  rendering lives only in `config._protection()`.
- IV Test first: each behaviour in `tasks.md` is a failing test, then the code.
- V Ponytail: the fallback is a synthetic empty classic body fed to the existing parsing,
  so no second code path for the classic fields. One regex loosened, one try/except, one
  key added.
- VII Security: never reports clean when unmeasured; merge still requires GitHub's
  `mergeable_state == 'clean'` (see "Merge and shepherd" below).

## Design

### 1. `adapters/code_host/github.py`

`_run()`, line 102: widen the protection-endpoint 404 match from
`r'Branch not protected \(HTTP 404\)'` to `r'\(HTTP 404\)'`. The endpoint regex on line 101
already limits this to `repos/<o>/<r>/branches/<b>/protection`. Keep the message
`'branch protection absent'`; it is now an internal signal between `_run()` and
`protection()`.

`protection()`, line 311: wrap the classic read.

```python
    try:
        value, classic = _api(f'repos/{_repo(repo)}/branches/{quote(branch, safe="")}/protection'), True
    except ValueError as exc:
        if str(exc) != 'branch protection absent':
            raise
        # 404: unprotected or no admin. Read on as an unprotected branch; the rulesets read
        # below still measures, and fails closed when the repository is not visible.
        value, classic = {'enforce_admins': {'enabled': False},
                          'allow_force_pushes': {'enabled': True},
                          'allow_deletions': {'enabled': True}}, False
```

The existing parsing then yields `required_checks = []`, `strict False`, `approvals 0`,
review booleans False, `enforce_admins False`, `allow_force_pushes True`,
`allow_deletions True`, `conversation_resolution False`. Add `'classic': classic` to the
`result` dict (line 326). The rulesets loop (lines 338-365) is unchanged.

### 2. `tests/fixtures/code_host/recordings.json`

Add `"classic": true` to the `protection` recording's `data`, so `test_read_recording` and
every `Fake`-backed test carry the new key.

### 3. `cli/wuwei/commands/config.py`

- `run()`, line 75: pass the gate name:
  `_protection(host, repo, config['shepherd']['min_reviewers'] == 0, config['shepherd']['review_gate_check'])`.
- `_protection(host, repo, solo, gate)`:
  - delete the `branch protection absent` branch (lines 172-175); the adapter no longer
    returns it.
  - inside the `try`, `names = sorted({check['name'] for check in data['required_checks']})`
    and `listed = ', '.join(names)`; `absent` stays as today.
  - first row: `('protected ref', 'ok', '') if data['classic'] else ('classic protection',
    'none visible (404: unprotected or no admin)', '')`. A missing `classic` key raises
    `KeyError`, which the existing `except` turns into `unmeasured`.
  - `required checks` row: state `f'ok ({listed})'` when `names and not absent`; the fix text
    appends `f'; required now: {listed}'` when `names` is not empty.
  - `required reviews` row: the fix text appends
    `f'; the required check {gate} (shepherd.review_gate_check) may be satisfying it'` when
    `gate in names`.
  - the final loop and exit computation are unchanged; the classic row has a truthy state,
    so it is never a finding.

Resulting lines for a classic 404 with rulesets `[]`:

```
  acme/widget main: classic protection: none visible (404: unprotected or no admin)
  acme/widget main: required checks: missing (require status checks on main)
  acme/widget main: required reviews: missing (require at least 1 approving review on main, or set shepherd.min_reviewers = 0 for a solo owner)
  acme/widget main: force pushes: missing (block force pushes on main)
  acme/widget main: deletions: missing (block deletions of main)
```

### 4. `docs/site/configuration.md`, section "Host protections and seat credentials"

- `protected ref` row: `ok` when classic branch protection is readable.
- New row `classic protection`: printed instead of `protected ref` when the classic
  endpoint answers 404 (`none visible (404: unprotected or no admin)`); information only,
  the other lines then come from rulesets.
- `required checks` row: lists the required check names; a missing line names the
  `review_required_checks` names that are not required and the ones that are.
- `required reviews` row: when a required check is named as `shepherd.review_gate_check`,
  the missing line says that check may be satisfying it; it stays a finding.
- Replace "A branch protected only by rulesets currently reads as missing." with: the
  check, review, force-push and deletion lines combine classic protection with the
  branch's rulesets, so a branch protected only by rulesets measures correctly.

### Merge and shepherd (no code change)

`cli/wuwei/merge.py` and `cli/wuwei/shepherd.py` call the same `protection()`. After this
change a classic 404 gives them rules-derived evidence instead of exit 2:

- merge: `green()` still refuses with no required checks, and the policy still requires
  `mergeable_state == 'clean'`, which GitHub computes with classic rules the caller cannot
  read; a caller without admin cannot bypass them, and `gh pr merge` never uses `--admin`.
- shepherd: its `branch protection absent` handling (lines 122-138) is no longer reached
  through the GitHub adapter; the empty `required_checks` path that replaces it already
  retries the default branch and falls back to `review_required_checks`. Leave the code as
  is: removing it is cleanup outside this issue, and `test_stacked_base_uses_default_branch_required_checks`
  still exercises it through the `Fake`.

### What must not change

- The `gh` allowlist in `_run()` (no new command shape).
- The rulesets parsing and the classic parsing for a 200 response.
- Exit 2 for every non-404 classic failure, for any rulesets failure, and for a malformed
  protection result.
- `merge.py`, `shepherd.py`, `adapters/code_host/none.py`, the registry contract.
- Output for a readable classic protection, apart from the names on the `required checks`
  line.

## Files

| File | Change |
| --- | --- |
| `adapters/code_host/github.py` | 404 regex in `_run()`; try/except and `classic` key in `protection()` |
| `cli/wuwei/commands/config.py` | `_protection()` rows, gate argument, delete absent branch |
| `docs/site/configuration.md` | host protections table and closing sentence |
| `tests/fixtures/code_host/recordings.json` | `"classic": true` in protection data |
| `tests/test_code_host.py` | classic 404 tests; update `test_unreadable_protection_is_not_absent` |
| `tests/test_env_credentials.py` | end-to-end config check tests; update two existing tests and one parametrize row |
| `tests/test_shepherd.py` | update `test_missing_branch_protection_keeps_reason_for_fallback` |
| `tests/test_docs.py` | assert the new doc terms |

## Test notes

- Classic 404 replay step: `{'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'}` (and the
  `Branch not protected` form). Rulesets step for an empty answer: `{'stdout': '[[]]'}`
  (`--paginate --slurp` wraps pages in a list).
- End-to-end `config check` through the real adapter: config
  `[adapters]\ncode_host="github"\n` plus the `REPO` table; replay steps in order:
  `{'exit': 0}` for `gh auth status`, the classic 404, the rulesets page. The conftest
  removes `GH_TOKEN` and `GITHUB_TOKEN`, so no scope read follows. Use the `case` fixture,
  not `host` (which replaces the adapter with the `Fake`).
- Rules JSON for checks and reviews: see `rules_step` in `tests/test_merge_ports.py`
  (`required_status_checks` with `strict_required_status_checks_policy` and
  `required_status_checks: [{'context': ...}]`; `pull_request` with all five parameters;
  `non_fast_forward`; `deletion`).

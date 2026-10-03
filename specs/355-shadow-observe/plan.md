# Implementation Plan: --shadow means posture observe, and guards.mode retires

**Branch**: `355-shadow-observe` | **Spec**: `spec.md`

## Summary

Two shared spots. `init.upgrade` already feeds `doctor`'s `template` row and the
`init-upgrade` fix, so one line-based rewrite there serves `init --upgrade`, `doctor` and
`doctor --fix` at once. One helper in `workspace.py` names where the effective posture
comes from, and `config check` and the `doctor` posture row both print it. The template
reorders `[security]`; two docs pages change a few sentences. No new module, no schema
change, no change to `posture()` or any guard.

## Technical Context

Python 3.11 stdlib only (`copy`, `re`, `tomllib`). Tests: pytest, in process, existing
fixtures: `tests/test_posture.py::checked`, `tests/test_doctor.py::ws`,
`tests/test_setup.py` (`project`, `host`, `terminal`, `run_setup`), and the in-process
`init.run(SimpleNamespace(path=..., upgrade=..., dry_run=...))` pattern of
`tests/test_config_transition.py::upgrade_output`.

## Constitution Check

- I stdlib only: yes. II exits: a rewrite the line edit cannot verify exits 2 with the
  reason and writes nothing (the existing `ValueError` path of `upgrade`).
- III one behaviour one function: the rewrite lives only in `init._retired_mode`; the
  posture source only in `workspace.posture_source`.
- IV test first: tasks.md orders each test before its code.
- V ponytail: reuse `_sections`, the `_stamp` value regex and the existing
  `init-upgrade` fix; no migration framework, no schema removal.
- VII security: the rewrite never changes the effective posture (shadow was observe and
  stays observe); `config.toml` stays a protected record, written only by the owner's
  `init --upgrade` or `doctor --fix`.

## Design

### 1. `cli/wuwei/workspace.py`

Add next to `posture` (do not change `posture` itself or `SCHEMA`):

```python
def posture_source(config):
    """The key the effective posture comes from (#355); guards.mode is retired."""
    return ('guards.mode = "shadow", deprecated; run doctor --fix'
            if config['guards']['mode'] == 'shadow' else 'security.posture')
```

### 2. `cli/wuwei/commands/config.py` (`run`, lines 78-94)

- Line 79 becomes
  `print(f'Posture: {name} (from {workspace.posture_source(config)})')`.
- Delete the `if config['guards']['mode'] == 'shadow':` block (lines 92-94). Exit code
  unchanged.

### 3. `cli/wuwei/commands/doctor.py` (`_calibration`, lines 318-328)

```python
guards, name = config['guards'], workspace.posture(config)[0]
shown = f'{name} (from {workspace.posture_source(config)})'
if guards['mode'] == 'shadow':
    rows.append(_row('workspace', 'posture', 'warn', shown, 'wuwei init --upgrade',
                     apply='init-upgrade'))
elif name != 'observe':
    rows.append(_row('workspace', 'posture', 'ok', shown))
else:
    # today's days computation, unchanged
    rows.append(_row(..., 'ok', f'{shown}, {left} days left') if left > 0 else
                _row(..., 'warn', f'{shown}: ' + SHADOW_NUDGE.format(days=days), <same fix>))
```

The deprecated row carries no day count: after the fix the next `doctor` shows it. The
`init-upgrade` fix is also offered by the `template` row (section 4); `fix` dedupes ids.

### 4. `cli/wuwei/commands/init.py`

New function after `_without_empty_repos`:

```python
def _retired_mode(raw):
    """#355: guards.mode = "shadow" becomes security.posture = "observe"; "enforce" (the
    default) is dropped. shadow_since, shadow_days and every other line stay."""
```

- `mode = tomllib.loads(raw).get('guards', {}).get('mode')`; `None` returns `(raw, [])`.
- `sections = _sections(raw)`; in each section labelled `'guards'` drop lines matching
  `r'\s*mode\s*='`. When `mode == 'shadow'`, in the section labelled `'security'` replace
  the value of the first line matching `r'\s*posture\s*='` with the same regex `_stamp`
  uses: `re.sub(r'=\s*("[^"\n]*"|\'[^\'\n]*\')', '= "observe"', line, count=1)`, keeping
  any trailing comment.
- Verify: `expected = deepcopy(tomllib.loads(raw))`; pop `expected['guards']['mode']`; if
  shadow set `expected['security']['posture'] = 'observe'`; if
  `tomllib.loads(result) != expected` raise `ValueError('cannot safely retire guards.mode
  in this TOML layout; set security.posture = "observe" and delete guards.mode')`. Any
  missing table (an unreachable layout) also lands here, not in a `KeyError`: build the
  check so it raises the `ValueError`.
- Return `(result, [line])` with line
  `'guards.mode = "shadow" becomes security.posture = "observe"'` or
  `'remove guards.mode = "enforce" (the default)'`.

In `upgrade` (lines 258-260 and 290-303):

- `migrated, added = _migrated_config(text, template)`, then
  `migrated, retired = _retired_mode(migrated)`, then `_stamp` as today. The order
  matters: migration first guarantees a `[security]` `posture` line exists (it adds the
  template's `guarded` line when missing), and the rewrite then sets it to `observe`.
- After the `for key in added:` loop: `for line in retired: print(f'{prefix} config.toml:
  {line}')`.
- The `No workspace changes needed` condition gains `and not retired`.
- `config_changed` already covers the write (`migrated != raw`).

`run` (new workspace) does not change. Its `'posture = "guarded"'` replace (line 93)
must still hit the key, so no template comment may contain that literal text.

### 5. `templates/workspace/config.toml` (lines 227-232)

```toml
[security]
# observe: guards record what they would refuse and let the call through; records and owner-only actions still refuse. setup --shadow starts here.
# guarded: the default. Records, publishing and integrity block; MCP findings, outward text and seat launches warn.
# strict: every area blocks, and unknown config keys are errors.
posture = "guarded" # The posture table and its floors are in the security docs.
required = true
# Per-area overrides of the posture: off, warn or block. records always blocks.
# [security.areas]
# mcp = "off" # integrity, mcp, publish, records, outward, seats
```

`[guards]` is unchanged (no `mode` line today). Comment lines must not match the
`test_every_template_config_key_is_documented` key regex (`# word =`).

### 6. Docs

- `docs/site/configuration.md`
  - `guards.mode` row (line 39): `Retired. init --upgrade and doctor --fix rewrite
    "shadow" to security.posture = "observe" (keeping guards.shadow_since and
    guards.shadow_days) and remove "enforce". Until then "shadow" still means observe,
    and config check and doctor show posture: observe (from guards.mode = "shadow",
    deprecated; run doctor --fix).` (with the usual backticks).
  - `security.posture` row (line 43): add that `setup --shadow` and `init --shadow` set
    `observe` for `guards.shadow_days` days from `guards.shadow_since`, then one nudge
    asks to switch to `guarded`; `config check` and `doctor` print the effective posture
    and its source.
- `docs/site/security.md`
  - Line 48: `config check` prints the effective table and the key it comes from.
  - Line 65: replace the last sentence (`guards.mode = "shadow"` counts as observe) with
    `setup --shadow` and `init --shadow` write `observe`.
  - Line 71 (`observe` bullet): `setup --shadow` starts it; observe for
    `guards.shadow_days` days, then one nudge asks you to switch to `guarded`.

## What must not change

- `workspace.posture` and `SCHEMA['guards']['mode']`: a config not yet upgraded loads and
  runs observe exactly as today, in every posture (removing the key would make it an
  unknown key that `strict` refuses, #353).
- `setup.py`, `interview.py`, `profiles.py`, `status.py`, `next.py`, the hook and every
  guard: untouched.
- `_migrated_config`, `_stamp`, `_without_empty_repos` and their output lines.
- `config check` exit codes; the area table lines, the floor and `scanner.mcp.block`
  lines.
- `doctor.FIXES` and the fix flow: the rewrite rides on `init-upgrade`.

## Tests that change

- `tests/test_posture.py::test_config_check_prints_posture`: `Posture: guarded (from
  security.posture)\n`; the shadow case expects the deprecated source line, one line
  with `deprecated`, and no separate `set security.posture = "observe"` line.
- `tests/test_doctor.py::test_workspace_rows_healthy`: posture value
  `guarded (from security.posture)`.
- `tests/test_doctor.py::test_workspace_calibration_and_shadow`: `observe (from
  security.posture), 4 days left`; the nudge value starts `observe (from
  security.posture)` and keeps `8 days`, its fix and no `apply`; the alias case is
  `warn` with `apply == 'init-upgrade'`; strict is `strict (from security.posture)`.

## Project Structure

```text
cli/wuwei/workspace.py          posture_source
cli/wuwei/commands/config.py    one posture line
cli/wuwei/commands/doctor.py    posture row
cli/wuwei/commands/init.py      _retired_mode, upgrade output
templates/workspace/config.toml [security] order and comments
docs/site/configuration.md, docs/site/security.md
tests/test_posture.py, tests/test_doctor.py, tests/test_workspace.py, tests/test_setup.py,
tests/test_docs.py
```

# Implementation Plan: First-day docs after the fix wave (#340)

**Branch**: `340-docs-first-day` | **Spec**: [spec.md](spec.md)

## Summary

Docs only. Close the gaps spec.md lists: doctor in the README and index first-day path,
three new "What ships today" bullets, a first-week observe line in Limits, doctor at the
top of the daily path, `config set` instead of hand edits, a nine-entry troubleshooting
section in `recovery.md`, and a test that pins the `security.md` posture table to the code.
Every behaviour gets a test in `tests/test_docs.py` first.

## Technical context

- Files changed: `tests/test_docs.py`, `README.md`, `docs/site/index.md`,
  `docs/site/daily.md`, `docs/site/recovery.md`, `docs/site/configuration.md`.
- Shared helpers reused: the `SITE` and `ROOT` constants and the section-split idiom
  (`text.split('\n## X\n', 1)[1].split('\n## ', 1)[0]`) already used in `tests/test_docs.py`;
  `workspace.AREAS`, `workspace.POSTURES`, `workspace.FLOORS`, `workspace.SCHEMA`
  (`cli/wuwei/workspace.py:38-58`) as the single source for the posture test. No new
  helper, no new page, no new fixture.
- Must not change: any code under `cli/`, `adapters/`, `hooks/`; `.github/workflows/*`;
  `scripts/build-hero.py` and `docs/assets/hero-*.svg` and the README hero alt text (the
  stations did not change); `reference.md`, `concepts.md`, `docs/integrity.md`,
  `remote.md`, `security.md` text (the posture test pins today's text); every existing
  assertion in `tests/test_docs.py` (extend, never loosen). The latency phrases pinned by
  `test_reference_states_hook_latency_budget` and `test_readme_lead_and_limits` stay.
- Writing: humanizer checklist on every new sentence (`humanizer:humanizer`, embedded
  mode); short sentences; no em-dashes, no emojis; no "professional"; no
  self-deprecation; no client or repository name from the trial report and no absolute
  local path.

## Constitution check

- I (stdlib): tests use only stdlib and pytest. Pass.
- III (one behaviour, one test): each doc behaviour has one test function. Pass.
- IV (test first): every page task follows its failing test; the posture test is a pin
  over correct text and is shown to bite by a local mutation. Pass.
- V (ponytail): troubleshooting goes into the existing recovery page; no new page or
  helper; four existing tests are extended rather than duplicated. Pass.

## Tests (all in `tests/test_docs.py`)

### Test 1: extend `test_readme_first_day_and_shipped_areas`

- Steps become `('setup --shadow', 'bin/wuwei doctor', '/wuwei plan')` for both the README
  Quick start and the index Start here (the loop already covers both).
- Add to the What ships today link tuple: `docs/site/daily.md#2-configure`,
  `docs/site/reference.md#doctor`, `docs/site/security.md#security-posture`.
- Fails today: `'bin/wuwei doctor'` is not in either section.

### Test 2: extend `test_readme_lead_and_limits`

- Add `'setup --shadow'` and `'observe'` to the Limits phrase tuple (the check lowercases
  and flattens).
- Fails today: Limits has neither.

### Test 3: new `test_troubleshooting_covers_the_first_run_findings`

```python
TROUBLESHOOTING = (  # the 0.11.0 trial findings B1 to B9, in order
    ('.in_use', 'bin/wuwei integrity check'),
    ('not attached (unapproved)', 'bin/wuwei mcp decide proceed-unmeasured'),
    ('does not load', 'bin/wuwei config check'),
    ('delete that line before using [[repos]] tables', 'bin/wuwei init --upgrade'),
    ('by hand', 'bin/wuwei config set'),
    ('fast_checks = []', 'bin/wuwei config promote'),
    ('CI only', 'bin/wuwei calibrate --measure'),
    ('none visible (404: unprotected or no admin)', 'bin/wuwei config check'),
    ('read-only', 'bin/wuwei why last refusal'),
)


def test_troubleshooting_covers_the_first_run_findings():
    from wuwei import integrity
    section = (SITE / 'recovery.md').read_text().split('\n## Troubleshooting\n', 1)[1].split('\n## ', 1)[0]
    assert re.search(r'bin/wuwei [a-z-]+', section)[0] == 'bin/wuwei doctor'
    entries = [' '.join(entry.split()) for entry in section.split('\n### ')[1:]]
    assert len(entries) == len(TROUBLESHOOTING)
    for entry, (symptom, command) in zip(entries, TROUBLESHOOTING):
        assert symptom in entry and command in entry, (symptom, command)
    assert integrity.MARKERS == '.in_use'
```

Fails today: no `## Troubleshooting` in `recovery.md` (IndexError).

### Test 4: extend `test_doctor_is_the_first_stop`

```python
    daily = (SITE / 'daily.md').read_text()
    first = daily.split('\n## 1. ', 1)[1].split('\n## ', 1)[0]
    assert first.index('setup --shadow') < first.index('bin/wuwei doctor')
    flat = ' '.join(daily.split())
    for key in ('security.posture', 'guards.shadow_days', 'owner.timezone', 'metrics.band_margin',
                'sessions.rotate_after'):
        assert f'bin/wuwei config set {key}' in flat, key
    assert '"guarded"` in `config.toml`' not in flat
    intro = (SITE / 'configuration.md').read_text().split('\n## Sections\n', 1)[0]
    assert 'bin/wuwei config set' in intro and 'bin/wuwei config add-repo' in intro
```

Fails today: doctor is in section 2, not section 1.

### Test 5: new `test_security_posture_table_matches_the_code`

```python
def test_security_posture_table_matches_the_code():
    from wuwei import workspace
    page = (SITE / 'security.md').read_text()
    section = page.split('\n## Security posture\n', 1)[1].split('\n## ', 1)[0]
    rows = [[cell.strip() for cell in line.strip().strip('|').split('|')]
            for line in section.splitlines() if line.startswith('|')]
    default = workspace.SCHEMA['security']['posture'][1]
    names = [cell.removesuffix(' (default)') for cell in rows[0][2:]]
    assert names == list(workspace.POSTURES) and f'{default} (default)' in rows[0]
    table = {row[0].strip('`'): row[2:] for row in rows[2:]}
    assert table == {area: [workspace.POSTURES[name][area] for name in names] for area in workspace.AREAS}
    flat = ' '.join(section.split())
    for area, level in workspace.FLOORS.items():
        assert f'`{area}` always {level}s' in flat, area
    block = ', '.join(workspace.SCHEMA['scanner']['mcp']['block'][1])
    assert f'`scanner.mcp.block` (default `{block}`)' in flat
    ziran = ' '.join(page.split('\n## ZIRAN integration\n', 1)[1].split('\n## ', 1)[0].split())
    for phrase in ('By default only a critical finding or a check that could not run blocks launches',
                   'never starts an unapproved project server', '`uvx`, `npx` or `pipx run`'):
        assert phrase in ziran, phrase
```

Passes today (a pin). Change one cell (for example `seats` guarded to `block`) locally,
see it fail, restore.

## Page changes

### `README.md`

- Quick start, after the `--shadow` paragraph (line 106), add a doctor step:
  a sentence, a `sh` block with `../wuwei-plugin/bin/wuwei doctor`, and one sentence:
  it prints a row per check with the fix for anything not ok, and `bin/wuwei doctor --fix`
  applies the deterministic fixes after one confirmation
  ([doctor](docs/site/reference.md#doctor)). Leave the rest of the section; `config set`
  must stay in it.
- What ships today, three bullets after the day-loop bullet:
  - setup: one command finds the repositories, calibrates, asks the owner interview and
    applies one proposal after a digest ([setup](docs/site/daily.md#2-configure));
  - doctor: install, host, workspace, gate, day and guard problems with their fixes
    ([doctor](docs/site/reference.md#doctor));
  - security posture: observe, guarded or strict per area, with floors no setting lowers;
    the MCP registry gate warns by default and blocks a critical finding or a check that
    could not run ([security posture](docs/site/security.md#security-posture)).
- Limits: one bullet: start a new project with `setup --shadow`, a first week in the
  observe posture, so the guards record what they would refuse before they refuse it
  (link `docs/site/security.md#security-posture`).

### `docs/site/index.md`

- Start here: after the setup paragraph, add the doctor step (same wording as the README,
  `bin/wuwei doctor`, link `reference.html#doctor`), before the `/wuwei plan` sentence.
- Page list: Recovery line becomes "doctor first, troubleshooting for first-day failures,
  and low-level commands for when evidence and state disagree" (shorter if it reads better).

### `docs/site/daily.md`

- Section 1, after the setup paragraph: "Then run `bin/wuwei doctor` ..." (moved from
  section 2, lines 64-66; delete it there). Mention `doctor --fix` and link
  [troubleshooting](recovery.html#troubleshooting).
- Lines 73-75: the switch to guarded becomes
  `bin/wuwei config set security.posture '"guarded"'`, or raise `guards.shadow_days` with
  `bin/wuwei config set guards.shadow_days 14`.
- Lines 184-185: "Set them with `bin/wuwei config set` in a host terminal", with
  `owner.timezone '"Europe/Lisbon"'`, `metrics.band_margin 0.3` and
  `sessions.rotate_after.turns 200` as examples. Each shows a diff and applies after its
  digest. (All five keys were checked against the shipped template: each reaches the
  digest prompt.)

### `docs/site/configuration.md`

- Line 9: replace "Edit it in the workspace root." with: change one value with
  `bin/wuwei config set <key> <value>` and add a repository with
  `bin/wuwei config add-repo` in a host terminal (see [calibration](#calibration)); edit
  the file by hand only for what they refuse, a table or a value that spans lines.

### `docs/site/recovery.md`

- Replace the doctor paragraph (lines 14-16) with `## Troubleshooting`. It opens with
  `bin/wuwei doctor` and `doctor --fix`, says the entries below are first-day recovery
  (the word "recovery" must be in the section, see spec Edge Cases), then nine `###`
  entries in this order. Each: what the owner sees, what changed in 0.12.0 where it
  matters, the command. Two to four sentences each.

  1. `### Every tool call refused with plugin integrity`: 0.11.0 counted Claude Code's
     `.in_use` process markers in the plugin directory as tampering; 0.12.0 skips them
     (only files named by a process id directly in the install root's `.in_use/`; another
     name, a directory, a symlink or a deeper `.in_use` is still a finding, see the
     integrity doc on GitHub). Install the new release, run
     `bin/wuwei init --upgrade`; if it still pages, `bin/wuwei integrity check` names the
     files. Doctor's `in_use` row counts the markers.
  2. `### The MCP gate blocks or names a server unmeasured`: `bin/wuwei mcp check` reports
     each server: `not attached (unapproved)` is never started, an `unpinned launcher` is
     not run, an unreachable or slow server is unmeasured by name. Under `guarded` only a
     critical finding or a check that could not run blocks; an unmeasured server is a
     nudge. Accept one with `bin/wuwei mcp decide proceed-unmeasured <server>`; give a slow
     one more time with `scanner.mcp.timeout_seconds`.
  3. `### config.toml does not load`: every tool is refused with the error except
     `ToolSearch` and `Read`, `Grep` and `Glob` of `.wuwei/config.toml`, so the session can
     show the line. `bin/wuwei config check` names the key, the line and the fix.
  4. `### repos = [] next to [[repos]] tables`: the error ends with "repos is assigned on
     line N; delete that line before using [[repos]] tables". `bin/wuwei init --upgrade`
     removes the line (`doctor --fix` offers it). The template no longer ships it.
  5. `### Changing one value`: `bin/wuwei config set <key> <value>` and
     `bin/wuwei config add-repo --name --path --branch` show a diff and apply after a
     digest; edit by hand only a table or a value that spans lines.
  6. `### fast_checks stays empty after promote`: 0.11.0 left `fast_checks = []` alone;
     a one-line empty list is now filled by `bin/wuwei config promote`.
  7. `### A test suite proposed as a fast check`: test runners are CI only unless
     measured; `bin/wuwei calibrate --measure` times them against
     `calibrate.fast_check_seconds` ([calibration](configuration.html#calibration)).
  8. `### Branch protection reads as unmeasured`: a 404 on the classic endpoint means the
     branch is unprotected or you lack admin; `bin/wuwei config check` now prints
     `classic protection: none visible (404: unprotected or no admin)` and reads the
     rulesets.
  9. `### A read-only shell command was refused`: from 0.12.0 a `for` loop, `$(...)` or
     `git symbolic-ref` that only reads is not refused, and outside a workspace every hook
     allows. If a refusal is left, `bin/wuwei why last refusal` prints the guard, the rule,
     the command and the fix; under `observe`, `bin/wuwei shadow report` lists what would
     have been refused.

  Write the symptoms generically; nothing from the trial report's client, repository or
  host names.

## Deferred

- `cli/wuwei/commands/doctor.py:262-271` and `:322` still print hand edits for
  `repos.N.identity` and `security.posture` (its ponytail comment waits for `config set`,
  which shipped in #327). Code, not this docs issue: a follow-up can switch those fix lines
  to `bin/wuwei config set`.
- The hero: unchanged; the PR body says the stations still match (Calibrate and the
  interview are what setup runs).

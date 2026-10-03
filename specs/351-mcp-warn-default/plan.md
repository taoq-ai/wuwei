# Implementation Plan: MCP findings warn by default under guarded, block only under strict

**Branch**: `351-mcp-warn-default` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

The posture table already says `mcp = warn` under guarded; the default `scanner.mcp.block =
["critical"]` overrides it through the guarded floor in `mcp.cached`. Fix it at the shared
spot: the default becomes `[]` and the template drops the key. Every consumer (`plan.propose`,
`agent_launch.check_mcp`, the runtime adapters through `mcp.launch`, `doctor`, `setup`) already
routes through `mcp.cached`, so no caller changes for the warn. Strict keeps its existing union
(`critical`, `high`, `unmeasured`). Then three small visibility edits: one summary helper in
`mcp.py` for the exit-1 reason, `plan.propose` prints the check's reason when it proceeds, and
the `mcp.finding` attention row shows the finding and the command. `config check` prints one
line about a non-empty `scanner.mcp.block`.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. No new module, no new config key, no new event
kind, no new state key. The posture area table (`workspace.POSTURES`) stays the single
source; no second mode flag.

## Constitution Check

- I stdlib: yes.
- II fail closed: a registry check that could not run still blocks under guarded and strict
  (`_gate` line 277-278 unchanged, the `cached` floor note unchanged); strict still blocks
  `unmeasured`. Only measured findings and unmeasured servers stop blocking by default under
  guarded, which is the owner's ruling (spec A1, A4).
- III one behaviour, one function: the default lives in `SCHEMA`; the summary in one helper
  `mcp._summary`; the posture decision stays in `mcp.cached`.
- IV test first: tasks.md orders every test before its code.
- V ponytail: one default changed, one helper, three small call-site edits, docs.
- VII security: tool names never reach the board (A10); scanner text on the board is limited
  to values matching `mcp.NAME`.

## Design

### 1. Default: `cli/wuwei/workspace.py`

Line 55-56, the `block` schema default `["critical"]` becomes `[]`:

```python
"block": [(str, None, ("critical", "high", "medium", "low", "unmeasured")), []]}},
```

Nothing else in `workspace.py` changes. Effect through `mcp.cached` (unchanged code):

| posture (mcp level) | default list | finding pending | unmeasured server | check could not run |
| --- | --- | --- | --- | --- |
| observe (warn) | ignored | 0 | 0 | 0 |
| guarded (warn) | `[]` | 0 | 0 | 2 |
| strict (block) | `critical, high, unmeasured` | 1 for critical/high | 2 | 2 |

### 2. Template: `templates/workspace/config.toml`

Lines 108-109 become comments only (no `block` key):

```toml
# Launch gate override: critical, high, medium, low or unmeasured. Unset, the posture decides:
# observe and guarded block no finding; strict blocks critical, high and unmeasured.
# A check that could not run blocks under guarded and strict.
# block = ["critical"]
```

`init --upgrade` (`_migrated_config`) adds only keys present in the template, so nothing is
added to existing workspaces, and their explicit `block = ["critical"]` stays (spec A6).

### 3. Summary helper: `cli/wuwei/mcp.py`

- Constant next to `NOT_CHECKED` (line 19): `DECIDE = 'bin/wuwei mcp decide'`.
- New helper above `_result` (line 268):

  ```python
  def _summary(record):
      """One line for a pending finding batch (#351): what was found and the command."""
      return (f"MCP registry findings ({', '.join(record['severities'])}) await review in "
              f"{record['pending']}: run {DECIDE}")
  ```

- `_result` line 271: the code-1 branch returns `_summary(record)` instead of
  `'MCP registry findings: owner decision required in ' + record['pending']`.
- `_gate` line 280: `return registry.Result(1, reason=_summary(record))`.

`cached` then appends its existing posture note, so a strict refusal reads
`MCP registry findings (critical) await review in .wuwei/days/<date>/decisions/D-1.md: run
bin/wuwei mcp decide (mcp: block, security.areas.mcp)`. `record['severities']` is always set
(`_read` defaults a v0.11.0 record to every severity) and `record['pending']` is always set
when code is 1 (exit 1 means a high or critical finding, which always queues).

### 4. `plan propose` prints: `cli/wuwei/plan.py`

Add `import sys`. After the gate check (line 116-117), before the sweep line:

```python
    if measured.exit:  # #351: a finding the posture warns on is printed, not only filed.
        print(measured.reason, file=sys.stderr)
```

stdout stays the plan path (`commands/plan.py:48`). The sweep line (line 118) is unchanged and
now carries the summary.

### 5. Board row: `cli/wuwei/commands/status.py`

In `scan`, next to the `guard.would_refuse` reason (line 131-133), add:

```python
                    if kind == 'mcp.finding' and isinstance(payload, dict):
                        from wuwei.mcp import DECIDE, NAME
                        shown = [value if isinstance(value, str) and NAME.fullmatch(value) else 'unnamed'
                                 for value in (payload.get('severity'), payload.get('drift_type'),
                                               payload.get('server_name'))]
                        reason = 'MCP {} {} finding on {}: run '.format(*shown) + DECIDE
```

The lazy import keeps `status --line` fast when there is no finding. The row key, tier and the
`mcp.checked` exit-0 clearing (line 62-64) are unchanged. `wuwei_board` (`commands/board.py`,
Attention table) and the dashboard read these rows; no change there.

### 6. `config check`: `cli/wuwei/commands/config.py`

In `run`, after the posture rows and the owner-only line (line 81-82), before the
`guards.mode` deprecation line:

```python
    block = config['scanner']['mcp']['block']
    if block:
        ignored = levels['mcp'] == 'off' or name == 'observe' and levels['mcp'] == 'warn'
        print(f'  scanner.mcp.block ({", ".join(block)}): ' + (
            f'no effect under {name} (mcp: {levels["mcp"]}); remove the key' if ignored else
            f'blocks launches at these severities on top of the {name} default'))
```

Reported, not a finding: the exit code does not change.

### 7. Skill wording: `skills/wuwei-plan/SKILL.md`

Lines 14 and 16 say the refusal is what "`scanner.mcp.block` decides" / "blocks". Change both
phrases to "the security posture decides (`security.areas.mcp`, `scanner.mcp.block`)", and in
line 14 add after "Exit 1 means registry findings await an owner decision.": "Under observe
and guarded the day proceeds; show the owner the one-line reason, which names the decision
and the command." Nothing else in the skill changes (the decide flow is #354).

### 8. Docs

- `docs/site/security.md` line 15: replace "By default only a critical finding or a check
  that could not run blocks launches; an unmeasured server is a nudge named in every brief.
  `scanner.mcp.block` makes the gate stricter." with: the security posture decides; under
  `observe` and `guarded` (the default) every finding warns (it is recorded, shown in the plan
  sweep, on the board and in what the planner relays, with `bin/wuwei mcp decide`) and
  launches proceed; `strict` blocks critical, high and unmeasured until `mcp decide`; a
  check that could not run blocks under guarded and strict; `scanner.mcp.block` overrides.
- `docs/site/security.md` line 63 (MCP floor bullet): "MCP: under `guarded` and `strict` a
  registry check that could not run blocks launches whatever `security.areas.mcp` says,
  unless it is `off`. A finding blocks only at a severity in `scanner.mcp.block`, which is
  unset by default (no severity under guarded; `critical`, `high` and `unmeasured` under
  strict). Under `observe`, and with `mcp = "off"`, the list has no effect and `config check`
  says so."
- `docs/site/security.md` line 68 (guarded): "MCP findings below the floor warn" becomes "MCP
  findings warn".
- `docs/site/concepts.md`, `## Security posture` (after line 21): one paragraph: why MCP
  findings warn by default: a registry finding is a heuristic over tool descriptions, and a
  first measurement is new information, not drift; the publishing guarantee does not rest on
  the registry gate but on the code host protections and the credential layout (design 9.1),
  so a false positive must not stop the day; `strict` is for a repository where a changed
  tool must stop seats until the owner decides.
- `docs/site/configuration.md` line 393-398: `scanner.mcp.block` (unset by default; the
  posture decides: observe and guarded none, strict `["critical", "high", "unmeasured"]`).
  Remove the "(default `["critical"]`)" claim; keep the `[]` and v0.11.0 sentences adjusted;
  add: a workspace created before #351 carries `block = ["critical"]` from the old template;
  delete the line to take the posture default.
- `docs/site/recovery.md`, under `## Other recovery` (line 47): a short entry "An MCP finding
  on a server you installed yourself": under guarded the day proceeds and the finding stays on
  the board until `bin/wuwei mcp decide`; under strict review the report and decide; a
  `tool_redirect` hit on a description that points to a sibling tool of the same server is a
  known scanner heuristic issue, https://github.com/taoq-ai/ziran/issues/447. WUWEI reports
  the severity the scanner gives.
- `docs/specs/2026-09-24-wuwei-design.md` line 859-861 (S3 amendment): append "Amendment
  (owner, 2026-10-03, #351): the default list is empty; the security posture decides (strict
  blocks critical, high and unmeasured)." Line 984: same text as the security.md bullet.

## What must not change

- `mcp.check` (queuing, `queued` set, events, notes, `_recover`, `_backup`), `_queue`,
  `_cached`, `_gate` line 277-278 (could-not-run and unmeasured), `cached` (body unchanged),
  `decide`, `_proceed_unmeasured`, `launch`, `discover`.
- `adapters/scanner/ziran.py`; signal tiers (`mcp.finding` high/critical stays a page);
  `hook.posture`; `guards.AREAS`; `agent_launch`; `workspace.POSTURES` and `posture()`.
- `setup` and `doctor` code (they read `mcp.check`/`mcp.cached` and pick up the change).
- No `init --upgrade` rewrite (spec A6, #355).

## Existing tests that change

- `tests/test_workspace.py:145`: default `block` is `[]`.
- `tests/test_mcp.py` `test_posture_block_table` (line 808-848): row
  `(None, 'legacy-pending', None, 1, 1)` becomes `(None, 'legacy-pending', None, 0, 1)` (guarded
  warns, strict blocks). Add a row `(None, 'critical', 1, 0, 1)` (the trial case under the
  default list).
- `tests/test_mcp.py` line 545-546: the template no longer has `block = ["critical"]`; set the
  list with `.replace('timeout_seconds = 60', 'timeout_seconds = 60\nblock = ["high", "critical"]')`.
- `tests/test_doctor.py` line 393-394: under the default posture the `mcp gate` row for a
  pending critical record is `ok`; assert that, then write `[security]\nposture = "strict"\n`
  and assert `fail`.
- Any other test that relied on the `critical` default blocking (find them with the full
  suite) pins strict or an explicit list, never loosens an assertion.

## Project Structure

```
cli/wuwei/workspace.py            scanner.mcp.block default []
templates/workspace/config.toml   [scanner.mcp] block removed, per-posture comment
cli/wuwei/mcp.py                  DECIDE, _summary(); _result and _gate use it
cli/wuwei/plan.py                 print the check reason on stderr when proceeding
cli/wuwei/commands/status.py      mcp.finding attention row reason
cli/wuwei/commands/config.py      scanner.mcp.block line in the Posture section
skills/wuwei-plan/SKILL.md        posture decides; relay the reason under observe/guarded
docs/site/{security,concepts,configuration,recovery}.md, design spec S3 and 9.1
tests/test_mcp.py, tests/test_posture.py, tests/test_workspace.py, tests/test_doctor.py
```

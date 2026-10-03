# Data model: registry records after #325

All files live under `.wuwei/ziran/`, which `protect_state` already reserves for the
registry producer (`wuwei mcp check`, `wuwei mcp decide`).

## `status.json` (mode 0o444, written by `check` and `decide`)

Existing fields keep their meaning: `exit` (measurement 0/1/2), `day`, `generation`,
`pending` (decision path or null), `reports`, `reason`.

| Field | Type | Meaning | Default when absent (v0.11.0 record) |
| --- | --- | --- | --- |
| `severities` | list over `critical`, `high`, `medium`, `low` | Severities in the undecided finding batch(es) behind `pending`; empty when nothing is pending | all four (blocks as before) |
| `unmeasured` | list of `[name, digest]` | In-scope servers not measured this check and not owner-decided | `[]` |
| `decided` | list of `[name, digest]` | Servers not measured this check that an owner `proceed-unmeasured` decision covers | `[]` |

`name` matches `[A-Za-z0-9][A-Za-z0-9_.-]{0,127}`; `digest` is the 64-hex SHA-256 of the
server's one-server config body.

Derived states used by the gate (`_gate`):

- could not run: `exit == 2` and `unmeasured == []` (includes the `check incomplete`
  record written before scanning and every v0.11.0 exit 2 record). Always exit 2.
- per-server unmeasured: `unmeasured != []`. Exit 2 only when `block` has `unmeasured`.
- blocking findings: `pending` and `severities` intersects `block`. Exit 1.

## `accepted-<digest>.json` (mode 0o444)

Findings decisions keep `{decision, text, digest}`. A `proceed-unmeasured` decision adds
`servers`: the `[name, digest]` pairs it covers. `check` treats a still-unmeasured server
as decided only when its exact pair is listed, so a changed definition needs a new decision.

## `servers/<sha256(source path + NUL + name)>.json` (mode 0o600)

`{"mcpServers": {<name>: <entry>}}`, sorted keys, plugin `${CLAUDE_PLUGIN_ROOT}` expanded.
The only input the scanner receives. Its path is stable per (source, name), so the ZIRAN
adapter's snapshot directory (keyed on the file path) carries the baseline between checks.
Supersedes `plugins/*.json` (no longer written; old files are left in place).

## `mcp.decided` event

Findings: `{decision, outcome: "proceed"}` (unchanged). Unmeasured:
`{decision, outcome: "proceed-unmeasured", servers: [names]}`.

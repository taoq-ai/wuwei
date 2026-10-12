# Analysis: 860-codex-command-doctor

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | `test_host_rows_healthy` pins the host rows to five names; an always-present row would break the healthy view. | Resolved. The row appears only when it warns. |
| A2 | MEDIUM | "Calibration names the codex runtime" has no field of that name. | Assumed: a nonzero `budget.codex` window, the only codex-named setting of the calibration and window work. Recorded under Assumptions. |
| A3 | MEDIUM | The plugin alone raises the row, also on a claude-only day. | Intended by the issue ("or the companion is installed"); it is warn, not fail. |
| A4 | LOW | Plugin discovery could glob the plugin cache. | `installed_plugins.json` is the installed record and the scanner already reads it (`scanner.mcp.plugins_file`); a stale cache directory is not an install. |
| A5 | LOW | `config check` still flags an empty command only for `adapters.runtime = "codex"`. | Out of scope; doctor and the gate line carry it. |

Coverage: FR-001 and FR-002 T001-T002, FR-003 T003-T004, 100 percent.

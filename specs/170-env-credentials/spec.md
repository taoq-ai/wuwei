# Feature Specification: Workspace credentials

**Feature**: 170-env-credentials
**Created**: 2026-09-29
**Status**: Implemented
**Input**: Issue #170, workspace credentials and configuration diagnostics.

## User Scenarios & Testing

### User Story 1: Authenticate from the workspace (P1)

An operator keeps adapter credentials in a private workspace file so CLI commands,
hooks and background watch jobs can authenticate without shell setup.

**Independent test**: With LINEAR_API_KEY only in .wuwei/env, a recorded Linear
request receives the key and no output or persisted evidence contains its value.

**Acceptance scenarios**:
1. Given LINEAR_API_KEY only in .wuwei/env, when Linear runs, it authenticates.
2. Given a fresh or upgraded workspace, an empty private env file exists and is ignored by Git.
3. Given existing credentials, upgrade preserves their content.
4. Given invalid syntax, unreadable input or unsafe permissions, the operation exits 2
   with a value-free reason before any adapter runs.
5. Given an unrelated hook outside the workspace, it returns 0.

### User Story 2: Diagnose credential requirements (P1)

An operator runs config check to see each configured adapter's credential names
and set or missing status without disclosing values.

**Independent test**: Missing required credentials produce exit 1 and name the
missing requirement; populated requirements produce exit 0 without their values.

**Acceptance scenarios**:
1. Given missing credentials, config check names them and exits 1.
2. Given configured GitHub, Linear, Slack, Greptile, ICS and Codex adapters, the
   report covers gh auth, LINEAR_API_KEY, SLACK_BOT_TOKEN or SLACK_USER_TOKEN,
   SLACK_OWNER_DM_CHANNEL, GREPTILE_API_KEY, WUWEI_CALENDAR_URL and codex.command.
3. Given an unavailable GitHub tool or timeout, config check exits 2 with a reason.

### Edge Cases

Missing env files remain compatible with older workspaces. Empty values are
missing. Symlinks and nonregular files are refused. Parse errors never echo input.
Secret values in event keys, traces, command output and refusals are redacted.

## Requirements

- FR-001: Init and upgrade create .wuwei/env with mode 0600 and a Git ignore rule.
- FR-002: All entry paths load workspace credentials before invoking adapters.
- FR-003: File values remain private, including on failure and in watch logs.
  The existing state guard protects env against agent mutations like config.toml.
- FR-004: Config check reports requirements per configured adapter with exits 0/1/2.
- FR-005: Adapter documentation lists every required credential variable.

## Success Criteria

- SC-001: All supported entry paths authenticate using file-only credentials.
- SC-002: Missing requirements are named without any credential values in output.
- SC-003: Unsafe credential files cannot cause an adapter call.

## Assumptions

- Existing process environment wins, including explicit empty values.
- Syntax is literal KEY=value with blank lines and whole-line comments allowed;
  matching single or double quotes may surround a value. No expansion or execution.
- Missing files are allowed for backward compatibility; present files require 0600.
- Slack custom_app requires a bot token; connector identity accepts either token.
- Config check measures effective adapter defaults, including GitHub auth. It checks
  presence locally except for gh auth status, which uses the GitHub adapter.
- No new configuration keys are required. Existing calendar.url remains a legacy
  runtime fallback; configuration readiness requires WUWEI_CALENDAR_URL.

## Dependencies and Deferred

Builds on #121, #27 and existing shared scope, redaction, registry and atomic writes.
No work is deferred to another issue.

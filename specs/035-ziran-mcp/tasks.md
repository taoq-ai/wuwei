# Tasks: MCP audit and drift watch

## US1: Registration

- [X] T001 [US1] Write failing adapter contract and failure tests in tests/test_mcp.py.
- [X] T002 [US1] Implement watch-registry calls in adapters/scanner/ziran.py.
- [X] T003 [US1] Write failing discovery and init/upgrade tests in tests/test_mcp.py.
- [X] T004 [US1] Implement discovery and registration in cli/wuwei/mcp.py, cli/wuwei/workspace.py and cli/wuwei/commands/init.py.

## US2: Morning checks and launch gates

- [X] T005 [US2] Write failing morning drift, stale/error status and launch tests in tests/test_mcp.py.
- [X] T006 [US2] Implement checks in cli/wuwei/plan.py, cli/wuwei/guards/agent_launch.py and runtime adapters.

## US3: Evidence and decisions

- [X] T007 [US3] Write failing protection, redaction and owner-decision tests in tests/test_mcp.py.
- [X] T008 [US3] Implement decision command, reserved state/events and protection in cli/wuwei/mcp.py, cli/wuwei/commands/mcp.py and existing shared guards.

## Final verification

- [X] T009 Document config defaults and morning workflow in templates/workspace/config.toml and skills/wuwei-plan/SKILL.md.
- [X] T010 Run full suite and hygiene checks; record results in specs/035-ziran-mcp/tasks.md.

## Dependencies and execution

T001 through T010 run sequentially. Every behavior's test precedes its code.
US2 and US3 depend on US1; no parallel agent work is needed. The full scope is the
minimum useful release because scanning without enforced launch refusal is unsafe.


## Verification result

- Adapter contract: 18 failing tests against the old stub, then green.
- Core registration, morning gate and protections: 21 expected failures, then green.
- Added regression failures for snapshot rollback, interrupted recovery cleanup,
  accumulated report references, nonblocking visibility and shell relevance;
  each passed after the corresponding fix.
- PATH-stub integration verifies upgrade baseline, description drift at morning
  planning, metadata-only events and refusal before seat launch.
- Independent review and delta review covered snapshot durability, unresolved
  findings and shell relevance. Reported blockers have regression coverage.
- Full suite: `4924 passed, 3 skipped in 87.33s (0:01:27)`.
- `git diff --check` and changed-file hygiene scan passed. No commits or pushes.

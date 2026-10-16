# Feature Specification: the planner reads tracker measures into the lead's brief

**Feature branch**: `claude/planner-docs`
**Item**: planner-docs, tier full, goal G-2
**Input**: issue #1069. The lead could not read a goal measure kept in Linear ticket states,
because the lead has no tracker tools, and the suite command in AGENTS.md failed in a cloud image
where `python3` lacks pytest.

## The promise in my words

Docs only. The plan skill (`skills/wuwei-plan/SKILL.md`) gains a step before the lead is launched:
the planner reads each goal measure that `goals.md` states in a tracker's states (Linear, Jira)
with the MCP tools the planner's own session has, and writes the states, as read, into the lead's
brief. A measure the planner cannot read goes into the brief as unmeasured, with the reason. The
lead keeps its tool grant: tracker tool names differ per workspace, so they are not hard-coded into
the lead's charter. AGENTS.md and CONTRIBUTING.md say to run the suite with `python3 -m pytest -q`,
or `pytest -q` where python3 lacks the module. The vendored copy under `.claude/skills/` is
re-vendored. No runtime line changes.

The acceptance scenarios, restated:

1. `goals.md` states a measure in Linear ticket states: a planner following the skill reads them
   and the lead's brief carries the states as read, or names the measure unmeasured.
2. A seat in the cloud image follows AGENTS.md: `pytest -q` runs the suite.
3. The vendored-drift test passes against the re-vendored copy.

## Clarifications

### Session 2026-10-16

- Q: Does the planner read every measure, or only tracker ones? A: Only measures stated in a
  tracker's states. Other measures (CI, repository counts) the lead reads itself with gh and git.
- Q: Where does the step go? A: A new step 4, right before "Launch the lead", so the states exist
  when the brief is written. Later steps are renumbered; nothing refers to them by number
  (`grep -rn "step [0-9]" charters skills docs cli tests` finds none).
- Q: How is the step held by a test? A: Docs tests in `tests/test_setup.py` check that the skill
  names the tracker read before the launch step, with "own MCP tools", "unmeasured" and "lead's
  brief", and that AGENTS.md and CONTRIBUTING.md carry both suite commands.
- Q: Does the planner charter change? A: No. The skill is where the plan pass's steps live; the
  charter is out of the promise.

## User scenarios

### US1: the lead plans with tracker measures it cannot read itself (P1)

Acceptance 1. Test: `test_the_plan_skill_has_the_planner_read_tracker_measures_into_the_leads_brief`.

### US2: the suite runs where python3 lacks pytest (P1)

Acceptance 2. Test: `test_the_contributor_docs_run_the_suite_where_python3_lacks_pytest`.

### US3: the cloud copy follows the tree (P1)

Acceptance 3. Test: `test_the_vendored_plugin_matches_the_tree_it_was_copied_from`.

## Requirements

- FR-001: The plan skill tells the planner, before launching the lead, to read each goal measure
  stated in a tracker's states with its own MCP tools and put the states in the lead's brief.
- FR-002: A measure the planner cannot read is passed as unmeasured, with the reason.
- FR-003: AGENTS.md and CONTRIBUTING.md name `python3 -m pytest -q` and `pytest -q` as the fallback.
- FR-004: `.claude/skills/wuwei-plan/SKILL.md` is re-vendored with `setup.vendor('.')`.
- FR-005: No line changes under `cli/wuwei/`; the lead's charter and tool grant are unchanged.

## How this fails

1. The planner passes a stale or guessed state as if read, and the lead ranks on it. The step says
   "as you read them" and makes anything unread unmeasured, with the reason.
2. The planner's session has no tracker MCP tool, and the step reads as a blocker. The step names
   that case as unmeasured, so the pass goes on.
3. The skill copy in `.claude/` lags, so cloud planners never see the step. The vendored-drift test
   fails until it is re-vendored.

## Assumptions

- "Its own MCP tools" means whatever tracker tools the planner's session has; the skill names no
  tool. Overturned if the owner wants a configured tool name per workspace.
- Renumbering the later steps is safe, since nothing cites them by number.

## Success criteria

- SC-001: The two docs tests fail on main and pass at the head.
- SC-002: The full suite passes, with `cli/wuwei/` unchanged.

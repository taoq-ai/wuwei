Verdict: PASS
Gate: arch
Item: planner-docs
PR: taoq-ai/wuwei
Head: 5fb998ef12adaa6daac3b087e92e181fcac604df
Confidence: high
Breaking: no

## Findings
- [low] README.md:111 blocks: no. The Development block still shows only `python3 -m pytest -q`, with no `pytest -q` fallback. The promise names only AGENTS.md and CONTRIBUTING.md, so this is a follow-up, not a violation.
- [low] charters/lead.md:10 blocks: no. The lead charter does not say to use tracker states the planner hands it. Its existing "mark a source you cannot reach as unmeasured" fits the new step, and a brief is input the lead already reads, so nothing contradicts. Naming it in the charter would close the loop.
- [low] tests/test_setup.py:245 blocks: no. `skill.index('tracker')` anchors on the first "tracker" in the skill. A later edit that adds that word earlier would move the anchor, and the test fails loudly rather than passing silently.

## Probes
Diff origin/main...5fb998e (git diff --stat): 2 skill copies (identical hunks), AGENTS.md, CONTRIBUTING.md, tests/test_setup.py, specs/planner-docs/*. No runtime lines.
Citations of the renumbered steps: grep for "step N" in md/py/html/yml outside specs found none tied to wuwei-plan. charters/planner.md:8, charters/_way.md:6, skills/wuwei-watch/SKILL.md:27, README.md:56/87, docs/design.md:47, docs/site/concepts/the-day.md:32, docs/site/getting-started.md:50, hook.py:96 and __main__.py:73 cite `/wuwei-plan` by name only. The renumbering breaks nothing.
Lead boundary: agents/lead.md and .claude/agents/lead.md declare `tools: Read, Glob, Grep, Bash, Write`, with no MCP tools. This matches the skill's "The lead has no tracker tools", and the step keeps tool names out of the lead as the promise requires.
The `tracker` config key (ws.py:12, default github; reference.md:42) is separate from goals.md measures. The step does not read or redefine it, so it creates no contract change.
CI (.github/workflows/tests.yml:22-23) installs pytest and runs `python -m pytest -q`, so the doc fallback does not touch it. The fallback is additive.
Suite in an archive copy at the head: `python3 -m pytest -q` failed with "No module named pytest" in this image, which is exactly the case the item targets. `pytest -q` gave 464 passed.
Mutant 1 (removed step 4 from skills/wuwei-plan/SKILL.md): failed test_the_plan_skill_has_the_planner_read_tracker_measures_into_the_leads_brief and test_the_vendored_plugin_matches_the_tree_it_was_copied_from.
Mutant 2 (removed the fallback from AGENTS.md): failed test_the_contributor_docs_run_the_suite_where_python3_lacks_pytest.
The decision left open (what "its own MCP tools" means) is recorded under Assumptions in specs/planner-docs/spec.md:74.
Confidence is high because the change is docs only, every citation was checked with grep, and both new guards kill their mutants.

## Residual risk
Whether a planner actually reads Linear or Jira states depends on the session's MCP tools. No test can exercise that; only the brief wording is pinned.

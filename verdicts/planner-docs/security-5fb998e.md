Verdict: PASS
Gate: security
Item: planner-docs
PR: taoq-ai/wuwei
Head: 5fb998ef12adaa6daac3b087e92e181fcac604df
Confidence: high

## Findings
- [low] skills/wuwei-plan/SKILL.md:16 blocks: no. Tracker states are external data that now reach the lead's brief. The lead already takes the board (GitHub issues) and owner text, so this adds a source of the same kind, not a new trust class, and the step limits it to "states", not ticket bodies. The lead's tools are unchanged (Read, Glob, Grep, Bash, Write) and it has no tracker or outward tools. A later hardening could say to pass only the state names and to treat the ticket text as data, never as instructions.
- [low] blocks: no. The lead's brief is never persisted. But the lead's candidates (written to .wuwei/candidates.json, then plan.json `why`) can quote tracker states, and .wuwei/ syncs to the wuwei/state branch of a public repository (sync.LOCAL does not exclude these files). A private tracker's state names could appear there in public. The same was already true of anything the lead cites. The exposure is state names, not credentials. The planner reads through its own MCP session, so no token passes through the brief.

## Probes
- `git diff --name-only origin/main...5fb998e`: no change to agents/, charters/, settings, hooks or .mcp files. No tool grant changed, and cli/wuwei/ is untouched.
- Ran setup.vendor() from the head tree into a new scratch dir and ran `diff -r` against the head's .claude/. The only difference is settings.json, which init writes, not vendor(). The vendored copy matches.
- Mutant: reverted skills/wuwei-plan/SKILL.md to origin/main in a scratch copy. test_the_plan_skill_has_the_planner_read_tracker_measures_into_the_leads_brief and test_the_vendored_plugin_matches_the_tree_it_was_copied_from both fail.
- Full suite in a scratch copy at the head: `pytest -q` gave 464 passed. `python3 -m pytest` fails there with "No module named pytest", which is the case the docs change covers.
- `gh api repos/taoq-ai/wuwei --jq .visibility` returned public. sync.py LOCAL excludes only cache, traces.jsonl, executable, plan.html and canary.
- Confidence high: the change is docs only, grants are unchanged, the vendor diff is clean, and the mutant was killed.

## Residual risk
Prompt injection through tracker text depends on how faithfully the planner limits itself to state names. Private tracker state names can reach the public state branch through the lead's cited evidence.

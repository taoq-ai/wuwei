Verdict: PASS
Gate: goal
Item: planner-docs
PR: taoq-ai/wuwei
Head: 5fb998ef12adaa6daac3b087e92e181fcac604df
Confidence: high

## Findings
- [low] specs/planner-docs/spec.md:5 blocks: no. The spec's Input says issue #1069 also reports that the AGENTS.md suite command failed in the cloud image. The issue body says nothing about pytest; that half comes from the item's promise, not the issue. The delivered docs match the promise, so this is wrong attribution in the spec only.
- [low] blocks: no. Acceptance 1 is a planner behaviour, and only a docs test holds it (the step comes before "Launch the lead" and names "own MCP tools", "unmeasured" and "lead's brief"). No test shows a planner putting Linear states into a real lead brief. That waits for the next plan pass against G-4/G-6 style goals.

## Probes
- Issue #1069 (gh api repos/taoq-ai/wuwei/issues/1069): it offers two fixes, and the second is "the plan skill has the planner read every tracker-state measure the goals name and pass the result into the lead's brief before launching it". The new step 4 in skills/wuwei-plan/SKILL.md says exactly that, plus an unmeasured fallback with a reason, and leaves the lead's tool grant alone (git diff --stat origin/main...head -- cli agents charters is empty). This matches the item's Outside clause.
- Explain-back: "The promise in my words" in specs/planner-docs/spec.md matches the plan item's promise and its three acceptance scenarios (wuwei plan show planner-docs). No drift either way. The files touched are the four named, plus specs and tests.
- Cloud image fallback: `python3 -m pytest --version` gives "/usr/bin/python3: No module named pytest". `pytest --version` gives pytest 9.1.1 (uv tool at /root/.local/bin). `pytest -q` in a copy of the head tree: 464 passed. So the fallback text matches reality and acceptance 2 holds.
- Mutant 1, with skills/wuwei-plan/SKILL.md, AGENTS.md and CONTRIBUTING.md reverted to origin/main: both new docs tests fail, so they hold the change (SC-001).
- Mutant 2, with only .claude/skills/wuwei-plan/SKILL.md reverted to main: test_the_vendored_plugin_matches_the_tree_it_was_copied_from fails. At head it passes, so acceptance 3 holds.
- Renumbering: grep -rn "step [0-9]" charters skills docs cli tests at head finds no references by step number.

## Residual risk
The tracker read is a prose instruction. A planner session without tracker MCP tools gets unmeasured measures, which is the intended outcome, but nothing enforces that the brief actually carries the states.

Verdict: FIX
Gate: arch
Item: smart-tier
PR: taoq-ai/wuwei
Head: 5ce08929bbd1b2553a794097bd8105b9c3e17836
Confidence: medium
Breaking: no (minor: a new tier value, new optional flags --domain and --in-doubt, and a new default for an optional flag whose default the public API never documented)

## Findings
- [medium] cli/wuwei/evidence.py:48 blocks: yes. Failure: in a repository whose 28-day change failure rate is over 15 percent, a smart item marked in_doubt rises to standard and gates_for (evidence.py:343) takes REQUIRED['standard'], so the goal gate its doubt requires is dropped; the probe shows unraised "quality, goal" and raised "arch, quality, security", while a standard item raised in the same repo keeps goal. The error budget lowers a gate the item owed (requirement: promise "raise the gate set and never lower it", FR-002, design.md:155 "rises one step and takes its full gate set", the evidence.py:343 comment "an overrun budget trims nothing")
- [low] blocks: no. charters/planner.md:110 and docs/site/concepts/models.md:15,27 still list only light, standard and full for model and effort; a smart complex item gets the default (standard) seats through hook.advise, which looks up table.get(tier, table['']). This case is left out, not a break.
- [low] blocks: no. skills/wuwei-run/SKILL.md:37 still shows `--tier light|standard|full` with no smart and no --domain; the planner skill will not suggest the domain flag for one-off adds.
- [low] cli/wuwei/evidence.py:63 blocks: no. WAIVE hard-codes this repository's own guard names (PROCESS, DUTY, permissionDecision) into the generic evidence reader that every workspace runs. It fails toward more arch, so it is coupling rather than a defect. A per-workspace standards line would keep the rule out of core.
- [low] blocks: no. Mixed versions: a plan with smart items, synced through wuwei/state, read by an older WUWEI gives quality only (base needed() treats any unknown tier as below standard), and raises KeyError at RAISE[tier] under an overrun budget. The spec's Rollback line names this. A release note should tell workspaces to upgrade every clone together.
- [low] blocks: no. Runtime +28 lines against the brief's +20 (the plan.md estimate). The constitution's 3,600 cap holds at 3,424. analysis.md B1 records the overrun.

## Probes
- Conformance: needed() keeps the standard rows for smart (std = tier in standard, smart), adds the domain floor and signals only by `or`, and keeps the full branch unchanged. Smart clear is never below standard on gates, and complex defaults any missing or misspelled domain. This follows design.md:101 and FR-002, apart from the error-budget case above.
- Probe (pytest in a git archive copy of 5ce0892, scratch tests/test_raise_probe.py, removed after): smart clear in_doubt, plain code with a test. Unraised: "quality, goal". Raised (5 merges, 2 reverts): "arch, quality, security (tier raised to standard ...)". Standard raised: "arch, quality, security, goal (tier raised to full ...)".
- Coupling: evidence.py gains stdlib ast and uses gh.file, which it already imported; guards.create_door now passes headRefOid and baseRefOid to gates_for. The guards to evidence edge already existed, and there is no new module edge or cycle.
- Failure modes: an unread or unparsed head counts as a rise (fails closed). The result is cached a day per base and head sha in _cached, so a transient host error keeps security owed for that head. That is conservative, and an operator sees it as a "security" gate gap. The door cost is two contents reads per changed non-test .py file, only when smart and not already owing security.
- Spec artifacts: gaps() reads the item tier (not the raised one), so smart complex keeps them as safety under a raise. spec_gaps at tier smart uses the standard rule rows (evidence.py:227).
- Budget: `cat cli/wuwei/*.py | wc -l` gives 3,424 at head and 3,396 at merge base 86b2e56. `git diff --numstat` gives +49/-21 in cli/wuwei.
- Charter words: `wc -w agents/*.md` gives a maximum of 2,150 (sentinel-arch, the same as base), which equals AGENT_WORDS-100. `pytest tests/test_charters.py tests/test_smart.py tests/test_codex.py`: 237 passed.
- Drift: `bin/wuwei agents build` in the copy reports "agents match the charters". agents/ and .claude/agents are unchanged after the rebuild.
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference, and each charters/*.md equals .claude/wuwei/charters. `pytest tests/test_setup.py -k "vendored or budget or lines or drift or build"`: 5 passed.
- Breaking: at base, reference.md and SKILL.md show --tier given explicitly, and only charters/lead.md stated "standard by default" (seat guidance, updated here). Existing items keep their stored tier; upgrade.py maps unknown tiers to standard. A new item with no domain reads as complex, which is at least standard, so the new default requires more and never trims. Minor.
- Builder evidence read, not re-run: specs/smart-tier/route_diff.txt (route moves only toward more gates) and probe.txt (70 cases).
- Confidence is medium: the arch reading and the raise probe are direct. The full suite and the route corpus were not re-run here; those belong to quality and security.

## Residual risk
The guard-word signal is lexical: a guard change that names none of the words reads as no guard change outside owner paths (How this fails 1). The steward should watch smart clear and complicated items for arch escapes.

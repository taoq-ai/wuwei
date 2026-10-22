Verdict: FIX
Gate: arch
Item: free-lines-7
PR: taoq-ai/wuwei#1237
Head: adccd9904380aa59882ef4f58617ec6498df4422
Confidence: medium
Breaking: no (patch: charter prose, docs and the size test; no CLI, config, file format, PR body line or role name changes)

## Findings
- [medium] charters/_common.md:70 blocks: yes. Failure: old Boundaries 4 had two rules: "Outward text follows `_common-authoring.md`." and "Never put a secret or workspace content into an outward call." The trim merges them into "Outward text ... never carries a secret or workspace content", which ties the ban to authored text (posts, PR bodies, commits; gates do not even load `_common-authoring.md`) and no longer covers outward calls. A seat that puts private workspace content into a WebSearch query, a WebFetch URL or a `gh api` payload breaks no charter line any more, and the leak guard (cli/wuwei/guards.py:354) only catches the canary and token patterns. That contradicts the item's promise "trimmed with no rule lost", and the PR's rewording table calls it the same rule (requirement: promise "no rule lost"; CWE-200). Fix: keep the call scope, for example "Outward text follows `_common-authoring.md`; no outward call carries a secret or workspace content." That costs about 2 words, and sentinel-arch has 103 words of room.
- [low] charters/_common.md:3 blocks: no. "WUWEI audits the evidence, never the commands" can be read as "WUWEI never inspects commands", which the doors contradict (they refuse commands). It also drops the old meaning, "it never tells you which command to run". Suggested wording: "WUWEI audits the evidence and never names the command."
- [low] charters/_common.md:16 blocks: no. "for scope, goals" drops "a change of", so the ask trigger reads wider than before ("a change of scope or goals"). The `scope:` and `goal:` classes are unchanged, so the effect is small.
- [low] blocks: no. charters/builder.md:76 still says "the retro note", but `_common.md` no longer names the three lines as "the retro note" ("End every handoff with:"). The code block makes it clear, but the term is now undefined.
- [low] blocks: no. The reordered Done delta sentence (the owner's wording) puts "off risky paths" on docs as well. evidence.py needed() lets a docs delta carry on any path, and docs/design.md:94 keeps "docs or at most 20 lines off risky paths". So the charter is stricter than the code there. The PR's Assumptions record that design.md is left as it is.

## Probes
- Read plan show free-lines-7, `wuwei evidence taoq-ai/wuwei#1237` (gates missing: arch, quality; CI running) and the PR body via `gh api repos/taoq-ai/wuwei/pulls/1237` (head matches adccd99).
- Compared the 22 rows of the rewording table with `git diff origin/main...adccd99 -- charters/_common.md` sentence by sentence. Every rule is present except the Boundaries 4 outward-call scope (finding 1). The class list in Decisions 2 is unchanged (9 classes), and so are the 5 ask triggers, the Done list, the thresholds and the four process-fit items. The Evidence 4 scratch and copy rules stay; only the "(Boundaries 2)" cross-reference was dropped, and the first sentence still says "your scratch folder".
- Section numbering at the head: Decisions 1-4, Evidence 1-4, Boundaries 1-5. External citations still valid: charters/_gate.md:13 (Evidence 4), charters/planner.md:57 (Boundaries 3), charters/planner.md:88 (Decisions 2) (`grep -rn "Evidence [0-9]\|Boundaries [0-9]\|Decisions [0-9]" charters docs`). The "## Decisions" and "## Done" headers that hook.py:433 extracts for the planner are intact.
- Constitution: Governance says "Amendments are commits to this file with a dated line in the commit message". The commit adccd99 carries "Constitution amended 2026-10-22: runtime budget 3,600 lines, version 3.3.0", and the Version line reads 3.3.0, Last amended 2026-10-22. A minor bump for a budget raise follows the 3.1.0 to 3.2.0 precedent recorded under Assumptions. The amendment conforms.
- One statement: `grep -rn "3,400\|3400" --include=*.md --include=*.py .` outside specs/ and CHANGELOG finds nothing. Constitution VI, AGENTS.md, CONTRIBUTING.md, SECURITY.md, design.md section 11, philosophy.md and tests/test_setup.py all say 3,600.
- Fitness functions: runtime 3,390 lines (`cat cli/wuwei/*.py | wc -l`), under 3,600. `_common.md` went from 903 to 800 words (`wc -w`), and the largest agent, sentinel-arch, is at 2,147 words, under 2,150 (ceiling 2,250 minus 100).
- In a `git archive adccd99` copy: `pytest -q tests/test_charters.py tests/test_setup.py -k "charter or agent or common or size_budget or vendored"` gave 202 passed and 31 deselected. `bin/wuwei agents build` in the copy, then `diff -r agents` against the builder's worktree, showed no difference.
- Breaking: read against the public API in docs/site/concepts/evidence.md (Breaking changes). No CLI, config, file format, PR body line, question class or role name changed. The budget raise loosens an internal constraint. Patch.
- Confidence medium: finding 1 depends on reading "outward text" as authored text, which is how `_common-authoring.md` scopes it. A reader who takes "outward text" to mean any outgoing text would see no loss.

## Residual risk
Gates do not load `_common-authoring.md`, so for sentinels Boundaries 4 is the only line against putting workspace content into an outward call, and its wording has to say so on its own.

Verdict: FIX
Gate: arch
Item: seat-rules
PR: taoq-ai/wuwei#1111
Head: bec74db0c78b9f3f2b2812a77589d37427dffea6
Confidence: medium
Breaking: no

## Findings
- [medium] charters/_gate.md:26 blocks: yes. Failure: this charter loads into every workspace, and the trigger "rewrites a parser" fires on any parser in any repository. Take an adopter's PR that rewrites a YAML config parser: all four gates are told to probe "the checks that do not rely on door words" (a leak check on network programs, an ask rule for infrastructure commands) "with the new command shape". No such checks exist for that code, and "door words" is defined nowhere: not in the charters, not in docs/design.md, not in the skills (`grep -rn "door word" docs cli skills charters` finds only this line). So each gate either spends a round on an empty probe or makes up a check. This fails the same product-generic test as the line budget blocked last pass. Fix: scope the trigger to guard parsing, as the first half of rule 4 already does (for example "When a change to guard parsing makes more commands unreadable or rewrites the guard's parser"), and gloss door words in place (for example "the program names a guard matches on").
- [medium] charters/steward.md:17 blocks: yes. Failure: "goes in that repository's `.wuwei/standards.md` lines" names a file per repository, but the architecture has one per workspace. docs/design.md section 10 puts `standards.md` under the workspace's `.wuwei/`. docs/site/concepts/many-repositories.md says "one set of standards across all of them" and "nothing to configure differently" per repository. In a workspace with several repositories, a steward following this line writes `<repo>/.wuwei/standards.md` inside that clone. The planner never reads that file and never passes it to a brief (design section 3), so the lesson is lost. Fix: "goes in `.wuwei/standards.md` as a line that names that repository" (or, for lasting repository knowledge, a plan item to that repository's memory, as learning.md already says).
- [low] blocks: no. "door program" is glossed in place ("the guarded program the stub stands for") and the doors exist in every workspace through the plugin's hook. The rule is conditional on a change to guard parsing, so in other workspaces it does nothing rather than misleads. "stub program on PATH" was already in _gate.md rule 5 on main, and it is generic.
- [low] blocks: no. This diff does not touch the route corpus. builder.md:57 (`tests/fixtures/routes.json` where it exists) and planner.md:36-37 (`guards.py`, `hook.py`) were already WUWEI-specific on main. By this item's own rule 5, they are lessons about one repository's code and belong in standards lines. That is an existing gap for a later item.
- [low] charters/_gate.md:17 blocks: no. Rule 3 still says "A mutant that is equivalent ... is `[low] blocks: no`", while the new sentence lets a gate call code equivalent only after a differential probe. Both lead to blocks: no, so nothing goes wrong, but a reader may see two standards for "equivalent". Reword the earlier sentence to "a mutant you cannot turn into a bad input".
- [low] charters/steward.md:16 blocks: no. The line before it says proposals that change how the process runs go to `.wuwei/standards.md`. The new line sends lessons about how seats work to a charter proposal. A lesson can be both, and the order between the two is not stated.

## Probes
- Ran `git archive bec74db | tar -x` into scratch/arch-seat-rules/tree. Ran `git diff 9d6701e bec74db -- charters/ tests/`, and read the item with `wuwei plan show seat-rules`. All six promised rules are present, and no behaviour beyond the promise was added.
- Ran `pytest -q tests/test_setup.py` in the copy: 35 passed, including the drift and vendored-copy tests. In a second copy committed to a fresh repository, `bin/wuwei agents build` then `git status --short` showed no change (acceptance 1).
- Ran `grep -rn "door word" docs cli skills charters`: the only hit is _gate.md:27. Ran `grep -n door docs/design.md`: "door program" is defined in section 7, "door words" is not.
- Read docs/design.md sections 3 and 10, docs/site/concepts/many-repositories.md and learning.md: standards are one file per workspace.
- Read skills/wuwei-run, wuwei-rules and wuwei-close, docs/site/concepts/evidence.md and team.md. Nothing contradicts the together-forward rule, the parser rule or the equivalence rule. `grep -rn "rule [0-9]" cli` and the spec's grep found no citation of _gate.md rules by number, so the renumbering from 4-6 to 5-7 is safe.
- Outward contracts: the diff changes charter text, generated agents and tests only. No CLI command, flag, exit code, config key or file format changes. Breaking: no.
- Confidence is medium: both blocking findings come from wording read against the written architecture, not from a run of a seat in another workspace.

## Residual risk
Holding all verdicts until the last gate returns makes the builder wait for the slowest gate. The spec bounds that wait by treating a gate that never returns as a failed seat; the planner charter does not say so itself.

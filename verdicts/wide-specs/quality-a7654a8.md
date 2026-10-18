Verdict: PASS
Gate: quality
Item: wide-specs
PR: taoq-ai/wuwei#1142
Head: a7654a879f3e841e433ae81123c20498f705752c
Confidence: high

## Findings
- [low] tests/test_charters.py:72 blocks: no. Test quality (assertion survives a negated rule): the wide-change threshold string ends before its verb, so a charter that says "or 10 code files) adds no gate;" or "never adds arch;" passes, and so does "at `light`, risky or owner paths add security and a wide change" (mutants C1, C6, C5, each re-run in a fresh copy). Dropping a clause does fail it (C3 "or 10 code files", C4 the spec-contract clause). The gap was already there on main (the old string was verb-less too); the code in evidence.needed still enforces arch, so nothing gets through a merge. Fix: end the asserted string with "or 10 code files) adds arch" and start it at "at `standard`".
- [low] tests/test_charters.py:73 blocks: no. The spec-contract string includes its verb, but "neither a contract file nor a spec contract (...) takes arch at any tier" and "takes arch at any tier but light" still contain it and pass (C2, C7). Both are contrived; a note only.
- [low] cli/wuwei/evidence.py:41 blocks: no. Untested: removing the `^` anchor from the spec-contract clause survives (M8, re-run). Concrete input: light tier, `src/specs/contracts/h.py`, which would then take arch as well as quality. That adds a gate and drops none. Missing test: a nested non-root `x/specs/contracts/` code path that expects no arch.
- [low] cli/wuwei/evidence.py:261 blocks: no. Untested side effect, recorded under the spec's Assumptions: because CONTRACT now reads `wide` and not just `code`, a contract-shaped file under specs/ outside a contracts/ folder (`specs/x.proto`, `specs/001/openapi.yaml`) now takes arch at light/standard/full, where main gave (). No test pins it.
- [low] blocks: no. Existing gap, unchanged and recorded in the spec's Clarifications: a full-tier item whose diff is specs only gets () at 1,780 lines, while the same diff at standard gets ('arch',). So for a spec-only diff, the higher tier asks for fewer gates.

## Probes
Suite at head (git archive copy): /root/.local/bin/pytest -q gave 1700 passed, 2 skipped (test_release.py:36,57, ssh-keygen absent; unrelated). CI at head is reported green by the brief.
New tests on main code (main tree plus head tests): 10 fail. These are the 8 needed() cases that move (prose 300/6200, mixed code+prose, light/standard/full spec contracts), the evidence.gaps README case (files7), the delta test and the charter test. The 1780-spec, 200/201 spec-only, 150+50/150+51 and negative-path cases also pass on main, so they pin behaviour and kill the code-only mutant.
Bounds: specs-only 200 gives (), openspec 201 gives arch, code 150 + spec 50 gives quality, code 150 + spec 51 gives arch+quality. Tiers covered: light, standard, full. OpenSpec covered: a 201-line proposal and a nested `openspec/changes/x/specs/contracts/events.md`. The delta test runs through gh.compare via the fake's REST `filename` shape (conftest.py:95-101), the real consumer: README 300 carries, spec 200 carries, spec 201 and contract 2 go to arch.
Mutants (each in a fresh copy of the head; failing tests named by the pytest FAILED list):
- M1 `lines(wide)` changed back to `lines(files)` (the wide filter): 5 fail, among them wide_trigger[standard-files1/2/7], diff_decides[files7-150-None] and the delta test.
- M2 `wide` reduced to code only: 9 fail (wide_trigger[files0,4,5,8,9], diff_decides[files8-890-arch] and more).
- M3 CONTRACT spec clause dropped: 5 fail (wide_trigger[light-files8, light-files9, standard-files10, full-files11] and the delta test).
- M4 CONTRACT searched over `code`, not `wide`: the same 5 fail.
- M5 `>` changed to `>=` WIDE: 3 fail (wide_trigger[files3, files6] and the delta test).
- M6 openspec dropped from `wide`: 2 fail (files4, files9).
- M7 `(.+/)?` dropped: 4 fail.
- M9 trailing `/` dropped from `contracts/`: 1 fails (light-files12, `specs/contracts.md`).
- M10 openspec dropped from the clause: 1 fails (files9).
- M8 `^` dropped: survives (note above).
- Charter: C3 and C4 fail test_decisions_and_done_are_stated_once_in_common; C1, C2, C5, C6 and C7 survive (notes above).
Differential, needed() at main versus head: 1,890 generated cases (20 paths, 1-2 files, sizes 1/120/201, three tiers), 634 move. Every move falls in an intended class: spec contracts and contract files under specs/ gain arch at every tier, and prose-driven arch drops at standard (README 201 lines: arch to (); code+README: arch+quality to quality). No case loses quality or security. `docs/specs/contracts/a.md` and `src/specs/contracts/h.py` do not move.
Agents and vendored copy: `sh bin/wuwei agents build` in a fresh copy prints "agents match the charters", and diff -r against the head shows only __pycache__. cmp shows .claude/wuwei/cli/wuwei/evidence.py and .claude/wuwei/charters/_common.md identical to the sources, and .claude/agents/*.md identical to agents/*.md.
Runtime budget: cli/wuwei is 2,976 lines at main and 2,978 at head (+2, within the promise's 3 and the 3,000 cap).
Guard parsing probes and route-corpus differential: not applicable, since guards.py and hook.py are unchanged.
Simplicity: none deletable. `wide` is one filtered list that reuses `code` and the existing specs prefixes, and the CONTRACT change is one alternation. `f['path'] in code` is a list scan, but diffs are small, so it does not matter.
Confidence reason: every changed guard part has a killing test and the differential shows only intended moves. The surviving mutants either over-gate (M8) or edit charter prose that the code does not read.

## Residual risk
The charter text test checks substrings, so a reworded or negated rule can pass while the code stays correct. The spec-only diff at full tier still asks for fewer gates than at standard (existing behaviour).

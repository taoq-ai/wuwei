Verdict: PASS
Gate: security
Item: seat-rules
PR: taoq-ai/wuwei#1111
Head: bec74db0c78b9f3f2b2812a77589d37427dffea6
Confidence: high

## Findings
- [low] charters/_gate.md:20 blocks: no. "a surviving mutant alone is reported as untested" gives "untested" no severity. It does not weaken anything: the unchanged sentence before it still blocks a mutant with a named bad input, and a mutant with no bad input was already `[low] blocks: no`. The new rule only stops a gate from calling such a mutant "equivalent" without a differential probe. A later wording could say "untested, `[low] blocks: no` with the missing test as a note" to close the reading gap.
- [low] charters/planner.md:31 blocks: no. "the builder starts fixing only then" waits on the last gate for a head. A gate seat that never hands back would stall the fix round, and that includes an urgent security fix waiting on a slow arch gate. This is a delay, not a route around a door: merge still needs every gate's attested verdict, and a refused or failed seat still returns a report (_common Report). No timeout rule exists for a stuck seat; that gap was there before this change.

## Probes
- `git diff origin/main...bec74db -- charters/ tests/`: the only changes are 4 charters, the tests and specs, plus the generated agents/ and vendored .claude/ copies. No runtime code, hooks or allowlist changed.
- _gate.md renumbering: old rules 1-3 stay in place, with one sentence added to the end of 3. New rule 4 is inserted. Old rules 4, 5 and 6 become 5, 6 and 7, and the diff shows their text byte-identical apart from the number. Nothing was dropped or merged.
- The trust-boundary rule is intact in new rule 5: "A trust-boundary security finding always blocks" and "except a trust-boundary security finding, which still blocks" are both present and unchanged.
- grep for numbered rule references ("rule N", "gate rule N") in charters, agents, cli, hooks, docs and skills: none found, so the renumbering breaks no cross-reference.
- Ran `bin/wuwei agents build` in a git-archive copy and got "agents match the charters". `diff -r` against a fresh archive shows no change except __pycache__.
- Checked that the full charters/_gate.md text appears inside all 8 sentinel agents (agents/ and .claude/agents/): all True. The vendored .claude/wuwei/charters copies of _gate, planner, builder and steward are identical to charters/.
- `pytest -q tests/test_setup.py` in the copy: 35 passed.
- Read the new rules for security effect. The parser probe rule, the probe of checks without door words (leak check, infra ask), the requirement that fixtures be written by code, and the differential-before-equivalence rule all add duties; none removes one. The steward lesson-placement rule only says where lessons are filed and touches no door.
- Mutants: not run, because no guard or validation code changed (docs-only diff). The tests check that phrases are present, which is the right level for charter text.
- Confidence high: the diff is small, docs-only and fully read, and the drift check and tests ran at the head.

## Residual risk
The new parser-probe duties rely on seats following them, and nothing checks the reported counts. The two notes are wording and liveness gaps, not ways to bypass a door.

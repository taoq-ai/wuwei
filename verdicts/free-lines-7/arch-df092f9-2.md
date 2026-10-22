Verdict: PASS
Gate: arch
Item: free-lines-7
PR: taoq-ai/wuwei#1237
Head: df092f90cab026fa3e085cc9d75883c1b67044fe
Confidence: high
Breaking: no (patch: charter prose and generated agents only; no public API element changes)
Supersedes: free-lines-7/arch-df092f9.md

## Findings
- [low] charters/_common.md:40 blocks: no. The Done sentence summarises the code. It leaves out two limits: generated files carry only off owner and contract paths too, and only when a dated `Generated` standards line names them (evidence.py:341-344). A small delta carries only when the gate it needs is quality (evidence.py:348). docs/design.md:94 holds the detail, and the wording before this PR had the same gap.
- [low] blocks: no. sentinel-arch has exactly the 100 words of room the acceptance requires (2,150 of 2,250), so the next rule added to `_common.md`, `_gate.md` or sentinel-arch.md needs a deletion first.

## Probes
- closed: PR body record of the Done wording departure at df092f9. I read the body once with `gh api repos/taoq-ai/wuwei/pulls/1237`; the head is still df092f90.
- What and why, the promise section, the Done map row (line 27) and the Tests line (line 66) now carry the new Done wording.
- The Boundaries 4 map row (line 35) gives both rules with their own scopes. The word table shows sentinel-arch at 2,150 with 100 words of room.
- Assumptions line 58 records the departure from the plan item's quoted wording, why (`evidence.needed()` lets a docs-only delta carry on any path) and what would overturn it.
- The charter text and the generated agents are unchanged since my df092f9 FIX. That round in a fresh `git archive df092f9` copy gave 233 passed for `pytest -q tests/test_charters.py tests/test_setup.py`, and `bin/wuwei agents build` showed no drift.
- closed at df092f9: the Boundaries 4 outward-call scope, the docs-on-any-path Done note and the builder.md retro-note term.
- Confidence high: the head is unchanged, and the remaining fix was a body record I read directly.

## Residual risk
The goal gate may still weigh the departure from the promise's quoted Done wording; the PR body records it as an assumption with what would overturn it.

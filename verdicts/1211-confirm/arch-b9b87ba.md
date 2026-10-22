Verdict: PASS
Gate: arch
Item: 1211-confirm
PR: taoq-ai/wuwei#1233
Head: b9b87ba73f128c16d096bd7ec30f2bca0063de4e
Confidence: high
Breaking: no (patch: a row with no toolUseResult.answers now records answer.unconfirmed, as main did; no ledger kind, field, hook output field, CLI flag or exit code is removed or reshaped)

## Findings
none

## Probes
- Delta judged: fa48175e (hook.py both copies, design.md, hooks.md, tests, probe, mutants) and b9b87ba (spec artifacts only). The merge 34600145 brings in main d141928. `git diff d1419285 b9b87ba -- cli .claude/wuwei/cli docs` touches only hook.py (both copies), design.md and hooks.md. The hook.py lines that differ from main are the 1211 lines. The vendored hook.py is byte-identical (cmp).
- closed: text fallback lets an entry kept first record an answer the owner did not give (hook.py:326, CWE-345) at fa48175. I re-ran my crafted-label cases in a fresh `git archive` copy of b9b87ba. Batch case: _confirm returned the note "the tool_result has no toolUseResult answers (NoneType)" and the ledger holds only answer.unconfirmed, with no prompt and no plan.approved. Single-question case: _shown returns ({}, that reason) for both the real and the forged entry. Main d141928 records nothing.
- closed: design.md:257 "records what it finds" at fa48175. design.md now says "records an entry it can record whole; any other entry waits for the next call". That matches hook.py, where an entry with a reason at a Stop is skipped (`if why and (final or shown is None and fresh)`).
- closed: "Fixes #1231" at b9b87ba. The PR body now says "Refs #1231" (read with gh api repos/taoq-ai/wuwei/pulls/1233 --jq .body).
- closed: spec "re-ask only that question" at b9b87ba. A grep of specs/1211-confirm finds it only in analysis.md A7, marked removed.
- Doc consistency: design.md section 8 says only toolUseResult.answers counts, never the text. It lists the reasons: path outside projects, no tool_use, no toolUseResult answers, differing answer, no row after 10 minutes. It also says the Stop skips the 1.5 s wait past 10 minutes. hooks.md says "no `toolUseResult` answers (its text never counts)". Both match _shown and _confirm at the head. A grep of docs, SECURITY.md, charters and the spec finds no leftover text-fallback wording.
- Bound at a Stop: `fresh = cache_get(..., BOUND) is not None` gates the wait loop, so past 600 s a Stop calls _shown once and leaves the claim to the next call. That matches the coordinator's summary and design.md.
- Route differential (standards line), main d141928 vs head b9b87ba, using the head corpus, with case folders under scratch: sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at both. 288 routes, 590 cases, 0 moved (guards 288/0, bash 288/0, payload 12/0, session 2/0).
- Answer probe (specs/1211-confirm/answer_probe.py at the head, run against both trees): 1,560 cases per tree, 1,560 without a hook.error at both, 1,170 moved. Holes (mis-recorded, Stop blocked): main (295, 1170), head (0, 0). The new "no answers dict" class: 195 cases, head (0, 0).
- Runtime: concatenated line count of .claude/wuwei/cli/wuwei/*.py from the archive copies: main d141928 3,373 (#1229, #1228 and #1232 are merged), head 3,382 (+9). That is under 3,400 with 18 lines to spare. Adding 1222 at its budget (+3) gives 3,385; adding parked yes-word (+3) gives 3,388.
- Merge conflicts: #1228, #1229 and #1232 are already in main through the merge. 1222 (deliver) is untouched here.
- Full suite not run, as the coordinator asked (CI is green). Confidence is high: the closed finding, the doc wording and both probes were re-read at this head.

## Residual risk
A real compacted row with no toolUseResult.answers will now record answer.unconfirmed and stay unrecorded (fail closed, named), so #1231's compaction cause stays open until such a row is captured. A forged entry kept first still suppresses the real answer, as on main.

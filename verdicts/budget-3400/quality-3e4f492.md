Verdict: PASS
Gate: quality
Item: budget-3400
PR: taoq-ai/wuwei#1134
Head: 3e4f49280d2ccfab2dae51b77c55c983aec8b7be
Confidence: high

## Findings
- [low] README.md:101, docs/site/reference.md:28 and :36, cli/wuwei/ws.py:53, cli/wuwei/__main__.py:229, tests/test_ledger.py:15 blocks: no. These still say "five keys" while constitution VI, design.md (sections 2 and 11) and philosophy.md now say six. The runtime still reads five keys, so the user-facing reference is correct today and the design documents run ahead of it until models-record adds `models` to `ws.DEFAULTS`. The item's spec lists exactly this residue as an assumption, and the promise names models-record as the owner of tests/test_ledger.py. Models-record must update all six places; a grep for "five keys" and "five config keys" finds them.
- [low] SECURITY.md:135 blocks: no. A file outside the promise's list; the diff changes it from 3,000 to 3,400. This is correct, because it was the last stale budget statement, and the spec records it as T006a.

## Probes
- Size test mutation, run with `pytest -q tests/test_setup.py -k size_budget` in `git archive` copies of the head under the scratchpad (sentinel-quality-budget-3400). Runtime lines padded with a module `cli/wuwei/zz_pad.py`, measured with the test's own counting expression. At 3,400 lines it passes. At 3,401 lines it fails: `assert 3401 <= 3400` (tests/test_setup.py:113) with the message naming 3400.
- Reversed guard: the assertion set back to `<= 3000` with 3,100 runtime lines fails (`3100 <= 3000`). The test is a real guard and is not satisfied by the change alone.
- Full suite at the head copy, `pytest -q`: 1684 passed, 2 skipped (tests/test_release.py:36 and :57, ssh-keygen absent, unrelated to the item).
- Budget statements, read with `grep -rnIE "3,000|3000" --exclude-dir=specs .` in the head copy: no runtime budget line says 3,000. The only hits are `cli/wuwei/gh.py:33`, a GitHub API limit, and `cli/wuwei/hook.py:299`, a slice length, and each has a vendored duplicate under `.claude/wuwei/cli/`. Another hit, philosophy.md:30, reads "33,000 lines", which is history. 3,400 appears in the constitution, AGENTS.md, CONTRIBUTING.md, SECURITY.md, docs/design.md section 11, docs/site/concepts/philosophy.md and tests/test_setup.py. The older specs/* files keep 3,000 as the record of their own time and are not restated claims. `.claude/wuwei/` vendors only bin, charters and cli (no document states the budget), so it needs no change. Acceptance 3 holds.
- The runtime is untouched: `git diff efcd9e7 3e4f492 --stat -- cli` is empty, and the runtime measures 2,976 lines at the head. Zero guard or parser code is in the diff, so the combinatorial and differential probes and the route corpus are N.A.
- Constitution amendment rules: the governance line asks for a dated line in the commit message. Commit 66845f0 carries "Amended 2026-10-18: constitution 3.1.0 to 3.2.0 ...". The version footer reads 3.2.0 with Last amended 2026-10-18 and a matching description. The delete-first rule is kept and the one new rule is added. Both commits are authored by Leone with only a Co-Authored-By trailer.
- Reasoning arithmetic: 2,976 + 408 = 3,384, which is under 3,400 by 16; this matches the `wc` count at the head.
- Test-quality kinds (assertion that survives removal, wall-clock, ordering, network or shared file, prose): none. The test counts files and asserts a number.
- Simplicity: none. The diff adds no code, and nothing in it can be deleted.

## Residual risk
The design and philosophy pages say six keys while the runtime, README and reference say five until models-record merges. If that item stalls, the public docs stay inconsistent; the 3,400 budget has about 16 lines of slack against the stated backlog.

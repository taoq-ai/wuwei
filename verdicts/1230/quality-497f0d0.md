Verdict: PASS
Gate: quality
Item: 1230
PR: taoq-ai/wuwei#1234
Head: 497f0d04b97eeb3a675afde1bbe8a8219874a63e
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/evidence.py:345 blocks: no. Unchanged note: a comma with no space between globs (`a/*,b`) is untested and fails conservatively (the pass is re-read); a relocated PR hunk with identical changed lines and identical context normalises to the same patch and carries.

## Probes
- Delta a626a8a to 497f0d0 read with `git diff`; head tested from a fresh `git archive` of 497f0d0 in /tmp/claude-0/-home-user-wuwei/3c3b5210-f1f3-5623-83c3-a701461b643a/scratchpad/sentinel-quality-1230/base2. With -k 'base_merge or 300_file_cap or generated_glob' over tests/test_evidence.py and tests/test_guards.py: 44 passed, 2242 deselected. Also -k 'drift or vendored or charters' over tests: 186 passed (charters and agents/ are in step). cli/wuwei is 3381 lines of 3400. Full suite not run.
- Mutants, each applied to both cli/wuwei/ and .claude/wuwei/cli/wuwei/, one at a time, 12 run, 12 killed by behavioural tests: cap `len(was) < 300` only (killed by the 299-300 row), cap `300 > len(now)` only (300-299 row), cap `<=`, fallback zero-line entry and fallback was/now swap (both killed by the new row 'the merge keeps 30 lines main removed'), fallback without head-to-head lookup, the new exemption with RISKY, CONTRACT, owned dropped one at a time and all together (test_a_generated_glob_never_drops_a_risky_owner_or_contract_path), exemption forced always, fnmatch replaced by equality.
- closed: 300-file cap guard tested on one side only at a626a8a (rows 299-then-300 and 300-then-299 now kill both one-sided mutants at 497f0d0).
- closed: untested fallback arm of next() at a626a8a (new row owes quality; zero-entry and swap mutants are killed at 497f0d0).
- The new code exempts risky, owner and contract paths from a Generated glob: a trust-boundary hardening, since standards.md is writable by any session and fnmatch's `*` crosses `/`. Its test sweeps globs `*`, `src/*`, `*.py`, `src/sess*` over three path classes plus a contract file and a specs contract, and the plain-path rows still carry, so it is not vacuous.
- Acceptance 3 with `guide/api.json`: it still means what it did. The declared files (guide/*, src/version.py) carry; `guide/*` alone owes quality (the undeclared version.py), another repo, an undated line, a wrong label and no line owe arch. Moving off openapi.json (a contract file, now never droppable) is required by the exemption; 201 generated lines make the change wide, so arch is owed whenever the Generated line is not honoured, which makes the carry/owe difference sharper rather than weaker. The openapi.json contract case lives in the new exemption test.
- Simplicity: none deletable. The exemption adds one clause and reuses RISKY, CONTRACT and owned; the docstring reflow is net zero lines.

## Residual risk
The route differential and the real-git probe were not re-run at 497f0d0 (the delta changes only which paths a Generated glob drops, away from the first-round probe cases). A PR over 300 files falls to head-to-head by design.

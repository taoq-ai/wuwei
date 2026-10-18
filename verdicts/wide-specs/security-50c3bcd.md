Verdict: PASS
Gate: security
Item: wide-specs
PR: taoq-ai/wuwei#1142
Head: 50c3bcd8c4221d7edaccdcfbbccb68c9b7b623f5
Confidence: high

## Findings
- [low] blocks: no. Closed from 4b535bd: `wide` now reads the existing PROSE regex (evidence.py:19, :256), so non-prose `.txt` files count again. At standard 300, requirements/prod.txt, constraints.txt and CMakeLists.txt give ('arch',), as on main. Seat-loaded files (AGENTS.md, CLAUDE.md, charters/*.md, .claude/agents/*.md, .claude/skills/*/SKILL.md, docs/AGENTS.md) also give ('arch',), which closes my LLM01/LLM06 note too.
- [low] blocks: no. Other agents' instruction files are still prose under the existing PROSE seat list: `.claude/commands/*.md`, `.github/copilot-instructions.md` and `GEMINI.md` give () at standard 300 (OWASP LLM01). This sits outside this item and is a candidate follow-up that widens the PROSE seat list.
- [low] evidence.py:17 blocks: no. Anchoring DOCS to `^(LICENSE|NOTICE)$` moves the quality trigger, which the promise names as outside, but only toward stricter. LICENSE-MIT and NOTICE_handler.py now take quality, the test rule, and all four gates at full. No path loses a gate (0 losses against 4b535bd). The announcement states the change. One nit there: its `LICENSES/` example holds only for non-.txt files, because LICENSES/MIT.txt is still docs by extension.
- [low] blocks: no. Announcement: the line now links issue comment 6251566330 on this PR, which I read once over REST. It describes the BREAKING CHANGE, the loosening and the stricter LICENSE/NOTICE rule. The owner's `breaking:` ruling at this head is still pending, and it is the gap that holds the merge. The breaking_gaps follow-up from 4b535bd stands: the `Announcement:` check still accepts any text.

## Probes
- Delta 4b535bd..50c3bcd: evidence.py drops TEXT, anchors DOCS, builds `wide` from `not PROSE.match(path) or specs/ or openspec/`. The vendored copy is identical. +5 test rows, one row changed. Charter, agents, docs and spec text. Base still efcd9e7, and 4b535bd is an ancestor.
- Differential over the same 144,480 cases (sha256 1269843f5a0454163a973291633b19266a7489dd7d6189397925935fe4707e76):
  - main vs head: 24,698 moved. 5,103 losses, all arch at standard, on 729 distinct paths, each matched by PROSE and outside specs/ and openspec/ (0 non-PROSE losses). Gains: arch light 9,740 / standard 2,922 / full 5,455; quality 895 at each tier; security standard 200 and full 895; goal full 895.
  - 4b535bd vs head: 4,325 moved, 0 losses, all gains.
- Targeted probe, 300 lines at light / standard / full, main vs head:
  - requirements/prod.txt, constraints.txt, CMakeLists.txt, robots.txt, README.txt, LICENSES/MIT.txt and the seat files above: equal to main, ((), ('arch',), ()).
  - README.md, LICENSE, NOTICE: () at all tiers (the promise).
  - LICENSE-MIT and NOTICE_handler.py: stricter than main.
  - Specs/001-x/contracts/api.md: arch at every tier.
- Path classes: unchanged from earlier rounds. `%xx` reads as code. `//`, `/./`, `/../` are refused by git. Case variants are stricter.
- Mutants, each in a fresh git archive copy of 50c3bcd, tests/test_evidence.py. All killed, none survive:
  - a: DOCS anchor reverted, killed (1 failed).
  - c: specs/openspec dropped from `wide`, killed (5).
  - e: AGENTS.md and charters/agents dropped from the PROSE seat exclusion, killed (6).
  - f: openspec/ dropped from `wide`, killed (1).
  - t5: contract over `wide` instead of `files`, now killed (1).
- Suite at head (scratch copy): 1713 passed, 2 skipped (/root/.local/bin/pytest -q).
- PR read once via REST: head 50c3bcd, draft. Scanners: no dependency, workflow, hook or script change in the delta. CI at this head was not re-read in this round, so its state here is unmeasured.
- Confidence high: the full differential, the targeted probe and the mutants agree, and the change reuses a regex the suite already pins.

## Residual risk
The existing PROSE seat list and RISKY's `requirements[^/]*\.txt$` (which misses requirements/*.txt and constraints.txt for security) are both narrower than the files that act as instructions or dependencies. Both are outside this item.

Verdict: FIX
Gate: security
Item: wide-specs
PR: taoq-ai/wuwei#1142
Head: 4b535bda51ca365b800b78bc1247d715a2dd57a7
Confidence: medium

## Findings
- [medium] cli/wuwei/evidence.py:18 blocks: yes. Failure: CWE-693 (protection mechanism failure) on a supply-chain and build path. TEXT treats every `.txt` file as prose, so a non-risky `.txt` that is not prose loses arch and is left owing nothing. At standard, 300 lines of `requirements/prod.txt` or `requirements/base.txt` (RISKY's `requirements[^/]*\.txt$` cannot cross a `/`), `constraints.txt` (a dependency pin file) or `CMakeLists.txt` (a build script) owed `('arch',)` on main and owe `()` at this head. evidence.py:385 already exempts them from the test rule, so a PR that pins a new package or adds an `execute_process` download to the build merges with no gate. A 300-line delta into these files carried the passes on neither main nor a7654a8 as arch, and now it carries them. The repository's own prose definition says otherwise: docs/design.md:102-103 states "a `.txt` ... [is] not prose", and the PROSE regex at evidence.py:20 leaves `.txt` out. The Breaking section lists the loosening as "README, docs pages, LICENSE, NOTICE, and the .md files seats load", so this part is unannounced. The fix left this from my a7654a8 finding (non-prose files counted as prose). I missed it in round 1 because I filed every `.txt` under prose. Fix: drop `txt` from TEXT. Mutant t1 shows no current test opposes it (157 passed). Add rows `requirements/prod.txt` 300 -> ('arch',) and `CMakeLists.txt` 300 -> ('arch',), and align docs/site/concepts/evidence.md:95, specs/wide-specs/spec.md:14 and :83, and the PR body.
- [low] blocks: no. Closed from a7654a8: non-prose files under a `docs/` component and LICENSE/NOTICE-prefixed paths now count toward wide (docs/conf.py, src/docs/x.py, NOTICE_handler.py at 300 -> ('arch',), each with a test row). A contract under docs/ now takes arch at any tier. The 144,480-case differential shows the head only gains against a7654a8.
- [low] blocks: no. Kept from a7654a8, inside the promise and now announced in the Breaking section: seat-loaded `.md` files (AGENTS.md, CLAUDE.md, charters/*.md, .claude/agents/*.md, skills/*/SKILL.md) owe no gate at any size (OWASP LLM01/LLM06). The existing PROSE regex at evidence.py:20 already excludes exactly these files. Reusing it for `wide` would close this and the `.txt` finding in one line, if the owner wants that.
- [low] cli/wuwei/evidence.py:261 blocks: no. Mutant t5 survives (CONTRACT over `wide` instead of `files`; 157 passed, re-run in a fresh copy). Over the 144,480 generated cases it shows 0 differences, but it is not equivalent: `Specs/001-x/contracts/api.md` at light gives ('arch',) at the head and () under the mutant. Missing test: one row for a mixed-case spec folder holding a `.md` contract.
- [low] blocks: no. Announcement question. breaking_gaps (evidence.py:338) accepts any non-blank text after `Announcement:`, so a placeholder clears the announcement gap (CWE-1287, weak input validation). This is not a trust bypass: the gap that holds the merge is the owner's `breaking:` ruling at the exact head (evidence.py:341-345, owner=True), and the owner reads the announcement when giving it. It is a candidate follow-up, for example requiring a URL or a path that the diff changes. This PR's placeholder need not change before ready from the security side. Turning ready waits on gates, and merging waits on the owner's ruling. The `breaking:` question should quote the Announcement line verbatim so the owner sees that it names release-please's future notes, not a sent message. Note that the announcement's "Loosened" list would grow if `.txt` stays prose.

## Probes
- Delta a7654a8..4b535bd (git diff): evidence.py +TEXT at :18, `wide` at :257 built from TEXT, contract check over `files`. Vendored .claude copy identical. Tests +8 rows; docs, spec and charter test text. No dependency, lockfile, workflow, hook or script change. Base still efcd9e7.
- Differential: the same 144,480 cases (cases.json sha256 1269843f5a0454163a973291633b19266a7489dd7d6189397925935fe4707e76). Main vs head: 24,155 moved, 6,643 losses (all arch at standard), 17,512 gains (arch). Every loss is on a TEXT path (prose extension, or exactly LICENSE). 0 losses on non-TEXT paths. 204 distinct lost `.txt` paths. a7654a8 vs head: 12,577 moved, 0 losses, all gains.
- Targeted `.txt` probe, 300 lines, light and standard, main / a7654a8 / head:
  - requirements/prod.txt, requirements/base.txt, constraints.txt, CMakeLists.txt, robots.txt, src/wordlist.txt: main ((), ('arch',)); a7654a8 and head ((), ()).
  - requirements.txt, requirements-dev.txt, src/requirements.txt, docs/requirements.txt: unchanged (quality / arch, quality, security).
- Path classes: as at a7654a8. `%xx` reads as code. `//`, `/./`, `/../` and `./` are refused by git ("Invalid path"), so they cannot reach needed() from GitHub filenames. Case and unicode variants of docs/ and specs/ lose nothing.
- Mutants, each in a fresh git archive copy of 4b535bd, tests/test_evidence.py:
  - t2 drop re.I: killed (1).
  - t3 drop the `^` on the spec-contract clause: killed (1).
  - t4 drop the `$` on LICENSE|NOTICE: killed (1).
  - t6 revert `wide` to the a7654a8 form: killed (3).
  - t5 contract over `wide`: survived, re-run in a fresh copy (t5b), survived again. Not equivalent; distinguishing input above.
  - t1 drop txt from TEXT (the suggested fix): 157 passed, so no test pins `.txt` as prose.
- Suite at head (scratch copy): 1708 passed, 2 skipped (/root/.local/bin/pytest -q).
- PR read once via REST: head 4b535bd, draft. Body carries `BREAKING CHANGE:` and `Announcement: CHANGELOG.md (placeholder: ...)`.
- Confidence medium: the differential and the targeted probe agree. The open judgement is whether the owner meant `.txt` as prose. The spec says yes, but docs/design.md:102 and the PROSE regex say no, and the Breaking section does not announce it.

## Residual risk
RISKY's `requirements[^/]*\.txt$` misses `requirements/*.txt` and `constraints*.txt`, so those dependency files never get security or quality on main or here. That is outside this item, and it deserves a follow-up.

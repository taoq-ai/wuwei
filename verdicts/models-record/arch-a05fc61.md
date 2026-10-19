Verdict: PASS
Gate: arch
Item: models-record
PR: taoq-ai/wuwei#1146
Head: a05fc614a2a456d89b39e652c8cffb7d70f0e9af
Confidence: high
Breaking: no (minor). Unchanged from 78429d9. The merge adds no runtime, test or docs content of its own: outside main's content, the delta is the resolved sentinel-arch charter and its generated copies, plus corrected numbers in specs/models-record/plan.md and spec.md FR-007. The classification at 78429d9 was read against main b5822fe's declared API. It still holds against c7e0cd1, which changes only the release files (plugin.json, manifest, CHANGELOG).

## Findings
- [medium] agents/sentinel-quality.md:5 blocks: no. Carried from 78429d9, unchanged by the merge. When a launch passes no `model` on Bedrock, Vertex or Foundry, the full model ID can fall back to the session model. The diversity gate then loses its second model family. This is disclosed under Residual risk and Release notes.
- [low] cli/wuwei/setup.py:140 blocks: no. Carried. With CLAUDE_CODE_SUBAGENT_MODEL set, the doctor note row says advice is off, but frontmatter outranks the variable, so it steers no WUWEI seat. The row does not say so. The PR records this under Assumptions.
- [low] cli/wuwei/hook.py:89 blocks: no. Carried. advise tells a condition key from a tier key by `' ' in when`, a convention only agents.py knows.
- [low] blocks: no. Carried. Item line budget: +60 runtime lines against the promise's 40. The overrun is disclosed under Size and in spec.md FR-007. Repository fitness functions hold (see Probes).

## Probes
- Merge shape: `git log -1 --format='%H %P %an' a05fc61` gives parents 78429d9 and c7e0cd1, author Leone. Merge base 5fe8347.
- Delta outside main's content: `git merge-tree --write-tree 78429d9 c7e0cd1` gave tree ec9b7f8. `git diff --stat ec9b7f8 a05fc61` shows only 6 files: the 4 sentinel-arch files (charters/, .claude/wuwei/charters/, agents/, .claude/agents/) and specs/models-record/plan.md and spec.md. Every other path equals the automatic merge.
- No runtime or test change slipped in. `git diff --stat 78429d9 a05fc61 -- cli/ tests/ .claude/wuwei/cli/` shows only tests/test_charters.py (+30). That file comes from main b5822fe and is absent from `git diff --stat c7e0cd1 a05fc61`, so it is byte-identical to main. `git diff --numstat c7e0cd1 a05fc61 -- cli/wuwei/hook.py` gives +40 -4, the same as the branch's own diff from the merge base.
- Charter rules from both sides. `git diff c7e0cd1 a05fc61 -- charters/sentinel-arch.md` shows exactly the branch's two trims ("That is the design document its process names"; rule 2 "read what each changed module imports and who imports it"). `git diff 78429d9 a05fc61` on the same file shows main's three changes: the shorter vocabulary line, the new SemVer rule 7, and "note it." These are all kept. In the generated agent, the common-rules Done line "a breaking change (a SemVer major)" also comes from main. Rules 1 to 6 are textually unchanged on both sides.
- Generated agents match the charters. I ran `bin/wuwei agents build` in a `git archive a05fc61` copy under sentinel-arch-models-record-r3/tree; it printed "agents match the charters". `cmp` of every agents/*.md against .claude/agents/ and every charters/*.md against .claude/wuwei/charters/: 0 differ. `diff -r cli/wuwei .claude/wuwei/cli/wuwei`: same. The model and effort frontmatter (claude-opus-5-5, high) is kept on sentinel-arch.
- Fitness functions at the head, in that copy: `wc -w agents/sentinel-arch.md` 2248 (ceiling 2250). `cat cli/wuwei/*.py | wc -l` 3086 (budget 3400). `len(ws.DEFAULTS)` 6. Suite: `python3 -m pytest -q` 1990 passed, 2 skipped. All agree with the builder's figures.
- Spec numbers: plan.md now says main 3,026 at c7e0cd1, runtime 3,086 (+60), hook.py +40 -4, headroom 314. spec.md FR-007 says 60 and 3,086. Each figure matches the measurements above. These are spec artifacts only.
- PR read once over REST (`gh api repos/taoq-ai/wuwei/pulls/1146`): draft, head a05fc61, mergeable true, mergeable_state clean, title without `!`. The Tests section names the merged head's suite and word counts.
- closed: the merge with main dirty in four sentinel-arch files, at a05fc61 (resolved as proposed at 78429d9; the result is main's charter plus the branch's two trims, 2,248 words, suite green).
- Confidence high. The delta is mechanical and fully explained by the merge-tree comparison. Every claim above was measured at the head in a fresh copy.

## Residual risk
As at 78429d9: a client that launches seats without `model` on a third-party provider, or that relies on CLAUDE_CODE_SUBAGENT_MODEL, sees different seats run; the Release notes tell them. Charter word headroom on sentinel-arch is now 2 words, so the next edit to that charter or the common rules must trim first.

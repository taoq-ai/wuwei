Verdict: FIX
Gate: arch
Item: free-lines-4
PR: taoq-ai/wuwei#1112
Head: 50f66d80d4c882f8f855495a3b2856809d29a031
Confidence: high
Breaking: no

## Findings
- [high] cli/wuwei/guards.py:17 blocks: yes. Failure: dropping `\|\|` from OPS is not equivalent, which breaks the promise (no behaviour change), FR-002 and acceptance 3 (0 differences). In a punctuation run `||&>` or `||&>>`, base splits `||`, `&>`, but the head splits `|`, `|&`, `>` because `\|&` now matches at the second pipe. On the acceptance-3 grid (24 ops in pairs, 6 words in pairs, 4 positions, 82,944 commands), guards.segments differs for 72 commands, all ending `<w1> <w2>||&>` or `||&>>`. guards.bash changes its decision for 162 of 1,372 targeted commands. 62 of them go from deny to allow: `x||&>|git push origin main` and `x ||&>& gh pr merge 5 --admin` now read `git`/`gh` as a redirect target with argv `push ...`/`pr ...`, so neither the unreadable-door refusal nor the push/merge door fires. bash, sh and dash reject all of these with a syntax error (stub git/gh on PATH, nothing ran), so no door actually ran. That is why this is high and not critical, but the guard now reads them differently than base did. Fix at zero line cost: keep `\|\|` in OPS (drop only `;;`), correct the trailing comment, and add an `x||&>y` -> x, ||, &>, y case to the split test. With `\|\|` restored, both probes match base exactly.
- [low] blocks: no. FR-005 says "the four ledger refusals"; there are three call sites (guards.py:314, 322, 347), the same three as at base. Correct the spec text.
- [low] blocks: no. zsh is not installed here, so how zsh runs `||&>|` is unmeasured. zsh has `&>|`, so the head's reading (target git, command push) may match zsh. That does not change the finding, which is about matching base.

## Probes
- git archive of 9d6701e and the head into scratch. `cat cli/wuwei/*.py | wc -l`: 2999 -> 2976 (23 freed). `diff -r` cli/wuwei vs .claude/wuwei/cli/wuwei: identical.
- Python floor: pyproject requires-python >=3.11 and the constitution says 3.11+. ast.parse(feature_version=(3, 8)) accepts every head module, so walrus in conditions and comprehensions is fine at 3.11. Suite at head: 1196 passed, 2 skipped (python 3.13).
- Differential probe of guards.segments, base vs head: the acceptance-3 grid plus every run of 1-5 characters over `();<>|&` (glued and spaced), 122,158 outputs. 82 differ, every one involves `||&>`. Same probe with `\|\|` restored in a patched copy of the head: 0 differ. The bash decision probe (1,372 commands) also matches base. So the `;;` drop alone is equivalent.
- Ran the deny-to-allow cases through bash, sh and dash with stub git/gh/push/pr on PATH: all three exit 2 with a syntax error and nothing runs.
- Contracts: LEDGER_DENIED holds the identical text, and no CLI output, message or exit code text changed. In bash(), the gh `elif` fall-through reaches only the INFRA branch, and gh is not in INFRA. _unwrap's if/else keeps input-redirect words out of targets and still skips them. Every walrus is parenthesised where it is negated.
- Headroom: 3000 - 2976 = 24. The queued items need shell-stdin 1 + records 12 + gh-args 3 + merge-evidence 4 = 20, which leaves 4. The fix costs 0 runtime lines, so the base stays sound for the queue.
- Confidence high: the difference reproduces in my own probe, and restoring one alternative removes it.

## Residual risk
The builder's 0-difference probe missed the trailing position, so other "equivalent" claims rest on how the probe is shaped. Exhaustive punctuation runs up to length 5 now cover OPS.

Verdict: PASS
Gate: quality
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: 38855c10e14946b3737c597133e74ec972268d6b
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:104 blocks: no. Readability: `(([] if re.fullmatch(r'<[<&]*', tokens[i]) else targets) if redirect else argv).append(...)` appends to a throwaway list to drop an input redirect's word. An explicit `if` is clearer.
- [low] cli/wuwei/guards.py:83 blocks: no. Readability: the `out = [UNREAD] if any(...) or any(a in REDIRECTS and (b in REDIRECTS and c != '(' or b in CONTROL - {'('}) ...)` one-liner is hard to read; naming the structural rule as a small helper or splitting it over lines would help.
- [low] cli/wuwei/guards.py:81 blocks: no. Surviving mutants, re-run in fresh copies. `(?<![<>]&)` narrowed to `(?<!>&)` only is not told apart from the full form, since it needs a contrived `<&3>x`. Narrowing `<[<&]*` to `<<*` survives too, because `<&word` is then counted as a target; that only over-refuses a path after `<&`. Pin both with a case each if wanted.
- [low] cli/wuwei/guards.py:83 blocks: no. The `tokens[2:] + ['']` end sentinel is equivalent to any other value (reversing it to `'('` survives): a trailing redirect already meets the `;` appended as `b`. The sentinel could be shortened.

## Probes
- Suite at head: `pytest -q` gave 1192 passed, 2 skipped. cli/wuwei/guards.py and .claude/wuwei/cli/wuwei/guards.py are identical. Runtime is 2999 lines (`cat cli/wuwei/*.py | wc -l`). A grep for em dashes found none.
- Prior finding closed: the multi-digit fd cases `10>x` and `true;12>x` now fail the single-digit mutant, and `git push origin main2>x` kills the removed-lookbehind mutant.
- Mutants on the new clauses (21), each applied to both the cli and vendored copies and run against the full suite.
  - Killed: both halves of the `(?<![<>]&)` lookbehind (removed, and `<&` only); the fd digit and lookbehind mutants; REDIRECTS entries `<<`, `<`, `<&`, `>|`.
  - Killed: the structural rule: off, `b in REDIRECTS` branch removed, `b in CONTROL` branch removed, the `(` exception removed or always true, `(` refused as `b`.
  - Killed: input-redirect handling: off, `<` only, no heredoc `<<`.
  - Killed: `i + 1 < len(tokens)`.
  - Survivors, all non-blocking and listed above: `(?<!>&)` only, the end sentinel, `<<*`.
- The old test changed on purpose, `segments('then echo a >')` is now UNREAD, matches the structural rule: a redirect with no word after it is unread.
- Simplicity: the OPS `&&`, `\|\|`, `;;`, `\|&` and `&>` alternatives remain equivalent to the single-character fallback; deletable, but harmless and now commented. The `''` end sentinel on line 83 is deletable by guarding the zip. Nothing trust-boundary is deletable.

## Residual risk
Behaviour is correct on every probe and every behavioural mutant is killed; what remains is readability of two dense lines and over-refusal-only survivors. I did not re-run the stub-git acceptance under bash at this head.

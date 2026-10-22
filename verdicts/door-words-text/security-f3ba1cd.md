Verdict: PASS
Gate: security
Item: door-words-text
PR: taoq-ai/wuwei#1245
Head: f3ba1cdee2be75aab753a3f84ddb2a2b1000253e
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:390 blocks: no. With re.I the found list echoes the command's own spelling, including the Unicode case folds Python matches for door letters (U+0130 and U+0131 for i, U+017F for s, U+212A for k), for example 'pu' + U+017F + 'h'. They are fold variants of fixed words, each item at most 40 characters, and main already refuses those commands.
- [low] cli/wuwei/guards.py:390 blocks: no. Carried from 80d7553: the .wuwei item echoes its run of '/' and '.', cut at 40 characters.

## Probes
- Delta: head f3ba1cd merges origin/main at 319a6d4 (#1248, #1249, #1250) into 80d7553. git diff origin/main...f3ba1cd -- cli/wuwei shows only the multi-line rule: the found refusal with re.I on both searches (the filter and the found list). It is the same in cli/wuwei and .claude/wuwei/cli/wuwei (diff of the two guards.py at head: identical). DOOR_WORDS at head carries main's (\.__main__)? for python -m wuwei hook.
- Route corpus differential: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at head, merge base 319a6d4 and current origin/main 1b8ef2b. 288 routes, head vs merge base: 0 verdict or decision moves, 3 reason moves (git push origin $'main'; git push origin $"main"; >&>x git push origin main), all "found: git push". Head vs current origin/main 1b8ef2b: 0 verdict moves, 4 reason moves; the extra one (gh pr create --draft) comes from a later main commit the branch does not hold, not from this PR. 0 routes differ from their recorded verdict.
- Generated probe at head vs merge base (python3 -I, stub gh exit 1 on PATH): 24 door spellings x 15 separators x 13 wrappers = 4680 commands.
  - Spellings: upper, mixed and .exe case; WUWEI.__MAIN__ hook; backslash path; Unicode case folds built with chr().
  - Separators: U+2028, U+2029 and U+0085 built with chr(), among others.
  - Result: 0 raised, 0 decision moves, 1451 found-refusals and 0 items outside git|push|gh|pr|api|repo|wuwei(.__main__)? hook|.wuwei[/.]*(/ledger)? under re.I, each at most 40 characters. 26 distinct items. Longest reason 333 characters.
- Cross-platform spellings main added, read at head: GIT push with a second line, echo $'a'; GIT.exe push, Git.EXE push, GH api, python -m WUWEI.__main__ hook, rm -rf .WUWEI/ledger, and cat '.wuwei\ledger' on two lines all deny with the new text (found: GIT push / Git push / GH api / WUWEI.__main__ hook / .WUWEI/ledger / .wuwei).
- Mutants (fresh git archive copy each, applied to both trees, run one at a time on test_guards -k windows_and_macos/door_words/multi_line): dropping re.I from the found search gave 4 failed (an upper-case door word then raises TypeError on None); dropping re.I from the filter gave 2 failed. Both killed.
- tests/test_guards.py at head: 2025 passed. The builder reports 3710 passed, 5 skipped for the full suite; I did not re-run the full suite in this delta round.
- Closed at 80d7553: no open finding carried; the found list stays closed (OWASP LLM01) and bounded (CWE-400).
- Scanner: no dependency, workflow or agent tooling changed in the delta; none was run, so it is unmeasured.
- Confidence high: the differential, the generated probe and both re.I mutants agree.

## Residual risk
Any new door word added with a broad wildcard could make the found list echo caller text. Python's re.I Unicode folds widen the refusal on main itself (non-ASCII look-alikes), but that only adds refusals and no command reaches a door through it.

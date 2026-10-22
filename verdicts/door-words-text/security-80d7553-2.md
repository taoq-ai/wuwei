Verdict: PASS
Gate: security
Item: door-words-text
PR: taoq-ai/wuwei#1245
Head: 80d75535c4d20efd080bc0c342a4870a00a1cab9
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:366 blocks: no. The found list is a closed alphabet rather than a strictly fixed word set: the .wuwei door word echoes its run of '/' and '.' (for example .wuwei/./././ledger), cut at 40 characters; no other caller text can reach the refusal.
- [low] cli/wuwei/guards.py:365 blocks: no. Existing gap, unchanged by this diff: segments() is quadratic on long input (400 KB about 2.5 s, 2 MB about 140 s at main and head alike); the door-word regexes add about 0.02 s at 400 KB.

## Probes
- Diff read: git diff origin/main...80d7553 -- cli/wuwei (merge base 8c38073 = origin/main). Only the refusal branch of guards.bash changes, identically in cli/wuwei and .claude/wuwei/cli/wuwei. The condition `any(all(...))` becomes a walrus over the same filter `all(re.search(w, command) for w in d)`, so the refusal condition is the same and `re.search(...)[0]` runs only on a matched word, so it cannot be None.
- Route corpus differential: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (same at main and head), 288 routes read through guards.bash at main and at head using the test_every_route_reads_as_recorded setup. Result: 0 verdict or decision moves, 3 reason moves, all "found: git push": git push origin $'main'; git push origin $"main"; >&>x git push origin main. 0 routes differ from their recorded verdict at either side.
- Generated combinatorial probe (python3 -I, head and main guards loaded side by side, stub gh exit 1 first on PATH, gh tokens cleared): 17 door spellings x 19 separators x 13 wrappers = 4199 commands. Separators include \n, \r, \r\n, \t, \x0b, \x0c, \x1c-\x1f, U+2028, U+2029, U+0085 (built with chr()), U+00A0, U+3000, U+1680, backslash-newline, 300 spaces and 50 newlines. Wrappers include heredoc, $(, backtick, bash -c, cd, env -C, sudo -D and a 5000-character prefix. Spellings include quoted and $'' forms and .wuwei with long ./ and / runs. Result: 0 raised, 0 decision moves between head and main, 1365 found-refusals, 0 found items outside {git, push, gh, pr, api, repo, wuwei hook} plus .wuwei[/.]*(/ledger)? of at most 40 characters; 13 distinct items; longest reason 333 characters. This probe calls guards.bash in Python and does not execute a door program, so "ran the door program" is not applicable here: the parser is unchanged.
- Large inputs at head: 2 MB 'git push' plus filler gives a 301-character reason; 200 KB slash run after .wuwei gives 333; 200 KB spaces between wuwei and hookx gives 298; 400 KB of repeated .wuwei// gives 311. None raised.
- Timing main vs head (segments, door-word regexes, bash) at 100/200/400 KB: same within noise. The slowness is in segments() and is the same on both sides (second note).
- Mutants (fresh git archive copy each, applied to both trees, run one at a time on tests/test_guards.py -k door_words/multi_line[/route]): dropping the [:40] cut was killed by test_the_door_words_found_are_listed_each_once_and_bounded (1 failed); negating the found condition gave 38 failed; skipping the whitespace/quote normalisation gave 1 failed (wuwei backslash-newline hook case). All killed.
- Full suite at head (git archive copy): pytest -q tests gave 3602 passed, 2 skipped.
- Trust boundary: the refusal text goes back to the model. Because the found list is a closed vocabulary, caller-supplied prose (heredoc bodies, quoted text) cannot steer the model through it (OWASP LLM01). The message is bounded at 4 groups x 2 items x 40 characters (CWE-400). No secret or path beyond .wuwei slashes is echoed (CWE-532).
- Secret or dependency scanner: no dependency, workflow or agent tooling changed, so none was run; unmeasured.
- Confidence high: the reported route differential reproduces exactly (0 verdict moves, 3 reason moves), the vocabulary holds over 4199 generated commands including all three Unicode separators, and the mutants are killed.

## Residual risk
New door words added to DOOR_WORDS later would need wildcards kept to closed alphabets, or the found list could echo caller text. The quadratic segments() cost on very long commands is unchanged and remains.

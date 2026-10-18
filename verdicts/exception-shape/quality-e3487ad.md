Verdict: PASS
Gate: quality
Item: exception-shape
PR: taoq-ai/wuwei#1136
Head: e3487adc9efb2678f8283bf174ede67df2b42179
Confidence: high

## Findings
- [low] tests/test_guards.py:295 blocks: no. The new linear-time test depends on wall-clock time (perf_counter < 0.5 s). I measured the margins. At the head, each of its 6 inputs takes at most 2 ms, so a pass has 250x headroom. The mutants it exists to kill take 4.38 s (lookbehind removed) and 2.15 s (non-possessive spaces), about 4x to 9x over the limit. A flake in either direction is unlikely, so this is a note, not a defect.
- [low] blocks: no. Carried from my note (a) at 353b6f7, partly closed. The empty gap followed by a newline (`exception: o/r#1 at abc1234:\nAccept?`) is now refused. A gap followed by a newline and then the question (`...: no test in the diff\nAccept?`) still passes, and the hook records "no test in the diff\nAccept": hook.exception_refs ends a gap only at ". " or "?". This is 378 of the 3,150 passes in my probe. It existed at main, needs a hook-side change, and the answer is still recorded, so it is a follow-up candidate.
- [low] guards.py:373 blocks: no. Carried: the owner review:/breaking: branch is unchanged, and no test holds its leading `\s*`. Mutant R15 survives, re-run in a fresh copy (1343 passed). It only refuses more, so nothing gets through.

## Probes
Delta 353b6f7..e3487ad: regex in guards.py:373-374 (vendored copy identical by `diff -r`), 20 test lines in test_guards.py, 20 in test_hook.py, spec docs. Runtime is 2,977 lines.
Suite at the head, git archive copy: 1710 passed, 2 skipped (test_release.py:36 and :57, ssh-keygen absent).
Previous blocking finding (G12, lookahead narrowed to `.*`): closed. As R2 it is killed by the new refusal case and the newline tails in the agreement test.
Previous notes: (b), whitespace other than a space around the colon, is closed (R5 and R7 killed). (c), a ref in the prose prefix, is closed: `[^#]*?` refuses it (R3 killed), and my probe shows 0 refs drifts. The quadratic note is closed: 160,011 characters take 2 ms. (a) is partly closed (see above). The G13 redundant `\b` is not re-measured at this head and no longer listed.
Agreement test: it now compares the hook's refs and gap with the written chain and gap, which is a real oracle. It covers 7 prefixes x 6 refs x 13 seps x 10 gaps x 8 tails = 43,680 questions, and reaches guards.pre_tool and hook.exception_refs.
Route corpus: routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at main efcd9e7 and at the head. 251 of 251 routes were dumped through guards.bash at both, and 0 moved.
Generated probe (scripts/probe2.py, fixtures built in Python): 11 prefixes x 15 refs x 20 seps x 15 gaps x 10 tails = 495,000 questions. Head: 3,150 passed, 3,150 recorded, 0 holes, 0 ref drifts, 378 gap drifts (all newline-then-question, see the note). Main: 377,400 passed, 286,746 holes. Decision diff, main to head: 374,250 newly refused, 0 newly passed, 0 refusal reasons changed. Old head 353b6f7 to head: 23,472 newly refused, 0 newly passed, 0 reasons changed. The change only ever refuses more.
Over-refusal check: every gap string in evidence.py's gap() calls starts with a letter or digit ('gates missing...', 'CI failing...', '{n} review threads...', 'no test...'). The `[^\W_]` first character therefore refuses no gap that `wuwei evidence` prints. A `#` in the prose prefix is now refused; the refusal names the shape.
Mutants: 17 run, each in a fresh git archive copy, with test_guards and test_hook. 16 were killed (R1 lookahead removed, R2 `.*` lookahead, R3 `[\s\S]*?` prefix, R4 lookbehind removed, R5 `\s*` both sides, R6 `\s*` after, R7 `\s*` before, R8 `\w` gap, R9 old gap class, R10 non-possessive, R11 and-chain removed, R12 leading `\s*`, R13 case-sensitive, R14 repo required in the chain, R16 gap character dropped, R17 optional colon). 1 survived: R15, in a branch this change does not touch, re-run in a fresh copy.
Confidence high: every count was re-derived at e3487ad, and the one survivor only refuses more.
Simplicity: none. Each new piece (lookbehind, possessive, `[^#]`, `[^\W_]`) is held by a killed mutant. The shared ref/gap parser remains a follow-up, as noted at 353b6f7.

## Residual risk
A gap that runs onto a new line before the question is recorded with that line included; this is a hook-side limit, older than this item. The linear-time test uses wall-clock time, with wide margins on both sides.

Verdict: PASS
Gate: security
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: f7d9ccd68960aba401e9efa25acc67f99b8eefaf
Confidence: high

## Findings
- [low] blocks: no. Closed from security-e82601e: the hook.py:245 re.match to re.search mutant is now killed by the two new cases in test_a_ruling_names_a_pr_in_ascii_digits_only (the exception question and the scope question).
- [low] blocks: no. Two guard mutants still survive, re.match to re.search and dropping \b at guards.py:346. Both fail closed (the guard lets the question through and the recorder records nothing), as noted in security-e82601e.
- [low] blocks: no. This predates the change: evidence.owner_approved counts an approved ruling of any kind as owner approval.

## Probes
- Delta e82601e..f7d9ccd is test-only (git diff --stat: tests/test_hook.py, 4 insertions, 2 deletions). cli/ is unchanged, so routes.json and the guard results stand as at e82601e (corpus sha256 93d26ddc4551ca97183df579631b05392c0af8edc7cd59d776163e8d16ffa20f).
- Suite at this head, in a git archive copy: 973 passed, 2 skipped.
- Mutant re.match to re.search at hook.py:245, in a fresh copy: 2 failed (the exception case and the scope case), 970 passed.
- The exception-row filter could hide an owner review row only if that row carried kind exception. Mutant tagging owner review rows kind "exception", in a fresh copy: 3 failed (test_an_owner_answer_becomes_a_ruling and two positive owner review cases). The filter therefore cannot hide a mis-tagged owner review row. Breaking rows keep kind breaking and are compared.
- m3.py probe at this head: the exception question with embedded owner review text records no owner review row, and x/y#2 owner_approved is False (main gives True).
- rulings.py battery output is identical to e82601e. e2e.py gives lib#3 False and app#9 False.
- Confidence is high because both mutants were run in fresh copies and the runtime is unchanged from the head already probed.

## Residual risk
owner_approved accepting rulings of any kind predates this change. The guard over-admission mutants fail closed and are held by no behavior test.

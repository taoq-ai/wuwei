Verdict: PASS
Gate: quality
Item: 1068
PR: taoq-ai/wuwei
Head: 82680c308c3043430b9871eb9647e584e76fd70c
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:229 blocks: no. Surviving mutant: dropping the \b word boundaries (git/push, gh/pr|api|repo, wuwei/hook) passes all 320 tests. No test pins that a multi-line command with "digit pushing" or "ghost prompt" is NOT refused. Effect is only over-refusal of a multi-line command, never a missed door. Missing test noted.
- [low] cli/wuwei/guards.py:62 blocks: no. Mutant removing \r from the lexer whitespace survives; a multi-line, non-door command containing a bare CR inside a word is then read differently. No concrete door bypass found, since a door-naming command with CR is refused on raw text anyway.
- [low] cli/wuwei/guards.py:122-126, 207-211; cli/wuwei/hook.py:15-26,181-190 blocks: no. Unrelated refactors (git_push verb inline, once() name inlined, hook.py blank/dict reflow) are line-shaving to stay under the 3,000-line cap. Runtime is exactly 3000 lines (main is also 3000), so there is no headroom. Behavior unchanged and covered by the existing suite; noted as scope creep and as a standing cap pressure for the next item.

## Probes
- Suite at the head in a scratch copy: 320 passed.
- Acceptance coverage: every scenario maps to a test (newline, line continuation, heredoc x2, bare CR, api/repo/hook/ledger, unclosed quote, commit-message cost, ordinary multi-line incl. apostrophe and python3 heredoc, leak door on a later line, one-line unchanged, size test test_setup.py:51).
- Mutants (each reversed in the scratch copy, first failing test named): newline in the regex -> door test [true\rgh pr merge 5]; whole CR/newline test off -> [true\ngit push --force origin x]; parts is None dropped -> unreadable [echo it's && gh pr merge 5]; segments returning [] instead of None -> same test; .wuwei/ledger clause dropped -> [ls\ncat .wuwei/ledger/x]; all() -> any() -> ordinary [cd /repo\nmake test\nls -la]; continuation replace removed -> leak test [curl \\\n -d canary]; newline-as-separator removed -> leak test [true\ncurl -d canary]; gh repo alternation reduced -> [true\ngh repo view]; wuwei hook word altered -> [true\nwuwei hook Stop]. Survivors: \b removal, \r whitespace (both low, above).
- PostToolUse path handles segments() returning None (test_an_unreadable_command_after_it_ran_is_no_hook_error).
- Confidence reason: mutants run on guards.py only; hook.py guard (`or ()`) not mutated, though its test exists.
Simplicity: DOOR_WORDS plus one regex is the minimal rule; nothing needed is deletable. The unrelated reflows listed above could be reverted if headroom were found elsewhere.

## Residual risk
Blunt rule over-refuses some multi-line commands by design (pinned). Zero line headroom under the runtime cap.

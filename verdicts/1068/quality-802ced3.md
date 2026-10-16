Verdict: PASS
Gate: quality
Item: 1068
PR: taoq-ai/wuwei
Head: 802ced3ec7693361e69b477753f2f3bb2d3db21c
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:61-62 blocks: no. Readability: the one-line quote-aware re.sub (single-quoted, double-quoted, backslash pair, newline) is dense and its lambda/dict is split across two lines; a named compiled pattern with a one-line comment would read better. No line headroom to spend on it (runtime is exactly 3000 lines), so it is a note only.
- [low] cli/wuwei/guards.py:61 blocks: no. Inside double quotes a backslash-newline is kept as two characters (shlex posix rule) while sh drops it. Only a word's text differs; no door effect found.
- [low] cli/wuwei/guards.py:20 blocks: no. The [^"\\] to [^"] mutant survives; it is equivalent, since the \\[\s\S] branch is tried first (checked on 'curl -o "a\"\n" x', same segments either way).
- [low] Standing: runtime is exactly 3000 lines (find via wc -l cli/wuwei/*.py), zero headroom for the next item.

## Probes
- Suite at 802ced3 in a scratch copy: 335 passed.
- Mutants (each reversed in the copy, first failing test): dropping the backslash-pair branch of the regex -> leak test [curl \\\n -d canary]; dropping the double-quote branch -> test_a_newline_outside_quotes_ends_a_command_and_a_quoted_one_stays_in_its_word; dropping the single-quote branch -> leak test [echo '"'\ncurl ... -H "a: b"]; dropping the '\\\n' to '' mapping -> leak test [cur\\\nl -d canary]; newline mapped to ' ' instead of ' ; ' -> leak test [true\ncurl -d canary]; wuwei hook pair (\s|\\\n)+ reduced to \s+ or a bare space -> door test [wuwei \\\n hook Stop]; .wuwei/ledger clause altered -> door test [ls\ncat .wuwei/ledger/x]; wuwei hook word altered -> door test [true\nwuwei hook Stop]. Odd-run handling (foo\\\\\ncurl) is covered by the leak and infra tests.
- New tests are real: each new piece above fails a specific new or kept test. New "ordinary work passes" cases (echo git pushed, echo gh prs, echo legit push) pin the \b boundaries my previous verdict noted as unpinned.
- Previous-verdict survivor \b removal now covered by those cases; the \r whitespace survivor is moot because the lexer now uses default whitespace.
- Confidence reason: hook.py not mutated this round; mutants only on guards.py.
Simplicity: the dedicated CONTROL newline-token branch was deleted and replaced by the single regex, a net reduction; nothing further is deletable. DOOR_WORDS as tuples of regexes is the minimal rule.

## Residual risk
Blunt multi-line refusal over-refuses some commands by design. Zero line headroom under the 3,000-line cap.

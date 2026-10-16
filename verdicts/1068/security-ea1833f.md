Verdict: PASS
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: ea1833f7d5ba7b02f8ec8853e54f6500521afdb5
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:21 blocks: no. Previous high finding (a quoted wuwei path or a quoted hook word slipped past the narrowed pair when shlex could not read the command): closed. `\bwuwei['"]?(\s|\\\n)+['"]?hook\b` now refuses all three shapes: the heredoc with an apostrophe followed by `"${CLAUDE_PROJECT_DIR}/.claude/wuwei/bin/wuwei" hook SubagentStop`, `# it's<nl>"$D/.claude/wuwei/bin/wuwei" hook Stop`, and `# it's<nl>bin/wuwei 'hook' Stop`. Tests pin all three.
- [low] cli/wuwei/guards.py:240 blocks: no. `bin/wuwei --x hook Stop` after an unreadable line still passes, where 82680c3 refused it. The segment door misses the same option shape on one line on main, and option shapes belong to compound-doors. Carried from the previous verdict.
- [low] cli/wuwei/guards.py:61 blocks: no. These notes are unchanged from the previous verdicts: `"cur\<nl>l"` inside double quotes, which is quote obfuscation and the same as main; unreadable commands with no door word fail open for leak and infra; newline-glued redirects; `.wuwei//ledger`.

## Probes
- Suite in a scratch copy at ea1833f: `/root/.local/bin/pytest -q` gave 338 passed, the size test included.
- cases.py (65 commands) ran against origin/main, 82680c3 and ea1833f, each exported into the scratch dir. No command that main denies or asks gets None on ea1833f. Compared with 802ced3, the three blocking shapes moved from None to deny and nothing else changed. 82680c3 refused 2 commands that ea1833f passes: `bin/wuwei --x hook Stop` (noted above) and `bin/wuwei \<CR><nl>hook Stop`, which bash does not run as a hook call (an escaped CR and then a newline).
- Mutants, each applied in a copy, with the test that kills it. Optional leading quote dropped: the heredoc `"${CLAUDE_PROJECT_DIR}/.../wuwei" hook` case. Optional trailing quote dropped: the `bin/wuwei 'hook'` case. Pair widened back to wuwei...hook: the `sed ... hooks.json` false-positive case. The 6 segments() and continuation mutants from the last round were rerun on this head and all are still killed.
- The new regex on 200 KB of adversarial input (`wuwei"` plus whitespace, repeated `wuwei" `, a long run of backslash-newlines) took 0.034 s or less, so no backtracking blowup.
- Confidence is high: every case comes from running the same inputs on all trees, and the change since 802ced3 is one regex line plus tests.

## Residual risk
The raw-text door rule is still a word regex. Splicing, ANSI-C quoting and option shapes stay out of scope by the plan. The leak and infra doors still depend on shlex reading the command, as they do on main.

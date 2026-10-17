Verdict: FIX
Gate: arch
Item: shell-stdin
PR: taoq-ai/wuwei#1115
Head: f7e30fbfd02531e999589f7cf383310cabb8579d
Confidence: high
Breaking: yes: a Bash command that runs sh, bash, zsh or dash with no readable -c body (fed by a pipe, a here-string, -s, < file, or given a script path, including bash -o pipefail -c) and whose raw text names a door program is now refused as unreadable, so seats chaining a script run with a door command (bash scripts/check.sh && git push origin feature) or feeding door text to a shell must split the call; a door command after a named-fd redirect ({fd}>x gh pr merge 5) now meets its door

## Findings
- [medium] SECURITY.md:47 blocks: yes. Failure: SECURITY.md is the published list of shapes the guards do not read, and every earlier guard fix kept it in step (#1109 added this very line and removed the shapes it closed). At this head it still says `{fd}>x git push origin main` is not read, and line 39 still lists input piped or fed to a shell (`| sh`, a here-string) as unread without saying it is now refused when the text names a door program. A reporter or owner reading the policy gets the wrong behavior for both shapes the item changes. Fix: drop the named-fd line, add `{fd}>x` to the redirect list (line 29), and say on line 39 (or in the closing paragraph at line 51) that a shell with no readable -c body is refused when it names a door program while its fed text still meets no leak or infra check.
- [low] docs/design.md:149 blocks: no. The new sentence lists a pipe, a here-string, `-s` and `< file`, but the code also marks a shell given a script path (`bash run.sh`) unreadable, which is exactly what causes the declared false refusal of `bash run.sh && git push origin x`. Add "or a script path" with the SECURITY.md fix.
- [low] blocks: no. The PR's BREAKING CHANGE line says "without -c"; `bash -o pipefail -c '<door command>'` and `bash --rcfile f -c ...` carry -c yet are newly refused (spec Clarifications names this). Worth a word in the BREAKING CHANGE line; no traced route has the shape.
- [low] blocks: no. Shells outside SHELLS (`ksh`, `busybox sh`) fed door text still pass, the same as main; outside the promise, a candidate for the plan.

## Probes
- Promise and acceptance read with `wuwei plan show shell-stdin`; PR read via `gh api repos/taoq-ai/wuwei/pulls/1115`: draft, head f7e30fb, title carries `!`, body has BREAKING CHANGE, Breaking, Migration and Rollback lines.
- Trees at 86135fa and f7e30fb extracted with `git archive` into scratch; vendored `.claude/wuwei/cli/wuwei/guards.py` is byte-identical to `cli/wuwei/guards.py` at head.
- Suite at head copy: `pytest -q` gives 1237 passed, 2 skipped (matches the PR).
- Traced seat routes: all 2,976 Bash targets in `.wuwei/traces.jsonl` run through `segments` plus the raw-text rule at main and head: 0 verdict moves; 39 gain the UNREAD marker (`bash <scratch>/mut.sh`, `sh $S/setup.sh && ...`) and name no door program, so they still pass.
- Charters, skills (`skills/`, `.agents/skills`, `.claude/skills`), `.specify`, hooks and docs/site grepped for a shell fed on stdin or `bash|sh <script>`: none; speckit skills run `.specify/scripts/bash/*.sh` as the program itself, not through a shell, so they are not newly refused.
- Wrapper probe (file-fed, head vs main): `sudo bash`, `nohup bash`, `time bash`, `xargs -0 sh`, `exec bash`, `stdbuf -o0 bash`, `timeout 5 bash`, `nice -n 5 bash`, `/usr/bin/env -S bash` fed `git push origin main`, and `echo 'gh pr merge 5' | bash`: all pass on main, all refused at head. `bash scripts/check.sh && git push origin feature` refused at head (the declared false refusal); `bash run.sh .wuwei/x` passes (the .wuwei door word needs `.wuwei` alone or `/ledger`). `ksh` and `busybox sh` pass on both.
- Design fit: the change reuses the existing UNREAD marker and the raw-text door-word rule (design.md 146-153), adds no door, config key or contract field; constitution (stdlib only, test first, line budget) holds.
- Line headroom: runtime `cat cli/wuwei/*.py | wc -l` is 2,976 at main and head (the budget test counts the same way). records (+12 est, budget 18) and gh-args (+3 est, budget 5) land at 2,991 on estimates and 2,999 at full budgets, both within 3,000.
- `docs/site/concepts/doors.md` does not list unreadable shapes, so no change is owed there (spec Assumption holds).
- Confidence high: the code change is two existing lines, the route and trace corpora are unmoved, and the blocking finding is a docs omission read directly from SECURITY.md at head.

## Residual risk
A seat that names a door program in a script path or argument beside a shell run (a scratch file named git-push-probe.sh) is refused; traces show none today. A shell fed an infra write or a leaking curl still passes, the same as main.

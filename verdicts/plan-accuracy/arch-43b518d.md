Verdict: PASS
Gate: arch
Item: plan-accuracy
PR: taoq-ai/wuwei
Head: 43b518df9ce5cbcfc6e151281f35355e0762e8fd
Confidence: high
Breaking: yes: scripts that call `wuwei plan run <id>` without --reason now exit 2 and record nothing (it exited 0 with an empty reason), and `wuwei plan add --from` on a file that is neither a list nor {"candidates": [...]}, or has an entry without id or title, now exits 2 (it exited 0 adding nothing, or crashed with KeyError after a partial add). Every in-repo caller (charters/_way.md, charters/planner.md, skills/wuwei-watch, skills/wuwei-plan, charters/lead.md) already passes --reason and writes the list shape, and the approved promise asks for exactly these refusals

## Findings
- [low] cli/wuwei/__main__.py:51 blocks: no. The reason check runs before the item lookup, so `plan run NOPE` without --reason reports the missing reason, not the missing item. Both exit 2 and record nothing, so this is harmless.
- [low] cli/wuwei/__main__.py:198 blocks: no. The actions table puts `restore` before `run`, so the choices order in the usage line and the invalid-choice message changed (show,add,park,drop,done,restore,run,pass,view). Cosmetic. Commands, flags, defaults and the other exit codes are unchanged.
- [low] cli/wuwei/plan.py:62 blocks: no. Cleared approval shows as "awaiting plan approval" only for an item with no linked PR and not of kind run (board.py:79-82 checks run evidence and linked PRs first). Acceptance scenario 2 covers only the no-PR case, so this is a limit, not a violation.
- [low] blocks: no. Callers checked: plan.followup (hook.py:255) always creates a fresh X-n id with no promise and then sets approved=True, so exception follow-ups keep their approval. upgrade.py builds items with its own _add and its own candidates reader, so neither the shape check nor the approval clearing touches it. Re-adding the same candidates file keeps approval, because the JSON lists compare equal.

## Probes
- Ran `git diff origin/main...43b518d` (merge-base 1620583 = origin/main) and read plan.py, __main__.py, board.py, hook.py:255 and upgrade.py:103 at head.
- Ran `git grep "add_from|plan.add(|followup|candidates|plan run"` at head to find every caller: the CLI (add, add --from), the hook's followup, the charters and skills. upgrade.py has a separate reader.
- Wrote scratch cmp.sh, which runs the same 25 plan commands against git-archive trees of base and head in fresh `wuwei init` workspaces, then diffed the output. `wuwei --help` differs only in the plan help string. `plan --help` gains the actions block with one line per action. The only exit-code differences are `plan run B` without --reason and `add --from {"items":...}`, which went from 0 to 2. Every other action (show, show id, park, drop, done, restore, run --reason, pass, view, bad choice, bad tier, bad score, empty list, valid candidates) gives the same output and exit code on both.
- Ran `diff -r cli/wuwei .claude/wuwei/cli/wuwei` at head: the vendored copy is identical. Runtime is 2,947 lines by wc, under the 3,000 cap.
- Ran the head suite with /root/.local/bin/pytest -q: 479 passed, 2 skipped. tests/test_plan.py: 20 passed.
- Compared docs/site/reference.md with the behaviour: it names the shape, the approval rule and `plan run ... --reason`, and docs/design.md:115 already writes `plan run <id> --reason`.
- Confidence is high because I traced every caller and the base/head comparison is direct.

## Residual risk
External scripts or old lead outputs that relied on a reasonless `plan run`, or on a silently ignored file shape, will now fail loudly (Breaking: yes above). The merge should carry the owner's breaking acknowledgement.

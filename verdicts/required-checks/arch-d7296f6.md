Verdict: PASS
Gate: arch
Item: required-checks
PR: taoq-ai/wuwei#1176
Head: d7296f6014efd31d9d682f7fef365ef08213a85e
Confidence: medium
Breaking: no (patch). At this head no route the base docs promise to pass is refused. Arming auto-merge still passes while CI runs, also when a required check has no run yet, and when only GitHub's own hold is left. Two kinds of call are now refused. (a) Any merge, auto included, once CI has settled with a required check that never ran. The base Done table already promised "CI green: the repository's own checks", and GitHub's auto-merge would never fire in that state anyway. (b) A direct merge GitHub reports blocked. That is an admin bypass of the base's own rules, the kind the Admin bypass door already refuses. In both cases the old behaviour contradicted the documented API. This verdict is a later "no" from a strict descendant of 19ede00, so it clears the "Breaking: yes" there, and no Announcement is needed.

## Findings
- [low] blocks: no. Item budget (constitution VI): the promise says "Runtime estimate +8, budget 10". The head adds +16 (3,208 to 3,224). plan.md names the 6 extra lines and the 4 lines moved. The repository budget of 3,400 holds, and constitution VI lets an item over 10 lines go ahead once it names its lines. This is for the retro.
- [low] blocks: no. The PR body is stale against the head. It still says 3,218 (+10) and gives the two-host differential (514 cases, 23 moved). At d7296f6 the count is 3,224, and the six-host differential gives 1,542 cases with 64 moved. plan.md says the body lists every moved route, including the other/x#5 row that was already refused at main. Update the body before the PR turns ready.
- [low] blocks: no. Carried: a MERGED PR is read against today's protection, so a check added later, or a host error, shows as a post-merge escape that never happened.
- [low] blocks: no. Carried: gh.pr reads only the first 100 check runs of a head, so a head with more can show a required check as not run. This fails closed.

## Probes
- Route differential: I ran specs/required-checks/route_diff.py through hook.handle at main 646e462 and at the head (copies made with git archive, Python 3.11.15, pytest 9.1.1 in a scratch venv). The corpus sha256 is 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 at both: 257 routes, 1,542 cases, 64 moved. No case went from refused to allowed. By host:
  - none 0, running 0, blocked_running 0.
  - required 23: 22 merge routes of o/r#5 went from allowed (merge.checked) to refused with "required check not run at aaaaaaa: test (3.11)", including `5 --auto`, `5 -t --auto` and ccr/auto_merge. The 23rd, `gh pr merge https://github.com/other/x/pull/5 -R o/r`, was refused at both naming other/x#5 and only gains that line.
  - blocked 20: every one is a direct merge route (15 PUT spellings on merge, `--repo=o/r 5`, `-R a/b -R o/r 5`, `5 --auto=false`, `5 --squash`, `5 -t --auto`), allowed to refused with the blocked gap. `5 --auto` and ccr/auto_merge stay allowed.
  - required_running 21: every one was already refused at main with "CI running" and now also lists "required check not run yet". `5 --auto` and ccr/auto_merge stay allowed at both.
  - `5 -t --auto` reads as a direct merge at both main and head. That is existing parser behaviour, not changed here.
- closed: evidence.py:448 (auto-merge refused while a required check is not created yet) at d7296f6. The required_running host keeps `--auto` and ccr/auto_merge allowed, the gap is waiting, and test_a_required_check_not_yet_created_while_ci_runs_waits_and_lets_auto_merge_arm covers it.
- closed: the blocked gap refusing auto-merge, at d7296f6. It is exempt under auto through evidence.AUTO and is now waiting, which also settles the "who acts" note.
- closed: the docs disagreement at d7296f6. doors.md, design.md section 7 and the Done table (design.md:88) now agree with the evidence.md table.
- Placement: guards.merge_door reads the exempt prefixes from evidence.AUTO instead of a string written into guards. This is the same dependency direction as base (guards imports evidence). `settled` is computed once and shared with the PR warm cache, so no logic is duplicated. gh.rules now URL-encodes the branch (`/` kept), and setup.doctor still gets a list.
- Mutants: I applied four, each to both runtime copies, one at a time in a fresh git archive copy, and ran test_evidence, test_hook, test_status_perf and test_replay. All four were killed.
  - AUTO without the "not run yet" alternative: 2 failed.
  - AUTO without the blocked alternative: 2 failed.
  - `settled` always True: 4 failed, including test_status_perf.
  - merge_door back to the "CI running" literal: 4 failed.
- Budget: `cat cli/wuwei/*.py | wc -l` gives 3,208 at main and 3,224 at the head. `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows the copies identical.
- Suite at the head: 2,194 passed, 4 failed, 1 skipped. The 4 failures are three test_bash_runs_the_push_in_each_refused_shape cases and test_the_hook_commands_run_under_either_harness_shell. They fail the same way at main on this machine's bash 3.2.57, so this change did not cause them.
- Confidence is medium. The differential and the mutants are measured. That GitHub's auto-merge waits on required checks and on its own hold even for admins comes from GitHub's documentation and the spec's recorded assumption; I did not probe it live.

## Residual risk
The 15-minute cache can delay a newly added required check. A token that cannot read the branch or its rules holds every merge in its repository, with the error named. Both are recorded assumptions and fail closed.

Verdict: PASS
Gate: arch
Item: builder-host
PR: taoq-ai/wuwei#1251
Head: 57d90a2fac28bbb537ffa68490d49cdfd9d741fb
Confidence: medium
Breaking: no (minor: an optional --host flag defaulting to agent, a new plan action, an additive plan field; items without host read as agent)
Supersedes: builder-host/arch-9019115.md

## Findings
- [low] cli/wuwei/board.py:167 blocks: no. A session that dies after opening its draft PR still counts as live and never shows stale. It surfaces only because the board row always names the session and the charter (planner.md:45) has the planner read get_session whenever the board names it.
- [low] blocks: no. The hook's held check still leaves hosted builders out, so a second planner session is not refused when it launches a duplicate Agent-tool builder on a hosted item; only the board row warns.
- [low] blocks: no. The planner charter grows from 1923 to 2075 words (wc -w) and is read at every session start. No word budget covers it, so its size is unmeasured.

## Probes
- git fetch origin: origin/leone/builder-host is at 57d90a2. The delta 90191150..57d90a2 touches 14 files, +107/-50.
- closed: start params at 57d90a2. planner.md:40-43 now names source_revision (the default branch, or the item's branch once it exists), outcome_branch (the item's branch), the table's builder model, and this session's permission mode.
- closed: dead or blocked session held its item unseen at 57d90a2. planner.md:44-47 reads get_session when the board names the session or shows it stale, answers a blocked one with send_message, and replaces a failed one or one completed with no draft PR. board.py:167-168 shows a session item with no PR as stale after STALE_HOURS idle; the item.open row from plan session starts that clock.
- closed: new session per fix round at 57d90a2. Fix rounds now go to the recorded session with send_message, and archive_session runs once the item merges, parks or drops.
- closed (note): plan session reopened a closed item at 57d90a2. My earlier probe script (probe_session.py) at the new head gives rc 2, status stays done, and the hosted live list is empty; at 9019115 it gave rc 0 and reopened the item.
- Mutant 1, run in an archive copy: dropping the status check in the plan session branch of __main__.py fails test_plan_session_records_a_host_session_builder_and_refuses_an_agent_item (killed).
- Mutant 2, run in an archive copy: replacing the no-PR session clause in board.flow with False fails test_a_session_builder_with_no_pr_after_four_hours_shows_stale_so_a_dead_session_surfaces (killed).
- Targeted suite in an archive copy of the head: pytest on test_charters, test_plan, test_flow, test_watch and test_setup gives 378 passed. The full suite was not run, per the brief.
- Runtime fitness function: cat cli/wuwei/*.py | wc -l gives 3710 (main 3697), under the 3,800 budget. The vendored cli and the planner charter match the tree (diff -r shows no difference).
- Docs: the delta to design.md section 6 and reference.md matches the charter and runtime (closed items refused, stale at four hours with no PR, the get_session, send_message and archive lifecycle).
- Layering: no new imports. The hook's held check and Stop hook still read running() without hosted seats. The new test_watch assertions show a gate launch on a hosted item is not refused and the hosted record does not quiet the builder session's Stop.
- Confidence is medium because the create_session, send_message and get_session facts are the brief's account; I did not call those tools.

## Residual risk
A long session still working after four hours with no PR also shows stale, and the planner must tell that apart from a dead session with get_session. The lifecycle relies on the planner following the charter, not on runtime.

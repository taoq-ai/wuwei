# Specification Analysis Report: 902-one-action

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | `decide` runs on the hook path (next derives it at SessionStart and in every `wuwei next`); a write there would break the hook budget and purity. | Resolved: `decide` reads state, events, git files and owner answers only; every write (tier, release, park, fix round, recheck, polish) stays in `next_step` and `_act` (FR-001). `test_offers_write_nothing` still passes. |
| A2 | HIGH | merge reading the receipt instead of the file could look like a lowered merge protection. | Resolved: `receive` lints the file before it records the receipt; the records floor keeps the planner off `decisions/`; a file changed afterwards could only block a merge, never pass one; derive already reads the receipt (#844 F3) (FR-006). |
| A3 | HIGH | A Blocked: line now passes the strict spec stop guard; a builder could use it to skip writing its spec. | Resolved: the owner is asked before the checks (FR-009); the spec gap still fails the build check and the dispatch backstop, so no item reaches its gates without its spec. |
| A4 | HIGH | Each contradiction needs proof that its exit works, not wording. | Resolved: `tests/test_one_action.py` drives the real commands through the PreToolUse hook and the Agent launch guard (`fakes.day.Day`), red on the base branch for each claim that holds. |
| A5 | MEDIUM | A shepherd that keeps stopping without a PR could loop. | Resolved: one fresh seat, one more per owner resume; then the item parks with a reason in `derive.ASK_PARKS`, so next asks the resume card (FR-008). |
| A6 | MEDIUM | An owner Yes on a Blocked card could continue the builder forever if it stops on the same line. | Resolved: the build record keeps the answered line; one continue per answered line, then the build goes on to its checks. |
| A7 | MEDIUM | A late initial verdict at a head other than round one's would trip merge's round-one HEAD agreement. | Resolved: it is recorded as a later round's (`round: delta` under the initial key, as `rotate` does) (FR-005). |
| A8 | MEDIUM | #927 edits `raise_action`, `resolve_offer` and `derive.offers`. | Accepted: this change keeps to `raise_action`'s stopped-seat branch, `resolve_offer`'s build and gate branches and the gate branch of `offers`; the merge of the two is mechanical. |
| A9 | LOW | `_blocked` read only seat agent ids, which a builder bound by its build record does not have, so the gate's Blocked card never fired in a real day. | Resolved in passing: it reads the build record's agent id too (needed by FR-009). |
| A10 | HIGH | Review F1: a late initial FIX, PARK or ESCALATE was read only through the delta re-read, so a later PASS waved it through. | Resolved: `decide` judges a late initial at the current head as an initial verdict (FR-005); `test_a_late_initial_that_blocks_is_judged_as_an_initial_verdict`. |
| A13 | MEDIUM | Review F2: a stale second opinion collided with its base role's fresh seat and dispatch opinion returned the stale record. | Resolved: FR-005a; `test_a_stale_second_opinion_reruns_through_dispatch_opinion`. |
| A14 | LOW | Review F4: an owner step behind the set's decision stayed in the launches as a command. | Resolved: FR-004; `test_an_owner_step_behind_the_sets_decision_is_not_a_launch`. |
| A15 | LOW | Review F3: the shepherd retry and #927's `_seat` helper both rewrite raise_action. | Deferred to the rebase (coordinator). |
| A11 | LOW | The round cap stays an owner decision through `dispatch next` (two steps to the resume card). | Accepted: the loop property test (`test_loop.py`) holds exactly one owner decision; dispatch next parks and next asks the resume card. |
| A12 | LOW | A builder not stood down at a gate still refuses in dispatch next. | Accepted (spec Assumptions); no executable step exists there. |

Coverage: FR-001 to FR-011 each have tasks (T001 to T019), 100 percent. CRITICAL 0 open, HIGH 0
open.

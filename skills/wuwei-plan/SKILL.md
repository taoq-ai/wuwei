---
name: wuwei-plan
description: Propose the day with lead discovery and run the morning gate before dispatch.
---

# /wuwei plan

Run this in a WUWEI workspace. Read `.wuwei/config.toml`, `.wuwei/memory/goals.md`, today's state, the most recent prior day's state, report and retro, and the configured repositories. Use the executable recorded in `.wuwei/executable` for CLI calls. Never invoke Python without `-P`. Do not create a worktree, claim an item, write to a tracker or dispatch a builder before approval.

Register this planner session with `wuwei plan session "${CLAUDE_SESSION_ID}"` before the sweep. Use the current session ID supplied by the skill runtime, never a seat's ID. Repeat registration when resuming planning in a new session or after day rollover. Only this registered session's Stop hook can acknowledge a planner wake.

1. Sweep live processes and lingering worktrees with measured host and VCS inputs. Record what was found and action taken. Refresh open PRs and obligations through configured adapters. Mark a missing adapter or failed measurement `unmeasured` with its reason. Do not call an absent measurement clean.
2. Dispatch one lead seat with `charters/lead.md`, `charters/_common.md` and `charters/_common-authoring.md`. Give it the goals and measured discovery inputs: tracker backlog, base-branch red checks, review and scanner findings, review threads, outcome metric regressions and follow-ups from today's PRs. Ask for one JSON proposal with `goals`, `cap`, `seat_policy`, `envelope`, `sweep` and ordered `candidates`. Each candidate needs `id`, `goal`, `evidence`, `scope`, `overlap`, `track`, all three boolean flags, and `score` and `evidence_lines` for each component of the configured framework. The lead checks open status and duplicate or overlapping work against today's items and other active work. Propose ranks with `wuwei rank`.
3. Write the lead JSON under today's day directory and call `wuwei plan propose <json-file>`. Read the generated `days/<date>/plan.md`; verify source failures, carry-over candidates, queue, CAP, seat policy and envelope are visible. Include a proposed explicit import of unfinished prior-day items when appropriate.
4. Run the morning gate with one AskUserQuestion per decision. Every question starts with `Morning gate` and cites `days/<date>/plan.md`. Ask separately for goals, queue, seat policy, CAP, envelope and carry-over as needed; put the recommended choice first. If the owner edits the proposal, update the lead JSON and rerun `wuwei plan propose` before asking for final approval. Do not infer approval from silence.
5. After the owner confirms the goals and approves the queue and settings, call `wuwei plan approve --items <approved IDs> --goals-confirmed`, adding `--import-yesterday` only if carry-over was explicitly approved. Verify `wuwei state get` shows `gate_approved`, `goals`, `approved_items`, `seat_policy`, `cap` and `envelope`; for carry-over, verify a `state.import` event. Only then continue to dispatch, with host floors checked at launch.

A CLI exit of 1 is a finding to resolve with the owner. Exit 2 means the plan could not run; show its reason and stop dispatch.

## Item dispatch and receive

For an approved code item, use its own worktree and the recorded seat policy. Run the builder through `wuwei build` with the item's fast checks. Before pre-PR gates, stop the builder, confirm its stop event and move the item to `gate`. Call `wuwei dispatch next <item>`. For an `action: gates` result, write one brief per returned role using `wuwei brief --gate --worktree`, then launch those roles in parallel. The brief and launch commands refuse a dirty tree, live builder and missing evidence. A refused brief is never launched.

When each sentinel stops, call `wuwei dispatch receive <item> <role> <seat-name>`. This lints and records the verdict file at the dispatched HEAD. Rejected or unmeasured verdicts return to that seat; they never count as PASS. Call `wuwei dispatch next <item>` again after each receipt. Wait for all required verdicts before a fix or PR raise.

For `action: fix`, transition the item to `fix`, give the builder only the named findings, run its fast checks and stand it down. Transition to `delta`; `wuwei dispatch next` returns only gates that gave FIX. Continue those same sentinel seats with the diff since their first verdict and parked findings by id; use a fresh seat only if the sentinel was lost. Receive deltas with `--round delta`. After the delta, `action: raise` includes residual review notes for the PR body. `action: escalate` blocks the PR. Do not run another pre-PR fix round. Once the PR is open, use the normal shepherd and review flow; pre-PR gates do not repeat.

The watch sweep emits a discovery request. A freed builder seat emits one when the queued planned item count is below `discovery.min_queue`. Discovery ranking and intraday start decisions are owned by the discovery workflow.

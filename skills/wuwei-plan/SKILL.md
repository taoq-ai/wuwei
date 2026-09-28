---
name: wuwei-plan
description: Propose the day with lead discovery and run the morning gate before dispatch.
---

# /wuwei plan

Run this in a WUWEI workspace. Read `.wuwei/config.toml`, `.wuwei/memory/goals.md`, today's state, the most recent prior day's state, report and retro, and the configured repositories. Use the executable recorded in `.wuwei/executable` for CLI calls. Never invoke Python without `-P`. Do not create a worktree, claim an item, write to a tracker or dispatch a builder before approval.

1. Sweep live processes and lingering worktrees with measured host and VCS inputs. Record what was found and action taken. Refresh open PRs and obligations through configured adapters. Mark a missing adapter or failed measurement `unmeasured` with its reason. Do not call an absent measurement clean.
2. Dispatch one lead seat with `charters/lead.md`, `charters/_common.md` and `charters/_common-authoring.md`. Give it the goals and measured discovery inputs: tracker backlog, base-branch red checks, review and scanner findings, review threads, outcome metric regressions and follow-ups from today's PRs. Ask for one JSON proposal with `goals`, `cap`, `seat_policy`, `envelope`, `sweep` and ordered `candidates`. Each candidate needs `id`, `goal`, `evidence`, `scope`, `overlap`, `track` and all three boolean flags. The lead checks open status and duplicate or overlapping work against today's items and other active work. Preserve the lead's proposed order until `wuwei rank` is available.
3. Write the lead JSON under today's day directory and call `wuwei plan propose <json-file>`. Read the generated `days/<date>/plan.md`; verify source failures, carry-over candidates, queue, CAP, seat policy and envelope are visible. Include a proposed explicit import of unfinished prior-day items when appropriate.
4. Run the morning gate with one AskUserQuestion per decision. Every question starts with `Morning gate` and cites `days/<date>/plan.md`. Ask separately for goals, queue, seat policy, CAP, envelope and carry-over as needed; put the recommended choice first. If the owner edits the proposal, update the lead JSON and rerun `wuwei plan propose` before asking for final approval. Do not infer approval from silence.
5. After the owner confirms the goals and approves the queue and settings, call `wuwei plan approve --items <approved IDs> --goals-confirmed`, adding `--import-yesterday` only if carry-over was explicitly approved. Verify `wuwei state get` shows `gate_approved`, `goals`, `approved_items`, `seat_policy`, `cap` and `envelope`; for carry-over, verify a `state.import` event. Only then continue to dispatch, with host floors checked at launch.

A CLI exit of 1 is a finding to resolve with the owner. Exit 2 means the plan could not run; show its reason and stop dispatch.

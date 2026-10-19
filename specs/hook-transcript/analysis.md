# Specification analysis: hook-transcript

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance, spike-962's run evidence, the owner's trust ruling of 2026-10-19 and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | HIGH (closed) | spec.md What the real flow showed | The promise says PostToolUse records the answer when the transcript holds its tool_result; the real flow shows that row is written 11 ms after PostToolUse returns, so the literal design records nothing real | Resolved: PostToolUse keeps the answer and the planner's next hook call records it; the trust model the owner ruled is unchanged. Recorded under Assumptions with what overturns it |
| A2 | Inconsistency | MEDIUM (closed) | plan.md Lines | The item budgets +22 runtime lines; the change adds 84 (3,208 to 3,292 on main d4a803f, after fix round 1) | Recorded as an assumption: the deferred confirmation (claim, wait, notes) and the seat launch check were not in the estimate. Runtime stays under the 3,400 cap |
| A3 | Coverage | MEDIUM (closed) | spec.md How this fails 3 | Codex answers and seat stops become unconfirmed, so a Codex gate is no longer attested | Recorded as an assumption; the Codex page already says to run gates as Claude seats. A Codex transcript reader is a follow-up item |
| A4 | Inconsistency | MEDIUM (closed) | spec.md Clarifications | The brief names the projects folder as "the folder the real path sits in"; a folder read from HOME or CLAUDE_CONFIG_DIR is the caller's | The folder comes from the password database; a real-entry test sets both variables |
| A5 | Coverage | LOW | spec.md What stays open | A replayed real answer or a real seat's stop repeats a record | Recorded as residual risk: the rows repeat what the harness recorded |
| A6 | Coverage | LOW | spec.md How this fails 2 | A session that asks and never calls again leaves the answer pending | Recorded; the transcript keeps the answer, so the owner can be asked again |
| A7 | Scope | LOW | spec.md Added from the write probe | `find` in the wrapper unwrap list also closes a ledger hole outside the item | Kept: the same line guards both, the probe found it, and it only refuses more |
| C1 | Coverage | LOW | tasks.md T019 | Six forge shapes left no row in the real-entry probe (no payload reached the entry) | The in-process forge class covers their payloads; the probe states them as unmeasured |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 projects folder from the password database | yes | T010, T019 | |
| FR-002 transcript_rows | yes | T005, T011 | the forge class's path cases |
| FR-003 PostToolUse keeps or refuses at once | yes | T004, T005, T011 | |
| FR-004 planner calls confirm; a Stop waits then records unconfirmed | yes | T004, T005, T011, T020 | race and wait tests |
| FR-005 SubagentStop launch check | yes | T006, T012 | |
| FR-006 running subtracts seat.unconfirmed | yes | T012 | |
| FR-007 guard refusals with the read routes | yes | T007, T013, T016, T017 | |
| FR-008 find after a wrapper | yes | T017, T018 | |

## Constitution alignment

No conflict: stdlib only in the runtime, no config key, test first, the records door extended to
the harness's transcripts under the owner's trust ruling. The runtime stays under the 3,400 cap;
the item budget overrun is A2.

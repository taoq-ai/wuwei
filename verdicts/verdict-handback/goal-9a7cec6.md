Verdict: PASS
Gate: goal
Item: verdict-handback
PR: taoq-ai/wuwei
Head: 9a7cec600c3e89192b872d23b8714a26d654504b
Confidence: high

## Findings
- [low] cli/wuwei/verdict.py:8 blocks: no. The two real 1068 verdicts still fail the head's grammar, which is correct: 802ced3 has a note with no "blocks:" at all, and 82680c3 names several locations in one finding ("guards.py:122-126, 207-211; hook.py:15-26,181-190"). The head does not make either parse. What it fixes is the silence: both now get a denied hand-back that the seat can act on, and if the run ends anyway they get a verdict.missing row. The shape error does not say "one location per finding", so a seat that hits the 82680c3 form will need a second try.
- [low] cli/wuwei/hook.py:195 blocks: no. Removing post_tool's Agent hand-back re-read drops the #1039 fallback. It only matters if PreToolUse lacks agent_type and the stop also cannot read the transcript. The harness schema says agent_type is present inside a subagent (see Probes), so this is a residual edge, not a regression in practice.

## Probes
- Requirement trace: the promise's three parts and five acceptance scenarios map to hook.py pre_tool/subagent_stop/transcript, verdict.py FINDING/parse/FORMAT, charters/_gate.md and the rebuilt agents/, and the tests test_a_malformed_verdict_denies..., test_a_well_formed_verdict_is_attested_once..., test_a_problem_found_after_the_handback_ended_the_run_is_recorded, test_a_note_needs_no_file_line_but_a_blocking_finding_does, plus the size test. The spec's explain-back matches the item. I found no unrequested behavior beyond the design.md hook table rows.
- agent_type assumption, settled. In the installed harness binary (/opt/claude-code/bin/claude), every hook's base input schema documents agent_id ("Present only when the hook fires from within a subagent") and agent_type ("Present when the hook fires from within a subagent (alongside agent_id)"). The PreToolUse schema is O().and({hook_event_name:"PreToolUse",tool_name,tool_input,...}), so it inherits both fields.
- Live evidence: .wuwei/traces.jsonl (618 rows, built from PostToolUse payload agent_id) has agent_id set on 487 subagent tool calls, including 30 with tool "SubagentHandback". So the harness names the tool SubagentHandback and sends subagent identity on tool hooks. Neither the ledger nor traces stores agent_type itself, so that part rests on the schema text, not on a recorded payload.
- 1068 replay: scratch/replay.py ran on the main copy and the head copy (git archive). verdict.parse strict rejects quality-82680c3.md and quality-802ced3.md on both. A head-path replay of a SubagentHandback PreToolUse with agent_type wuwei:sentinel-quality denies with the bad line plus FORMAT, records 1 refused row and 0 attest rows. A following SubagentStop, whose transcript ends with the hand-back, returns None and records verdict.missing with the problem. On main nothing was recorded: grep of .wuwei/ledger for 1068/quality-8 finds no attest and no verdict.missing row, which confirms the original silent loss.
- Suite at the head in a scratch copy: 403 passed. The runtime is 2997 lines (cat cli/wuwei/*.py | wc -l). The .claude/wuwei mirror of charters matches.
- Confidence reason: the harness schema and the live agent_id traces agree, and the replay shows the real failure turned into a deny plus a record. The only unproven step is a recorded agent_type value on a subagent PreToolUse.

## Residual risk
If a future harness drops agent_type from PreToolUse, a bad verdict is recorded rather than fixed: the stop path still catches it. The multi-location finding form still costs a seat one retry.

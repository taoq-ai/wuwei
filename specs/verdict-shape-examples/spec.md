# Feature Specification: the gate charter shows each finding shape, and a refused verdict leaves no stale line

**Item**: 1179, tier standard, goal G-2
**Input**: taoq-ai/wuwei#1179. Six verdicts in one workspace on 2026-10-19 were refused for shape: a
finding with sub-bullets, two PR body findings without a `<file>:<line>`, and a blocking finding
whose text read `Failure (contract, ...` instead of `Failure: `. Each refusal cost a gate run.

## The promise in my words

1. `charters/_gate.md` under The verdict says, with one example line each: every line under
   `## Findings` is one whole finding (no sub-bullet, no continuation line, detail goes under
   Probes); a note about the PR body names no file (`- [low] blocks: no. PR body: ...`); a blocking
   PR body finding names `PR-body:0`; a blocking finding's text starts with exactly `Failure: `, its
   class in parentheses after the scenario.
2. A test reads every example finding line from the charter and asserts `verdict.parse` accepts it,
   and that the parser refuses the three shapes from the issue.
3. The generated sentinel agents stay at or under 2,250 words. sentinel-arch was at 2,250, so the
   edit deletes as many words as it adds.
4. `evidence.uncounted` lists only the verdict files of the gates the gap names. A refused
   `security-<h7>.md` beside a counted `security-<h7>-2.md` no longer shows when only quality is
   missing. A file whose `Gate:` is not a known gate still shows, so no refused file goes silent.
5. Already on main, no change: a Claude sentinel gets the refusal naming the offending line at its
   SubagentHandback (hook.py pre_tool) and at its stop (hook.py subagent_stop). A new hook test pins
   the sub-bullet case.

Acceptance, restated:

1. The charter's example lines parse; the sub-bullet, `PR body, "Size:" line` and `Failure (` shapes
   are refused.
2. `bin/wuwei agents build` and `bin/wuwei agents check` pass, every agent at or under 2,250 words.
3. Security passed at h through `security-<h7>-2.md`, a refused `security-<h7>.md` beside it,
   quality missing: the not-counted lines name no security file.
4. Quality missing and an unattested `quality-<h7>.md`: evidence still names it with its reason.
5. A sentinel hands back a verdict with a sub-bullet under Findings: the hand-back is denied naming
   the line.

## Assumptions

- Ask 2 of the issue (refusal at write time) is already on main for Claude sentinels: pre_tool runs
  `_verdict_problem` on SubagentHandback and denies with each shape error, the line included
  (tests/test_hook.py `test_a_malformed_verdict_denies_the_handback_with_its_shape_errors`). Codex
  seats are item 1181. Overturned if a refused verdict reaches the board from a Claude sentinel
  whose hand-back was not denied.
- A verdict whose `Gate:` cannot be read is listed whatever gate the gap names, since its gate is
  unknown. Overturned if the owner wants those hidden too.
- `PR-body:0` is the fixed token for a blocking finding about the PR body. The parser already accepts
  any `\S+:[0-9]+` place, so no parser change is needed.

## Out of scope

Loosening the parser; Codex gate seats (1181); dropping the lines an exception covers (1168).

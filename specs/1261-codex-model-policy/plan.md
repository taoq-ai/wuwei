# Implementation plan

## Technical context

Python 3.11 stdlib runtime. Existing agents.TABLE, ws.config models, Codex adapter, seat.started ledger rows and report grouping remain the only paths. No owner-session configuration is written.

## Constitution check

Stdlib only, six config keys, test first, no new door or attestation. The owner approved two extra runtime lines for the final parser correction, +23 against parent 0d83e22e and 3,800 total here. The current global cap is 4,000. Source changes wait for focused red tests. hook.py waits for item 1254's pushed source head.

## Phase 0: research

Read the approved item, design, constitution and model paths. research.md records catalog and schema evidence; no unresolved clarification.

## Phase 1: design

render_codex takes existing models rows and an optional tier, default standard. A small shared setting selector maps table names and honors owner precedence. setup.init and doctor pass current models rows. Native adapter keeps original response resolution. PostToolUse records requested settings in asked/effort, child resolution in model, and launching-turn metadata with explicit names. fork_turns=all records the requested fork policy, not proof of actual child settings. Existing report grouping labels those fields.

No contracts directory: no new public interface or protocol. data-model.md names existing-row extensions. quickstart.md gives the consumer check.

## Implementation order

1. Focused generation/override/doctor failing tests, then minimum renderer/setup changes.
2. After rebase on 1254, focused requested/resolved/turn/fork report tests, then adapter/record/report changes.
3. Documentation, generated/vendor synchronization, focused checks, serialized full suite and route differential, analysis and draft PR.

## Approved parser correction

The prior effort regex overlaps the model-token and line-remainder quantifiers. Missing effort can make launch processing quadratic. Capture the model line once, split spaces and tabs, then find the first separate effort token after the model. Keep the existing multiword names, parenthesized suffixes, owner precedence and sanitized recording. Add bounded real-hook tests for long tokens and space tails, with separate-effort controls. Run focused checks, actual-hook growth measurements and main/parent/head routes; the planner controls further full-suite and mutant runs.

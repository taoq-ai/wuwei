# Implementation Plan: #949

## Technical context and constitution check
Stdlib Python 3.11+, existing event patches and atomic files. Tests use pytest and fake
adapters. Scope is this worktree. The review follow-up explicitly requires one full suite with eight workers. The issue authorizes the 5.7 change described under spec Assumptions.
No owner design edits. No new runtime modules or process. Tests precede runtime edits.

## Root cause and research
- commands/next.py:285 (baseline) closes an exhausted queue without reading goals.
- plan.py:275 (baseline) rejects every post-gate proposal before discovery.
- guards/__init__.py:13 and hooks/hooks.json omit Stop entirely.
- goals.py stores goal definitions, no completion status. No current auto-start bar.
- brief.write already injects discovery for every lead; reuse it for lead-N.
- sessions.needs_owner supplies content-bound one-use Owner step answers.

## Design
Keep row selection in next.step. Add a read-only refill selection helper there using
gate-approved goal snapshots, bounded refill counts and recorded outcomes. Number briefs/outputs by completed refills;
a running lead returns wait. Propose receives the number and uses the existing
validation/discovery/ranking pipeline before branching to refill admission. Share the
candidate-to-item state writer with morning approve. Store refill results as plan.approved event
patches with a refill number, admitted IDs and flags; retain exceptional proposals until owner answer. Suppress repeated empty
searches by exact goal snapshots. Render no-work goals in report.build.
Register lifecycle.stop in the guard registry. Stop checks day, planner, owner waits
and row signatures with the per-day block cap. The dispatcher translates its finding into block JSON,
exit 0, and its failures into recorded fail-open diagnostics. Avoid adapters, discovery,
launch resolution and long lock waits in this path.

## Validation
Reproduce exhausted client inventory/mapping/stakeholder goals, safe and exceptional
admission, empty search/report/dedupe, productive recurrence, changed goals, closed
day and every Stop exemption. Replay Stop through the executable shim. Run every
file importing a changed module plus hook/config contract tests, explicitly named,
using the task-specified interpreter and -p no:cacheprovider. Review diff for security,
correctness and excess code; record evidence in analysis.md.


## Review correction plan
Root causes before edits: lifecycle.py:100 counts next.action itself as progress;
next.py:181 has no count or time bound and reads memory directly; plan.py:473 rejects
unresolved repos for the entire batch and :479 admits empty-path/non-build work;
sessions.py:106/126 retains global owner requests; report.py:136 unions all passes.
signal.py:91 has no explicit Stop diagnostic tier, and its quiet list omits Stop blocks.

R001 updates assumptions, exact owner-design proposals, tasks and analysis. R002 writes
and observes regression failures. R003 replaces the Stop progress count, deletes global
owner-request tracking and classifies emitted events. R004 bounds refill selection and
admission, snapshots approved goals, references lead inputs and restricts automatic
admission. R005 reports only the latest search and bound reason. R006 runs affected
checks and the requested full suite once. No new modules; both next and report reuse
the same read-only refill bound check. L4 remains deferred as recorded in the spec.

## Round 2 correction
Root cause: commands/next.py:188-189 applies time.fromisoformat to a full datetime;
report.build calls this same helper. No existing envelope-end parser exists in
cli/wuwei. Use datetime.fromisoformat first, then the existing day/time combination,
and ignore invalid values. lifecycle.py:102 returns at the cap without a signal;
append one bounded-time hook.stop_capped event and classify it warn. Tests first for
next/report across formats, warning deduplication and status classification.

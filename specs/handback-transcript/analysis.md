# Specification analysis: handback-transcript

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item handback-transcript's
promise and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | HIGH | item promise | "never from the payload" while the PreToolUse payload names no agent transcript | Resolved in Clarifications: the seat transcript beside the session's, the payload text only picks one of the seat's own reports; tests and mutant M9 |
| A2 | Ambiguity | MEDIUM | item promise | Whether the rule covers non-gate seats at SubagentStop | Resolved: one rule for every seat stop; a report the transcript does not hold is not kept |
| C1 | Coverage | HIGH | acceptance 1 | A forged hand-back could still count through a link out of the folder | Resolved: links resolve and must stay under the projects folder; tests at both doors, mutant M6 |
| C2 | Coverage | MEDIUM | acceptance 2 | The real flow rested on hand-made transcripts | Resolved: fixtures built from a real session by fixtures.py |
| R1 | Risk | MEDIUM | spec How this fails 1 | The hand-back row may not exist when PreToolUse runs | Kept as residual: the stop still attests from the transcript; measured that the row exists while the tool runs |
| R2 | Risk | MEDIUM | spec How this fails 3 | A replayed real report re-reads a rewritten verdict file | Kept as residual, named in SECURITY.md; outside this item's promise |
| M1 | Mutants | LOW | mutants.txt | M11 survives | Recorded with its reason; the attested text is the seat's own in both readings |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement | Task | Test or evidence |
|-------------|------|------------------|
| FR-001 | T003, T008 | test_a_forged_handback_naming_a_pass_verdict_attests_nothing_and_evidence_does_not_count_it; test_a_launched_gates_handback_its_transcript_does_not_hold_attests_nothing |
| FR-002 | T003, T007 | test_a_replayed_gate_stop_with_a_forged_report_attests_nothing; test_the_real_gate_flow_with_a_forged_report_attests_nothing |
| FR-003 | T006, T013 | the link cases above; test_an_unreadable_or_odd_seat_transcript_never_attests_a_payload_report_twice_or_errs; mutant M6 |
| FR-004 | T004 | test_the_real_gate_flow_attests_at_its_handback_once_and_records_its_stop; test_every_fixture_payload_replays_without_an_error; route_diff.txt |

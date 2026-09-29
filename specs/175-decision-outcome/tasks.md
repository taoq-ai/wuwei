# Tasks: Decision outcomes and two-way digest

**Input**: [spec.md](spec.md), [plan.md](plan.md)  
**Tests**: Each behavior gets a failing test first.

- [X] T001 Add failing owner outcome, refusal, resume and report tests.
- [X] T002 Implement validated host-confirmed outcomes and item resume.
- [X] T003 Add failing reversal and measured zero metric tests.
- [X] T004 Record reversals and update the metric.
- [X] T005 Add failing digest batching, cooldown, draft and failure tests.
- [X] T006 Implement digest sweep through chat port with a fixed two-hour interval.
- [X] T008 Close opaque owner-outcome wrapper calls and draft digests when chat is unconfigured.
- [X] T009 Cover digest cooldown with a new decision and resumption through a build park link.
- [X] T010 Refuse unresolved commands individually in owner-outcome scripts; cover mixed route/expect, script, unbuffer and allowed route commands test first.
- [X] T011 Pin temporary Git commit timestamps to the retro test's workspace date after reproducing its date-dependent failure.
- [X] T007 Run full pytest suite and hygiene checks.

## Deferred

General approval draft sending belongs to issue 174.

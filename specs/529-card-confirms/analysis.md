# Specification Analysis Report: 529-card-confirms

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md`, design
5.2 (`Records`, #357), 5.8 and 9.1, and the code the plan names (`setup.set_value`,
`config.offer`, `integrity._host_confirm`, `guards/decision.record_gate`,
`guards/protect_state`, `sessions.gate_topics`, `commands/decision.decide`, `mandate`,
`owner_outcome`, `commands/outbound.apply`, `interview`, `commands/calibrate`). The base
has no `tests/test_invariants.py` (task T028 is conditional).

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Inconsistency | HIGH | US2 vs #530 `mandate` (`commands/decision.py:79-103`) | Under the default autonomous mode `decision route` takes a two-way, clear record under mandate with no card, so a config question written as a plain record would never reach the owner and `--from-card` could never pass. | Resolved: a config card record carries `Decided-by: owner` (the outbound learn precedent), which `mandate` hands to the legacy route and `route()` sends to the owner. Spec Assumptions, US2 intro, plan skill text and T013 fixture state it; a mandate-taken record has no card answer, so `--from-card` exits 1 (safe). |
| A2 | Security | HIGH | FR-001, FR-006 | If the hook let any planner `config set` through after any card, or trusted the planner's KEY VALUE, a planner could write a value the owner did not pick. | Resolved: the CLI checks the recorded answer itself (`card_answered` on the hashed answer, written only by `record_gate` from the harness payload) against the option title `KEY = VALUE`; the hook gate is only the existing friction layer (asked `D-n`). Seats stay refused (`agent_id`). Tests T013, T014, T018. |
| A3 | Inconsistency | HIGH | issue "never prompt y" vs strict | The issue says no prompt, and also that strict keeps the prompt. | Resolved: strict records no card answers (`gate_topics` returns nothing) and `set_value` ignores `--from-card` there; FR-007, US3, T020. |
| A4 | Coverage | MEDIUM | issue "every card that leads to a config write" | `telemetry proposals --widget` cards still print a host-terminal `config set`. A `Yes` there is not bound to one key and value, so it cannot be checked like FR-006 without a new card identity. | Accepted and deferred in spec Assumptions; the owner's named keys (cap, host.seats, outbound.default_tier, learn mode, tier rows and people through outbound learn) are covered. |
| A5 | Ambiguity | MEDIUM | `--from-card <decision id>` vs `calibrate --answer` | Two record commands could look like two mechanisms. | Resolved: one recording rule (FR-001) and one helper (`card_answered`) serve both; `--from-card` takes a `D-n`, interview cards keep their own record command (Assumptions). |
| A6 | Underspecification | MEDIUM | FR-006 ordering | Config written, then the decision outcome fails (record not routed): partial state. | Accepted: config first so an invalid value records nothing; both steps are idempotent and a rerun completes the outcome (Edge Cases, T014). |
| A7 | Collision | MEDIUM | FR-001 topic by header | Topics are keyed by card header; the repository row `gates` and the workspace row `reviewers` share `Reviewers`, so one answer could stand for the other. | Resolved: `gates` header becomes `Gate floor`; T005 pins unique headers. Other Morning gate headers (`Plan`, `Telemetry`) only collide on answers that fail `interview.effects`, so nothing is written. |
| A8 | Constitution | MEDIUM | FR-012, program rule | The item must add no refusal under observe or guarded. | Checked: the hook change only lets more through; the session exit 1 replaces an empty-answer decline (exit 1) or a `HOST_TERMINAL` exit 2 with a named next step; no guard gains a refusal. |
| A9 | Performance | LOW | `record_gate` on the hook path | New imports would cost hook latency (#542). | Resolved: only `sessions.card_topic` (stdlib `hashlib`); no interview import in the hook (plan Must not change). |
| A10 | Usability | LOW | `setup` | `setup` asks four more rows at the host terminal. | Accepted: one interview table; the first choice is the shipped default (Assumptions). |
| A11 | Trust | LOW | `calibrate --answer` from a seat | A seat sharing the planner's session id can run it. | Accepted: it writes only exactly what the owner answered on the card. |
| A12 | Terminology | LOW | spec, plan | "card" names the widget, `--from-card` takes a decision id. | Defined in spec Assumptions and Key Entities. |

No CRITICAL findings. HIGH findings A1 to A3 are resolved in the artifacts.

## Coverage summary

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T003, T004 |
| FR-002 | T001, T002 |
| FR-003 | T005, T006 |
| FR-004 | T007, T008 |
| FR-005 | T009, T010, T011 |
| FR-006 | T012 to T015 |
| FR-007 | T018 to T021 |
| FR-008 | T022, T023 |
| FR-009 | T018, T019 |
| FR-010 | T016, T017 |
| FR-011 | T024, T025 |
| FR-012 | T018, T022 (no new refusal asserted), T028 when present |
| FR-013 | T026, T027 |

Every behaviour task has its test task before it; no task without a requirement; no
requirement without a task.

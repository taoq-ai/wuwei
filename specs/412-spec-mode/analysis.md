# Analysis: Specification mode

Cross-check of spec.md, plan.md and tasks.md against design 5.10 and the constitution, run
before implement. No CRITICAL or HIGH finding; the MEDIUM and LOW rows were resolved during
implement as noted.

| ID | Category | Severity | Location | Summary | Resolution |
|---|---|---|---|---|---|
| A1 | Consistency | MEDIUM | plan.md `once` | Read then append outside a lock can write a duplicate event. | `once` reads and appends under the day's `state.lock`; no race remains and no `ponytail:` note is needed. |
| A2 | Conflict | MEDIUM | tasks.md T031, interview | The new glossary term "spec engine" would fail the plain-words interview test on the question text that design 5.10 fixes. | The `spec` question text is exempt in that test; its header is the plain word `Spec`. |
| A3 | Conflict | LOW | template `[spec]` | `tests/test_docs.py` forbids any `mode =` line (it guards the retired `guards.mode`). | The test now ignores the one `[spec]` `mode` line. |
| A4 | Coverage | LOW | plan.md "no assertion is changed" | One more interview question changes the question list and the answer count in two interview tests. | Those two expectations gain the new question; nothing else changes. |
| A5 | Coverage | LOW | scripts/headless_e2e.py | `fixture_plan` also feeds the paid rehearsal item. | Both get `tier: light`; a lead tier never lowers the gates, and their small diffs keep the skip. |
| A6 | Coverage | LOW | doctor, setup | Under the default `speckit`, a repository without `.specify/` makes doctor fail its spec row, so a first-day setup is not Ready until spec-kit is installed. | Intended by 5.10; the first-day setup test's repository carries `.specify/`. |
| A7 | Ambiguity | LOW | plan.md `check_stop` | An unmatched builder stop (no brief reference) is already recorded by `agent_launch.stop`. | `check_stop` returns clean there instead of exit 2, so it never blocks a stop the seat registry does not know. |

CRITICAL issues: 0

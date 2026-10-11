# Specification Analysis Report: 799-config-unknown-keys

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md` (1.5.0),
the #789 pass plan (PR 2), and the code at bfbf6a3.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| H1 | Inconsistency | HIGH (resolved) | plan.md item 2 | A first draft reassigned `text` with the pruned config. `upgrade` prints the `repos = []` line on `text != raw` and passes `text` to `security.load` and `_guide`, so the reassignment would misreport the repos removal. Found while prototyping. | plan.md now names a separate `pruned` variable and says not to reassign `text`. |
| M1 | Constitution | MEDIUM | spec Assumption 8; constitution VII | VII says refusals stay under `strict`. The deleted raise is a config-load error over a key nothing reads, not a guard; no guard area changes, and the #496 `outbound.tiers` refusal stays. | Recorded in the spec; the #789 pass plan names this change. No conflict. |
| M2 | Ambiguity | MEDIUM | spec Assumption 1 | The issue says "every key the schema no longer reads". A typo also gets removed, which drops the owner's intended value. | Recommendation recorded: remove it. The `did you mean` warning prints first, `--dry-run` previews, and the `doctor` template row lists the `Would upgrade ... remove` line before anything is written. |
| M3 | Coupling | MEDIUM | plan.md item 2 | `_unread_keys` reads paths out of the warning text, so a change to that text breaks it. | T007 feeds real `load_config` warnings, so a format change fails a test. `_validate` stays the only judge of what is unknown (Principle III). |
| L1 | Constitution | LOW | spec Assumption 7; constitution Workflow | The constitution asks for an invariant row per guard change; #789 PR 1 deletes that bullet. This change is not a guard either way, and `tests/test_invariants.py` has no row on unknown keys. | None needed. |
| L2 | Edge case | LOW | spec US1 scenario 3 | An unknown key inside `[[outbound.tiers]]` still raises, so `init --upgrade` exits 1 on it and cannot remove it. | Intended (b) check until #789 PR 16 replaces the tiers; stated in the spec. |
| L3 | Cosmetic | LOW | spec Assumption 3 | Comments above a removed key stay behind. | Accepted; the check compares parsed values. |

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 unknown keys warn in every posture | T001, T002, T005 |
| FR-002 `outbound.tiers` raise kept | T005 (kept code); existing outbound tests unchanged |
| FR-003 removal and per-key line | T007, T008, T011 |
| FR-004 parsed remainder check, exit 2 otherwise | T007, T011 |
| FR-005 `--dry-run` writes nothing | T008 |
| FR-006 newer template removes nothing | T009, T011 |
| FR-007 removal counts as a change | T008, T011 |

Every task maps to a requirement or to a test that pinned the deleted raise (T003). No
unmapped task, no requirement without a task.

## Metrics

- Requirements: 7; covered: 7 (100%).
- CRITICAL: 0. HIGH: 1, resolved in plan.md. MEDIUM: 3. LOW: 3.

## Next

No CRITICAL or open HIGH finding; `implement` may proceed.

# Specification Analysis Report: 838-outward-allowlist

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.2.0 after part 15);
- the #789 pass plan (owner constraints, "Process control kept", outward duties, #831 handoff);
- part 15's plan (`guards.FLOOR`, the posture reads it removed);
- the code and tests at 703b40de, and a full inventory of every reference to the deleted units.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Security floor | CRITICAL | `outward.check_tier`, `check_call` | The canary and honeytoken egress check lives inside `check_tier` and `check_call`; deleting them would drop the floor for MCP writes and ports. | Resolved. `check_send` calls `security.outbound` for local, owner and allowed calls, and `check_call` keeps it for ports; the canary tests are rewritten, never deleted (T002). |
| P2 | Process control | CRITICAL | US1 | An outward send to other people must stay refused outside policy in both enforce settings. | Resolved. `check_send` is on `guards.FLOOR` and refuses every write or unknown name not on `outward.allow` (T001). |
| O1 | Owner constraint | HIGH | US2 | The owner's own surfaces must be local, with one mechanism (#727). | Resolved. `local()` is the #727 class plus `owner_only`; the surfaces table names the config per surface (`outbound.owner.slack`, `mail`, `pages`); a call with no destination is never local. |
| D1 | Duties | HIGH | ports, `pr act` | Deleting the tiers must not stop the outward duties (pings, tickets, docs pages, the report DM, thread replies). | Resolved. Ports send after the canary check and the lint; `obligations.reply` stays for `pr act --reply` (US4, T003, T004). |
| T1 | Owner constraint | HIGH | `tests/test_tone.py` | The issue deletes `wuwei lint tone`; the owner keeps the CI tone budget test, which imports from `commands/lint.py`. | Resolved. The measure helpers move into the test; only the command and its cases go (Assumption 1, T005). |
| U1 | Upgrade | HIGH | `RETIRED_FILES` | `RETIRED_FILES` only reaches `memory/`, so `.wuwei/graph.json` would stay. | Resolved. One explicit removal with the symlink and inside checks (plan.md, init). |
| S1 | State | MEDIUM | `STATE_PRODUCERS` | It is the generic-write allowlist; removing keys that metrics and telemetry read for past days would break them. | Resolved. Only the keys nothing reads go; `decision_routes` and `decision_outcomes` stay listed; `reply_acks` stays. |
| F1 | Friction | MEDIUM | Assumption 3 | Unknown tool names now refuse (they warned under guarded). | Accepted. The refusal names one line and its card; fail closed matches an exact allowlist. |
| C1 | Card | MEDIUM | `config set --add` | The card command omitted `--add`, so the card would show a replace. | Resolved: the card shows `--add` (T001, T002). |
| R1 | Reasons | MEDIUM | tests/test_reasons.py | The two part 16 LEFT rows go with `drafts.py` and `commands/drafts.py`; the stale check enforces it. | Resolved (T006). |
| X1 | Telemetry | LOW | 5.13 | `draft.*` event names stay in telemetry vocabularies. | Accepted: telemetry is untouched; stored weeks still validate. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 allow key | yes | T001, T002 |
| FR-002 send check | yes | T001, T002 |
| FR-003 owner surfaces | yes | T001, T002 |
| FR-004 port policy | yes | T003, T004 |
| FR-005 deletions | yes | T005, T006, T008 |
| FR-006 retired keys and files | yes | T007 |
| FR-007 no terminal text, card `--add` | yes | T001, T002, T006 |
| FR-008 docs and charters | yes | T009 |
| FR-009 tone budget kept | yes | T005, T009 |

**Constitution Alignment Issues**: none. VII (as amended in part 15) keeps outward sends to
other people on the floor.

**Unmapped Tasks**: none.

**Metrics**: 9 requirements, 10 tasks, 100% coverage; 0 open CRITICAL or HIGH.

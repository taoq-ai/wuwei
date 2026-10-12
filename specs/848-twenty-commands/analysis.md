# Specification Analysis Report: 848-twenty-commands

Artifacts read: spec.md, plan.md, tasks.md; the constitution (2.4.0 after part 23); the #789
pass plan (owner constraints, follow-ups for part 24, the lead note on duplicated docs rows,
the #840 review note on host-terminal docs); part 23's artifacts; the code at 71d3f06b.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Acceptance | CRITICAL | US1 | The issue says "at most 20"; keeping every loop command, the owner's kept `telemetry` and `dora`, `agents` (owner constraint), and the two plumbing commands gives 23. | Resolved: folds by ownership (Assumption 2) and `hook`, `status --line` registered unlisted and documented (Assumption 1). |
| A2 | Hidden caller | HIGH | `status --line` | The owner's `.claude/settings.json` status line runs it; renaming or deleting it breaks every installed status line. | Resolved: kept as plumbing with its flags. |
| A3 | Hidden caller | HIGH | `discover` | The lead charter tells the lead to run it before writing the lead JSON; `plan propose` runs only after. | Resolved: the lead brief carries the candidates (FR-005, T003). |
| A4 | Hidden writer | HIGH | `index` | It is the only writer of `memory/index.md`, which SessionStart reads. | Resolved: promotion and `init --upgrade` write it (FR-006). |
| A5 | Records | HIGH | `RETIRED_FILES` directories | Removing directories (`git-hooks/`, `ziran/`) with a recursive delete could follow a symlink or reach `days/`. | Resolved: FR-007 and T006: inside `.wuwei/`, no symlink, never `days/`; a symlink is named and left. |
| A6 | Owner rule | MEDIUM | goals | A goals change today needs a hand edit; the planner cannot write `goals.md`. | Resolved: replacement blocks through propose and the gate card (FR-009, US3). |
| A7 | Unread key | MEDIUM | `adapters.redactor` | The plan asked to check traces redaction first. | Checked: `registry.load('redactor')` has no caller; traces import `redact.py` (Assumption 8). |
| A8 | Docs | MEDIUM | `reference.md`, `security.md` | Duplicated rows and host-terminal sections (lead note, #840 review). | Resolved: the rewrite keeps one copy or none (plan.md Docs). |
| A9 | Tone | LOW | charters | The defect-class sentences add text the tone and one-home tests read. | Resolved: one sentence per class, each in one charter (T010 runs the tests). |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 deletions and folds | yes | T001, T002, T004 |
| FR-002 plumbing | yes | T003, T004 |
| FR-003 dead subcommands | yes | T004 |
| FR-004 printed names | yes | T005 |
| FR-005 lead candidates | yes | T003, T004 |
| FR-006 index | yes | T001, T002 |
| FR-007 upgrade files | yes | T006, T007 |
| FR-008 retired keys | yes | T006, T007 |
| FR-009 goals | yes | T008, T009 |
| FR-010 defect classes | yes | T010 |
| FR-011 docs | yes | T011 |

**Constitution alignment**: III (each moved job keeps its one function), IV (red before each
behaviour change), V (no new module), VII (no guard loosened; integrity stays a warning).

**Metrics**: 11 functional requirements, 12 tasks, 100 percent covered. CRITICAL 0 open,
HIGH 0 open.

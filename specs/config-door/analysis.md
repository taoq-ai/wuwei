# Specification analysis: config-door

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise and
acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | HIGH | spec How this fails 1, FR-002 | The first head ran only the path class through the probe; the wuwei program class (12 spellings x 20 calls x 13 positions) found 117 seat holes, all an ANSI-C quoted word (`$'plan'`) read as `$plan` | Resolved: every `$'..'` command is unreadable, and a seat's unreadable text is matched without its quotes (C2); 16 tests red at 3dffaf94, green at the head |
| C2 | Coverage | HIGH | FR-002, FR-007 | Two more positions, `eval '<call>'` and `echo '<call>' \| sh`, found 282 holes at c3d77512. `eval` hid every door on main: 220 of 301 corpus routes read differently under `eval` | Resolved: `eval`'s words are read as a `sh -c` body; a seat's unreadable text is matched with quotes removed; 17 tests red at c3d77512; probe holes 0; corpus under `eval` 0 moved at the head |
| C3 | Coverage | MEDIUM | FR-003, mutants | Two mutants survived round 3 (`seat cli word gone`, `seat cli word without $`): no test held the door word for a call sh reads from stdin or eval | Resolved: stdin and eval cases in the seat write list; round 4 killed 33 of 33. Round 5 left three: two showed the `$word` reads redundant (dropped), one gets an unquoted `eval` test; round 6 killed 36 of 36 |
| A1 | Ambiguity | LOW | item promise | `tier` and `approve` are not `wuwei plan` actions on main | Resolved in Clarifications: refused from a seat; the item names them |
| S1 | Scope | MEDIUM | spec Assumptions, FR-007 | Reading `eval`'s words tightens every door for every session, past the item's two files | Kept and recorded: the root fix is one condition in the shared unwrap; owner corpus verdicts do not move |
| S2 | Scope | LOW | SC-003 | 104 seat reads are refused, all unreadable (`$'wuwei'` or fed to `sh` on stdin) | Kept: FR-003 by design, as for `wuwei hook` and the ledger words; the plain spelling passes |
| S3 | Scope | LOW | SC-003 | The owner's `sed -i.bak` inside `.wuwei` is now refused (48 probe cases) | Kept: FR-004 and FR-005; main already refused `sed -i` there |

No CRITICAL or HIGH finding is open. Constitution: test first (129 red on main, 16 red at 3dffaf94, 17 red at
c3d77512), stdlib only, no new dependency or config key, runtime 3,910 at main and 3,918 at the head (+8,
budget 8).
